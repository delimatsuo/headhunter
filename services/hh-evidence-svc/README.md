# hh-evidence-svc

The **hh-evidence-svc** provides a tenant-aware REST API for retrieving AI-generated candidate evidence sections. The service enforces Firebase authentication, tenant validation, and Redis-backed caching to guarantee consistent performance when serving evidence analysis to recruiter-facing applications.

## Endpoints

### `GET /v1/evidence/{candidateId}`
Retrieve normalized evidence sections for a candidate.

| Parameter | Type | Description |
|-----------|------|-------------|
| `candidateId` | path | Candidate identifier scoped to the tenant. |
| `sections` | query | Optional comma-separated list of section ids to include. Defaults to all allowed sections. |

**Successful Response**
```json
{
  "sections": {
    "skills_analysis": {
      "id": "skills_analysis",
      "title": "Skills Analysis",
      "summary": "Candidate excels in ...",
      "highlights": ["7+ years in Java", "AWS certified"],
      "score": 0.92,
      "confidence": 0.88,
      "lastUpdated": "2024-04-01T12:00:00Z"
    }
  },
  "metadata": {
    "candidateId": "cand_123",
    "orgId": "tenant_abc",
    "locale": "pt-BR",
    "generatedAt": "2024-04-01T11:59:30Z",
    "redacted": false,
    "sectionsAvailable": ["skills_analysis"],
    "cacheHit": false
  }
}
```

**Error Codes**
- `400 bad_request` – Missing tenant context or unknown section identifiers.
- `401 unauthorized` – Invalid Firebase credentials.
- `403 forbidden` – Tenant validation failed.
- `404 not_found` – Candidate evidence missing for the tenant.
- `503 service_unavailable` – Dependencies degraded (Redis or Firestore).

### Health Checks
- `GET /health` – Returns component status for Firestore and Redis with HTTP `503` when degraded.
- `GET /ready` – Provided by the shared Fastify bootstrap.

## Data Model

Evidence documents reside in the Firestore collection defined by `EVIDENCE_CANDIDATES_COLLECTION` (defaults to `candidates`). Each document must include:

- `candidate_id` and tenant-bound `org_id` fields.
- `analysis` map with section identifiers (e.g. `skills_analysis`, `experience_analysis`).
- Optional evidence metadata block:
  ```json
  "metadata": {
    "locale": "pt-BR",
    "version": "2024.04.01",
    "generated_at": "2024-04-01T11:59:30Z",
    "restricted_sections": ["compensation_analysis"],
    "allowed_sections": ["skills_analysis", "experience_analysis"]
  }
  ```

The service removes restricted sections automatically when `EVIDENCE_REDACT_RESTRICTED` is enabled (default).

Firestore queries project only the configured fields to limit payload size; keep `candidate_id` and `org_id` in the projection list so tenant scoping and response metadata remain available.

## Caching Strategy

- Redis keys follow `hh:evidence:{tenantId}:{candidateId}`.
- Cached payloads include timestamps for proactive eviction and stale detection.
- After TTL expiry the service returns the cached payload immediately while asynchronously refreshing it (debounced per candidate) to honour the stale-while-revalidate window.
- `EVIDENCE_CACHE_TTL_SECONDS` controls freshness; `EVIDENCE_CACHE_SWR_SECONDS` keeps entries around for background refresh.
- Set `EVIDENCE_CACHE_DISABLED=true` to bypass Redis (useful for debugging).

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `EVIDENCE_REDIS_HOST` | inherited | Redis host (comma-separated when using cluster). |
| `EVIDENCE_REDIS_PORT` | inherited | Redis port number. |
| `EVIDENCE_REDIS_PASSWORD` | `undefined` | Optional Redis password. |
| `EVIDENCE_REDIS_TLS` | `false` | Enables TLS when `true`. |
| `EVIDENCE_REDIS_PREFIX` | `hh:evidence` | Cache key prefix. |
| `EVIDENCE_CACHE_TTL_SECONDS` | `300` | Primary cache TTL. |
| `EVIDENCE_CACHE_SWR_SECONDS` | `120` | Stale-while-revalidate extension. |
| `EVIDENCE_CACHE_DISABLED` | `false` | Disable caching entirely. |
| `EVIDENCE_CANDIDATES_COLLECTION` | `candidates` | Firestore collection for evidence documents. |
| `EVIDENCE_ORG_FIELD` | `org_id` | Firestore field storing the tenant id. |
| `EVIDENCE_FIELD` | `analysis` | Field containing section data. |
| `EVIDENCE_FIRESTORE_PROJECTIONS` | preset list | Firestore field projections applied to reads (must include `candidate_id` and `org_id`). |
| `EVIDENCE_ALLOWED_SECTIONS` | preset list | Comma-separated section ids exposed via the API. |
| `EVIDENCE_MAX_SECTIONS` | `8` | Hard cap on sections returned per request. |
| `EVIDENCE_MAX_RESPONSE_KB` | `256` | Maximum serialized payload size. |
| `EVIDENCE_DEFAULT_LOCALE` | `pt-BR` | Locale applied when document metadata lacks locale. |
| `EVIDENCE_REDACT_RESTRICTED` | `true` | Remove sections not explicitly permitted. |

Set Firestore project context using the shared variables (`FIREBASE_PROJECT_ID`, `FIREBASE_EMULATOR_HOST`, etc.) described in `services/common/README.md`.

## Local Development

```bash
cd services
npm install
cd hh-evidence-svc
cp .env.example .env
npm run dev
```

The dev command launches a Fastify server with live TypeScript transpilation. Ensure that:

1. Firebase emulators are running (`firebase emulators:start --only firestore`).
2. Redis is accessible locally (e.g. `redis-server`).
3. Authentication headers (`Authorization: Bearer <token>`) include `orgId` claims matching Firestore data.

## Testing

Run unit suites with:

```bash
npm run test
```

Follow the TDD expectations in `docs/TDD_PROTOCOL.md`. Add Vitest specs under `src/__tests__/` once business logic stabilizes.

## Deployment

The provided Dockerfile builds using workspace dependencies. Deploy via Cloud Run:

```bash
gcloud builds submit --tag gcr.io/$PROJECT_ID/hh-evidence-svc
gcloud run deploy hh-evidence-svc \
  --image gcr.io/$PROJECT_ID/hh-evidence-svc \
  --set-env-vars "SERVICE_NAME=hh-evidence-svc" \
  --set-env-vars "EVIDENCE_REDIS_HOST=redis:6379" \
  --allow-unauthenticated=false
```

Ensure service-to-service authentication is configured via IAM and that Redis credentials live in Secret Manager. Rotate keys following the process documented in `docs/HANDOVER.md`.

## Troubleshooting

- **Empty responses** – Confirm Firestore documents include `analysis` data and allowed sections.
- **403 responses** – Validate that the Firebase token carries the correct `orgId` and that the organization exists.
- **Cache misses** – Check Redis connectivity (`redis-cli ping`) and ensure `EVIDENCE_CACHE_DISABLED` is not set.
- **High latency** – Tune `EVIDENCE_CACHE_TTL_SECONDS` and review Redis/Firestore health logs via `/health`.
