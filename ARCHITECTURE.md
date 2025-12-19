# Headhunter System Architecture

> Canonical repository path: `/Volumes/Extreme Pro/myprojects/headhunter`. Do not use the deprecated legacy clone location.

## Overview

Headhunter is delivered as a Fastify microservice mesh. Eight HTTP services run in concert with shared infrastructure (Postgres with pgvector, Redis, Firestore emulator, Pub/Sub emulator, mock external providers). Each service is an npm workspace under `services/`, with shared middleware, telemetry, and error handling supplied by `@hh/common`.

`docker-compose.local.yml` is the authoritative definition for local parity. The same topology informs Cloud Run deployments, with managed equivalents for each infrastructure dependency.


## Current Production State (Dec 2025)
> **Note**: The current active AI Search Pipeline operates on **Firebase Cloud Functions** and connects directly to the React Frontend.
> - **Search**: `skillAwareSearch` (Firebase Function) -> Postgres (pgvector).
> - **Analysis**: `analyzeJob` (Firebase Function) -> Gemini (Cognitive Decomposition).
> - **Search**: `JobDescriptionForm` -> `vector-search.ts` (Structured Semantic Anchor).
> - **Reranking**: `rerankCandidates` (Firebase Function) -> Gemini (Reasoning Judge).
>
> The Fastify Mesh described below is the **Target Architecture** for high-scale independence.

## Neural Match Architecture (Agentic RAG)
The system currently implements a **Multi-Signal Retrieval** architecture:

### Multi-Signal Retrieval (v4.0 - Dec 2025)
1. **Classification**: Each candidate is pre-indexed with `searchable.function` (product, engineering, data, etc.) and `searchable.level` (c-level, vp, director, etc.)
2. **Multi-Pronged Query**:
   - Pool A: Firestore query by function (e.g., `function = 'product'`)
   - Pool B: Vector similarity (pgvector)
3. **Scoring**: Function match (60pts) + Level match (25pts) + Company pedigree (30pts) + Vector similarity (15pts)
4. **Cross-Encoder Rerank**: Vertex AI Ranking API on top 50

### Cognitive Matchmaking (Legacy)
1.  **Brain**: Decomposes JDs into 4 Semantic Dimensions (Role, Domain, Env, Scope).
2.  **Body**: Retrieves candidates using a Weighted Semantic Anchor (not keywords, not hard filters).
3.  **Judge**: Scores candidates based on "Blast Radius" and "Domain Fit".

## Service Topology

| Service | Port | Responsibilities | Key dependencies |
| --- | --- | --- | --- |
| `hh-embed-svc` | 7101 | Normalizes profiles, issues embedding jobs, and retains deterministic vectors for downstream services. | Postgres (pgvector), Redis cache, Together AI (mock in local).
| `hh-search-svc` | 7102 | Validates tenant context, performs ANN + deterministic recall, coordinates rerank RPCs, and marshals search responses. | Postgres, Redis, `hh-rerank-svc`.
| `hh-rerank-svc` | 7103 | Maintains Redis-backed scoring caches, merges enrichment artifacts, and enforces the integration baseline (`cacheHitRate=1.0`, rerank latency ≈ 0 ms). | Redis, `hh-embed-svc`, `hh-enrich-svc` snapshots.
| `hh-evidence-svc` | 7104 | Serves provenance, audit trails, and supporting evidence for recruiter UX flows. | Firestore, Postgres, Redis.
| `hh-eco-svc` | 7105 | Manages ECO datasets (occupation templates, validation queues) and shares normalization routines with enrichment. | Postgres, Firestore, filesystem templates.
| `hh-msgs-svc` | 7106 | Handles notifications, outbound messaging, and Pub/Sub topics; syncs queue offsets across Redis + Postgres. | Redis, Postgres, Pub/Sub emulator.
| `hh-admin-svc` | 7107 | Admin APIs, policy enforcement, scheduler jobs, and guardrail tasks; exposes tenant onboarding flows. | Redis, Postgres, Scheduler (Pub/Sub in prod/emulator locally).
| `hh-enrich-svc` | 7108 | Coordinates long-running enrichment pipelines, invokes Python workers under `scripts/` via bind mount, and persists enriched data. | Python worker container, Firestore, Postgres, Redis.

Python enrichment scripts (`scripts/`) are mounted into `hh-enrich-svc` during local runs. Production delegates the same jobs to Cloud Run jobs or Cloud Functions triggered by Pub/Sub.

## Service Dependency Graph

`docker-compose.local.yml` encodes startup order and health probes. Key relationships:

- `hh-search-svc` depends on `hh-embed-svc`, `hh-rerank-svc`, Postgres, and Redis to satisfy requests.
- `hh-rerank-svc` defers readiness until Redis is reachable and baseline caches are hydrated.
- `hh-enrich-svc` waits on Postgres, Firestore emulator, and the Python worker volume mount before starting job consumers.
- Messaging, admin, and ECO services block on Pub/Sub emulator initialization to ensure scheduler topics exist.

When adding new services or infrastructure, reflect dependencies both in compose and in this section to keep the bootstrap contract explicit.

## Shared Infrastructure & Parity

| Local container | Image | Production analogue |
| --- | --- | --- |
| Postgres | `ankane/pgvector:v0.5.1` | Cloud SQL for PostgreSQL with pgvector extension enabled |
| Redis | `redis:7-alpine` | Memorystore Redis (standard tier) |
| Firestore emulator | `gcr.io/google.com/cloudsdktool/cloud-sdk:slim` | Firestore (Datastore mode) |
| Pub/Sub emulator | `gcr.io/google.com/cloudsdktool/cloud-sdk:slim` | Pub/Sub + Scheduler |
| Mock Together AI | `node:20-alpine` (internal mock server) | Together AI hosted API |
| Mock OAuth | `node:20-alpine` (internal mock server) | Google Identity Platform / Auth0 (tenant SSO) |
| Python worker | `python:3.11-slim` | Cloud Run job container (enrichment pipelines) |

Compose networking mirrors Cloud Run service-to-service calls. Environment variables (`.env`, service-level `.env.local`) configure connection strings and mock endpoints. Treat `docker-compose.local.yml` as the blueprint for staging/prod parity.

## Bootstrap Automation Context

`docker-compose.local.yml` currently requires manual sequencing:

1. Install workspace dependencies (`npm install --workspaces --prefix services`).
2. Copy `.env.example` to `.env`, populate secrets, and ensure each service's `.env.local` is aligned.
3. Seed tenants and sample data via helper scripts (`scripts/manage_tenant_credentials.sh`, `scripts/load_demo_candidates.py`).
4. Start the stack (`docker compose -f docker-compose.local.yml up --build`).
5. Run integration validation (`SKIP_JEST=1 npm run test:integration --prefix services`).

`scripts/prepare-local-env.sh` (upcoming) will encapsulate these steps. Document any additional prerequisites or manual gaps in docs so the script can cover them. Once live, the bootstrap section in documentation will point to a single command with optional flags for partial workflows.

## Integration Testing Expectations

- **Command:** `SKIP_JEST=1 npm run test:integration --prefix services`.
- **Baseline metrics:**
  - `cacheHitRate=1.0` reported by `hh-rerank-svc` (Redis caches warm and stable).
  - Rerank latency ≈ 0 ms (sub-millisecond) measured during tests.
- **Failure handling:**
  - If `cacheHitRate` drops, inspect Redis keys (`redis-cli --scan`), confirm embed service hydration order, and rerun warmup tasks.
  - If latency spikes, check Postgres indexes (`
\d candidate_embeddings`) and Redis connection pool saturation.
  - Persist deviations to `docs/HANDOVER.md` troubleshooting logs for operational visibility.

## Tenant Isolation & Mock Auth

- `@hh/common` Fastify hooks enforce tenant headers, JWT validation, and authorize service-to-service calls. Middleware attaches `tenantId`, `requestId`, and correlation metadata to every log entry.
- JWTs originate from the mock OAuth server locally; tokens mirror production issuer/audience claims so services exercise the same validation path.
- Redis namespaces include tenant identifiers to prevent cache poisoning. Postgres schemas isolate tenant data via composite keys and check constraints.
- Local tests rely on the Firestore emulator seeded with tenant-specific collections; reset via helper scripts before destructive integration test runs.

## Multi-Tenant Candidate Data Model

Candidates use a **shared database, shared schema** approach with multi-org visibility:

```typescript
{
  org_id: string,           // Primary org (for backward compatibility)
  org_ids: string[],        // All orgs with access to this candidate
  source_orgs: [{           // Track who added this candidate
    org_id: string,
    org_name: string,
    added_at: Timestamp,
    source: string          // "CSV Import", "Resume Upload", etc.
  }],
  canonical_email: string,  // Normalized email for deduplication
  // ...other fields
}
```

**Access Control:**
- **Ella (org_ella_main)**: Sees ALL candidates regardless of org_ids
- **Client orgs**: See only candidates where `org_ids.includes(their_org_id)`

**Deduplication:**
- Primary key: `canonical_email` (normalized, lowercase)
- When importing duplicate: `add_org` strategy adds new org to existing candidate's `org_ids[]`
- Fallback identifier when no email: `name + linkedin_url` or `name + phone`


## Observability & Troubleshooting

- **Metrics:** Scrape `/metrics` from each service. Hook into the optional `docker/prometheus` stack when deeper analysis is required.
- **Logs:** Use `docker compose logs -f <service>` to trace request flows. Look for `tenantId` and `traceId` fields to stitch cross-service operations.
- **Common issues:**
  - *Service stuck in `starting`*: Ensure dependent containers are healthy; check `depends_on` graph for missing readiness checks.
  - *Redis connection errors*: Confirm `REDIS_URL` in `.env` and that the container exposes port 6379.
  - *Firestore emulator auth failures*: The emulator requires `FIRESTORE_EMULATOR_HOST` to be set; confirm environment propagation in service `.env.local` files.
  - *Python worker timeouts*: Validate the bind mount (`scripts/`) and check `python:3.11-slim` container logs for missing dependencies. Regenerate `scripts/venv` if necessary.
  - *JWT validation errors*: Regenerate mock OAuth keys (`scripts/mock_oauth/reset_keys.sh`) and recycle services relying on cached JWKs.

## Deployment Notes

- Services build from workspace-specific Dockerfiles; CI publishes to Artifact Registry. Deployment manifests reference the same port numbers documented above.
- Cloud Run connects to Cloud SQL (pgvector), Memorystore (Redis), Firestore, Pub/Sub, and Together AI with secrets supplied via Secret Manager.
- Scheduler-driven workflows in production mirror Pub/Sub topics defined in compose; keep topic names identical to preserve local parity.

## Legacy Reference

Older Cloud Functions documentation is available for auditing purposes only. All new development should follow the Fastify architecture described in this file.
