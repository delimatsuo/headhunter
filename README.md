# Headhunter - AI-Powered Recruitment Analytics

> Canonical repository path: `/Volumes/Extreme Pro/myprojects/headhunter`. Older copies under `/Users/delimatsuo/Documents/Coding/headhunter` are deprecated and read-only.

## Fastify Service Mesh Overview

The production stack runs as eight coordinated Fastify HTTP services. Source lives under `services/` as npm workspaces (see `services/package.json` for the workspace manifest).

| Service | Port | Primary responsibilities |
| --- | --- | --- |
| `hh-embed-svc` | 7101 | Normalizes raw candidate data, requests embedding jobs, and hands off batches to enrichment for long-lived processing.
| `hh-search-svc` | 7102 | Handles multi-tenant search APIs, composes Postgres pgvector recalls with deterministic filters, and orchestrates rerank callbacks.
| `hh-rerank-svc` | 7103 | Maintains Redis-backed scoring caches, enforces `cacheHitRate=1.0` baseline during integration, and returns near-zero latency rerank payloads.
| `hh-evidence-svc` | 7104 | Aggregates provenance artifacts and exposes evidence APIs consumed by recruiter experiences.
| `hh-eco-svc` | 7105 | Manages ecosystem (ECO) data pipelines, occupation normalization, and document templates.
| `hh-msgs-svc` | 7106 | Processes outbound notifications, queue fan-out, and Pub/Sub emulator bridging for local development.
| `hh-admin-svc` | 7107 | Hosts scheduler and tenant onboarding endpoints, including policy enforcement and guardrail jobs.
| `hh-enrich-svc` | 7108 | Coordinates long-running enrichment flows, calls out to Python workers via bind-mounted `scripts/` pipelines, and persists derived attributes.

Each service exposes `/health` and `/metrics` endpoints and shares middleware from `@hh/common` for tenant validation, structured logging, and error semantics.

## Shared Infrastructure

`docker-compose.local.yml` stands up application services and infrastructure sidecars. Local parity mirrors production resources:

- **Postgres (ankane/pgvector:v0.5.1)** – master store for deterministic search, embeddings, and transactional data.
- **Redis (redis:7-alpine)** – request cache, idempotency locks, rerank scoring store.
- **Firestore emulator + Pub/Sub emulator** – gcloud containers matching production GCP services.
- **Mock OAuth & Together AI services** – emulate auth/token issuance and LLM API contracts for offline runs.
- **Python worker bind mounts** – `scripts/` directory is mounted into enrichment containers to execute auxiliary jobs.

Service dependencies and startup order follow the `depends_on` graph declared in `docker-compose.local.yml`; Fastify services wait for infrastructure health checks before accepting traffic.

## Architecture Diagram

```
                           ┌────────────────────┐
                           │  Gateway / BFF     │
                           │  (Fastify proxy)   │
                           └─────────┬──────────┘
                                     │ JWT + tenant middleware
                ┌────────────────────┼────────────────────┐
                │                    │                    │
        ┌───────▼──────┐     ┌───────▼──────┐     ┌───────▼──────┐
        │ hh-search     │     │ hh-embed     │     │ hh-admin     │
        │ svc :7102     │     │ svc :7101    │     │ svc :7107    │
        └───────┬──────┘     └───────┬──────┘     └───────┬──────┘
                │                    │                    │
        ┌───────▼──────┐     ┌───────▼──────┐     ┌───────▼──────┐
        │ hh-rerank     │     │ hh-enrich    │     │ hh-msgs      │
        │ svc :7103     │     │ svc :7108    │     │ svc :7106    │
        └───────┬──────┘     └───────┬──────┘     └───────┬──────┘
                │                    │                    │
        ┌───────▼──────┐     ┌───────▼──────┐     ┌───────▼──────┐
        │ hh-evidence   │     │ hh-eco       │     │ Shared infra │
        │ svc :7104     │     │ svc :7105    │     │ (Redis,      │
        └──────────────┘     └──────────────┘     │ Postgres,    │
                                                  │ Firestore,   │
                                                  │ Pub/Sub,     │
                                                  │ Mock APIs)   │
                                                  └──────────────┘
```

## Prerequisites

### GCP Infrastructure
Before running services locally or deploying to production, provision the required GCP infrastructure:

- **Google Cloud CLI** (`gcloud`) installed and authenticated
- **Appropriate IAM permissions** (Owner or Editor role on the project)
- **Secret values prepared** (API keys, passwords - see Secret Prerequisites below)

### Local Development
- **Docker Desktop** installed and running
- **Node.js 20+** for Fastify services
- **Python 3.11+** for enrichment workers

## GCP Infrastructure Provisioning

Provision all required GCP resources (Cloud SQL, Redis, VPC, Pub/Sub, Cloud Storage, Firestore, Secret Manager):

```bash
# Provision all infrastructure with a single command
./scripts/provision-gcp-infrastructure.sh --project-id headhunter-ai-0088

# Or dry run first to see what will be provisioned
./scripts/provision-gcp-infrastructure.sh --project-id headhunter-ai-0088 --dry-run
```

**What gets provisioned:**
- Cloud SQL (PostgreSQL + pgvector extension)
- Redis (MemoryStore)
- VPC networking with NAT and connectors
- Pub/Sub topics and subscriptions
- Cloud Storage buckets
- Firestore database (native mode)
- Secret Manager secrets (with placeholders)

**After provisioning:**
1. Review provisioned resources: [`docs/infrastructure-notes.md`](docs/infrastructure-notes.md)
2. Populate secrets with real values (see Secret Prerequisites below)
3. Configure local environment using connection strings from infrastructure notes

**Detailed instructions:** See [`docs/gcp-infrastructure-setup.md`](docs/gcp-infrastructure-setup.md)

### Secret Prerequisites

Before provisioning (or after, if using placeholder secrets initially):

```bash
# Validate secret prerequisites
./scripts/validate-secret-prerequisites.sh --check-only

# Generate a template for secret values
./scripts/validate-secret-prerequisites.sh --generate-template

# Set required secrets as environment variables (example)
export HH_SECRET_DB_PRIMARY_PASSWORD="$(openssl rand -base64 32)"
export HH_SECRET_TOGETHER_AI_API_KEY="your-together-api-key"
export HH_SECRET_OAUTH_CLIENT_CREDENTIALS='{"client_id":"...","client_secret":"..."}'
export HH_SECRET_STORAGE_SIGNER_KEY="$(openssl rand -base64 32)"
```

After infrastructure is provisioned, populate secrets in Secret Manager:

```bash
# Populate secrets in Secret Manager
echo -n "YOUR_SECURE_PASSWORD" | gcloud secrets versions add db-primary-password --data-file=-
echo -n "YOUR_TOGETHER_API_KEY" | gcloud secrets versions add together-api-key --data-file=-
```

## Local Bootstrap Procedure

1. **Provision GCP infrastructure** – Follow GCP Infrastructure Provisioning section above, then review [`docs/infrastructure-notes.md`](docs/infrastructure-notes.md) for connection strings.
2. **Install workspaces** – From `/Volumes/Extreme Pro/myprojects/headhunter`, run `npm install --workspaces --prefix services` to hydrate all Fastify packages defined in `services/package.json`.
3. **Environment preparation** – Copy `.env.example` to `.env` and provide keys for Together AI, Firebase Admin, and any provider-specific overrides referenced by service `.env.local` files. Use connection strings from [`docs/infrastructure-notes.md`](docs/infrastructure-notes.md).
4. **Seed tenant credentials** – Use existing helpers (e.g., `scripts/manage_tenant_credentials.sh`). Record any manual steps that `scripts/prepare-local-env.sh` should absorb when it lands.
5. **Launch the stack** – `docker compose -f docker-compose.local.yml up --build`. Wait for service logs confirming `/health` success across ports 7101–7108 and supporting infrastructure.
6. **Run integration validation** – Execute `SKIP_JEST=1 npm run test:integration --prefix services`. The baseline is `cacheHitRate=1.0` with rerank latency ≈ 0 ms. Investigate Redis metrics and rerank logs if either metric regresses.
7. **Optional front-end** – Start the UI worktree (`headhunter-ui/`) or additional tooling after the Fastify mesh is healthy.

📌 **Upcoming automation:** `scripts/prepare-local-env.sh` will consolidate steps 2–6 (install, env scaffolding, credential seeding, compose bootstrap, and integration smoke test). Keep this checklist current and annotate remaining manual steps until the script ships.

## Integration Baseline & Observability

- **Health checks:** `curl http://localhost:710X/health` for each service. Expect `200 OK` with `{"status":"ok"}`.
- **Metrics:** Prometheus-style metrics live at `/metrics`. Redis cache efficiency and rerank latency gauges are exported by `hh-rerank-svc`.
- **Logs:** Structured JSON logs include `tenantId`, `requestId`, and `traceId`. In development, logs stream to stdout; tail targeted services with `docker compose logs -f hh-rerank-svc` etc.
- **Regression actions:**
  - `cacheHitRate < 1.0` → flush and warm Redis, verify embedding ingestion ordering.
  - `rerankLatency > 5ms` → inspect Redis connection pool and Postgres index usage.

## Developer Workflow Notes

- Services share utilities through `@hh/common`; contribute shared logic there to keep parity across the mesh.
- Python enrichment helpers under `scripts/` are bind-mounted into `hh-enrich-svc` during local runs; keep dependencies declared in `scripts/requirements.txt`.
- Update documentation when adjusting ports, dependencies, or service responsibilities so `docker-compose.local.yml` and this README stay aligned.

## Production Deployment

- Quick start: `./scripts/deploy-production.sh --project-id headhunter-ai-0088`
- Detailed procedures are documented in [`docs/PRODUCTION_DEPLOYMENT_GUIDE.md`](docs/PRODUCTION_DEPLOYMENT_GUIDE.md)
- Deployment artifacts (manifests, logs, reports) are written to `.deployment/` and ignored from git
- A comprehensive deployment report is generated automatically at `docs/deployment-report-*.md`; review it for SLA evidence, blockers, and sign-off before closing the release.

## Monitoring

- Run `./scripts/setup-monitoring-and-alerting.sh --project-id headhunter-ai-0088 --notification-channels <channels>` after each production deployment to reconcile dashboards, alert policies, uptime checks, and cost tracking.
- Review dashboard URLs and alert resource IDs in `.monitoring/setup-*/monitoring-manifest.json`; full catalog lives in [`docs/MONITORING_RUNBOOK.md`](docs/MONITORING_RUNBOOK.md).
- Confirm no SEV-1/SEV-2 alerts remain active before closing a deployment.

## Load Testing

- Execute `./scripts/run-post-deployment-load-tests.sh --gateway-endpoint https://<gateway-host> --tenant-id tenant-alpha` immediately after smoke tests to validate SLA compliance.
- Scenario logs, aggregated metrics, and SLA validation live under `.deployment/load-tests/post-deploy-*/`.
- Use load test outputs and dashboards to document performance in the deployment report.

## Deployment Workflow

1. **Provision infrastructure** – `./scripts/provision-gcp-infrastructure.sh --project-id headhunter-ai-0088`
2. **Populate secrets** – Load production values into Secret Manager
3. **Orchestrated deployment** – `./scripts/deploy-production.sh --project-id headhunter-ai-0088`
4. **Set up monitoring & alerting** – `./scripts/setup-monitoring-and-alerting.sh --project-id headhunter-ai-0088`
5. **Run post-deployment load tests** – `./scripts/run-post-deployment-load-tests.sh --gateway-endpoint https://<gateway-host>`
6. **Generate deployment report** – Automatically triggered by the deploy script or run `./scripts/generate-deployment-report.sh`
7. **Review dashboards & reports** – Validate readiness (`./scripts/validate-deployment-readiness.sh`), confirm SLO compliance, archive manifests and load test summaries

## Key Documentation

- [`ARCHITECTURE.md`](ARCHITECTURE.md) – in-depth architecture, dependency graph, and bootstrap context
- [`docs/PRODUCTION_DEPLOYMENT_GUIDE.md`](docs/PRODUCTION_DEPLOYMENT_GUIDE.md) – end-to-end production deployment runbook
- [`docs/HANDOVER.md`](docs/HANDOVER.md) – operator and incident response handbook
- [`docs/gcp-infrastructure-setup.md`](docs/gcp-infrastructure-setup.md) – infrastructure provisioning checklist
- [`docs/infrastructure-notes.md`](docs/infrastructure-notes.md) – auto-generated infrastructure resource details (created after provisioning)
- [`docs/deployment-report-*.md`](docs) – auto-generated deployment reports (`scripts/generate-deployment-report.sh`)
- [`scripts/validate-deployment-readiness.sh`](scripts/validate-deployment-readiness.sh) – readiness validation checklist and JSON report generator
- [`.taskmaster/docs/prd.txt`](.taskmaster/docs/prd.txt) – authoritative PRD (this `PRD.md` exists as a historical snapshot; see notice within)
- [`docs/MONITORING_RUNBOOK.md`](docs/MONITORING_RUNBOOK.md) – monitoring and alerting operational guide
- `.monitoring/setup-*/monitoring-manifest.json` – dashboard, alert, uptime, and cost tracking inventory
- `.deployment/load-tests/post-deploy-*/load-test-report.md` – post-deployment load test summaries

## Deployment Artifacts

Deployment scripts create a workspace-local `.deployment/` directory with subfolders for build logs, deployment manifests, smoke test reports, and gateway snapshots. The folder is gitignored; archive or publish artifacts externally if they must persist beyond a single deployment.

## Legacy Reference (Cloud Functions Era)

The Cloud Functions implementation is fully retired but retained for historical awareness. Do **not** base new work on this section.

- **LLM processing (historical):** single-pass Together AI (Qwen 2.5 32B) pipelines generated structured profiles, evidence, and analysis artifacts.
- **Storage:** Firestore plus planned pgvector ingestion; Firebase Authentication gated access.
- **Processing scripts:** `scripts/performance_test_suite.py`, `scripts/prd_compliant_validation.py`, and `scripts/upload_candidates.py` orchestrated legacy ingestion flows.
- **Frontend:** React SPA (Firebase Hosting) with Candidate Page deep view and admin callables for allowed users.
- **Security:** Firebase Auth + Secret Manager; no mock fallbacks in prod/staging.

Historic deployment steps (Cloud Run worker, Firebase Functions) remain available in git history if needed for auditing.
