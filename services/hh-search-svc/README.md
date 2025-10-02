# hh-search-svc

`hh-search-svc` is the Headhunter hybrid search Cloud Run service. It combines full-text search (FTS) and vector similarity powered by pgvector, enriches responses with skill-alignment heuristics, and exposes a Fastify API aligned with the platform service conventions.

## Features
- `POST /v1/search/hybrid` – hybrid retrieval with tenant-aware ranking and match rationales.
- Redis-backed response caching with tenant-prefixed keys (`hh:hybrid:{tenant}:{cacheKey}`).
- Integration with `hh-embed-svc` for query embeddings.
- Health/readiness endpoints lighting up pgvector, Redis, and embedding dependencies.
- Structured logging, authentication, and tenant validation via `@hh/common`.

## Getting Started

```bash
cd services
npm install --workspaces
npm run build --workspace @hh/hh-search-svc
npm run dev --workspace @hh/hh-search-svc
```

Copy `.env.example` to `.env` (or export variables) before running locally.

## Configuration
Key environment variables (see `.env.example` for exhaustive list):
- `PGVECTOR_*` – Postgres connectivity and pooling.
- `REDIS_*` – cache endpoint and credentials.
- `EMBED_SERVICE_URL` – base URL for `hh-embed-svc`.
- `SEARCH_*` – knobs for ranking weights, cache TTL, batching.

## Development Workflow
1. Install dependencies (`npm install --workspaces`).
2. Start a local Postgres/pgvector instance and Redis.
3. Run `npm run dev --workspace @hh/hh-search-svc` to start Fastify in watch mode.
4. Execute tests with `npm test --workspace @hh/hh-search-svc`.
5. Publish API changes by updating schemas in `src/schemas.ts` and documenting contract updates here.

## API Overview
A minimal hybrid search request:

```json
{
  "query": "Senior data engineer",
  "jdHash": "d41d8cd98f00b204e9800998ecf8427e",
  "limit": 20,
  "filters": {
    "location": ["Brazil"],
    "skills": ["Python", "Spark"]
  }
}
```

Successful responses include ranked candidates, rationale metadata, cache flags, and timing diagnostics. See `src/schemas.ts` for the OpenAPI-aligned schema.

## Deployment
The Dockerfile follows the shared Cloud Run pattern:

```bash
cd services
gcloud builds submit --config cloudbuild.yaml --substitutions _SERVICE=hh-search-svc
```

Ensure staging and production configs supply the correct `EMBED_SERVICE_URL`, pgvector credentials, and Redis hosts. Rollouts should follow the canary policy in the PRD.

## Troubleshooting
- Health endpoint (`/health`) returns non-200 when Redis or pgvector degrade.
- Enable debug logs via `LOG_LEVEL=debug`.
- Use `SEARCH_CACHE_PURGE=true` to disable Redis caching locally.
- Verify embeddings service reachability with `curl $EMBED_SERVICE_URL/health`.

Refer to `docs/RUNBOOK.md` for operational runbooks.
