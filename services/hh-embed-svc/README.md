# hh-embed-svc

`hh-embed-svc` is the Cloud Run embeddings service that powers tenant-scoped semantic search for the Headhunter platform. The service exposes Fastify HTTP APIs for generating embeddings, persisting vectors in Cloud SQL (pgvector), and performing similarity search with pluggable embedding providers.

## Features

- Authenticated Fastify APIs built on top of `@hh/common` (request logging, auth, tenant validation, error handling).
- Default Gemini/Vertex embedding provider with pluggable local and Together stubs.
- Tenant-isolated pgvector storage in the `search.candidate_embeddings` table backed by HNSW cosine indexing.
- Configurable similarity thresholds, query limits, and connection pooling tuned for Cloud Run.
- Dockerfile aligned with existing services for repeatable builds and deployments.

## API Endpoints

All routes require the standard authentication headers handled by `@hh/common` middleware. Tenant scoping is derived from `x-tenant-id`.

### `POST /v1/embeddings/generate`
Generate an embedding from raw text.

**Request body**
```json
{
  "text": "PostgreSQL wizard with AI pipeline experience",
  "provider": "vertex-ai"
}
```

**Response**
```json
{
  "embedding": [0.12, -0.03, ...],
  "provider": "vertex-ai",
  "model": "text-embedding-004",
  "dimensions": 768,
  "requestId": "c5e5210b-..."
}
```

### `POST /v1/embeddings/upsert`
Persist or replace a tenant-scoped embedding.

**Request body**
```json
{
  "entityId": "candidate:1234",
  "text": "Seasoned backend engineer ...",
  "metadata": {
    "title": "Senior Backend Engineer",
    "location": "São Paulo"
  },
  "chunkType": "profile"
}
```

**Response**
```json
{
  "entityId": "candidate:1234",
  "tenantId": "tenant_42",
  "vectorId": "0c4a814e-...",
  "modelVersion": "text-embedding-004",
  "chunkType": "profile",
  "dimensions": 768,
  "createdAt": "2024-05-10T15:00:00.000Z",
  "updatedAt": "2024-05-10T15:00:00.000Z",
  "requestId": "c5e5210b-..."
}
```

### `POST /v1/embeddings/query`
Run a cosine-similarity search against stored embeddings.

**Request body**
```json
{
  "query": "Go engineer with fintech background",
  "limit": 10,
  "similarityThreshold": 0.78
}
```

**Response**
```json
{
  "results": [
    {
      "entityId": "candidate:1234",
      "similarity": 0.86,
      "modelVersion": "text-embedding-004",
      "chunkType": "profile",
      "embeddingId": "0c4a814e-...",
      "updatedAt": "2024-05-10T15:12:00.000Z"
    }
  ],
  "count": 1,
  "provider": "vertex-ai",
  "model": "text-embedding-004",
  "dimensions": 768,
  "requestId": "c5e5210b-...",
  "executionMs": 142
}
```

## Configuration

Copy `.env.example` to `.env` and adjust as needed. Important variables:

| Variable | Description |
| --- | --- |
| `EMBEDDING_PROVIDER` | `vertex-ai` (default), `local`, or `together`. |
| `VERTEX_AI_MODEL` | Gemini model ID, defaults to `text-embedding-004`. |
| `GCP_PROJECT_ID` / `GCP_LOCATION` | Vertex AI project and region. |
| `PGVECTOR_HOST/PORT/...` | Connection parameters for Cloud SQL. Unix sockets are supported through standard PG env vars. |
| `PGVECTOR_HNSW_EF_SEARCH` | Optional per-session search depth for HNSW queries (`SET hnsw.ef_search`). Leave unset to rely on pgvector defaults. |
| `PGVECTOR_POOL_MAX` | Maximum pooled connections (tune for Cloud Run concurrency). |
| `EMBEDDING_SIMILARITY_THRESHOLD` | Default cosine similarity threshold for searches. |
| `EMBEDDING_QUERY_LIMIT` | Maximum number of matches returned per query. |
| `ENABLE_AUTO_MIGRATE` | When `true`, the service creates/updates schema objects on startup (local/dev only). Defaults to `false`; production should run migrations manually. |

### Schema Management

- The embeddings table enforces `vector(<EMBEDDING_DIMENSIONS>)` so update migrations alongside any dimensionality change.
- Production runs should leave `ENABLE_AUTO_MIGRATE=false` and apply SQL migrations (see `scripts/pgvector_schema.sql`) during deploys.
- Local development can set `ENABLE_AUTO_MIGRATE=true` to bootstrap the schema; in production the service will verify that the schema, extensions, and `candidate_embeddings_embedding_hnsw_idx` are present.
- The expected ANN index is `USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)`. Adjust query recall using `PGVECTOR_HNSW_EF_SEARCH`.

The service inherits logging, auth, and runtime settings from `@hh/common` (`SERVICE_NAME`, `LOG_LEVEL`, etc.).

## Local Development

1. Install dependencies from the monorepo root:
   ```bash
   npm install --workspaces
   ```
2. Export required environment variables or create `services/hh-embed-svc/.env`.
3. Start the service:
   ```bash
   cd services/hh-embed-svc
   npm run dev
   ```
4. Call endpoints with an emulator token and `x-tenant-id` header. Use `curl` or the API gateway.

### Testing

Unit tests are wired through `npm test` (Vitest). Add coverage alongside new logic and keep parity with Python integration tests under `tests/`.

### Linting & Type Checking

Run ESLint and TypeScript checks from the service directory:

```bash
npm run lint
npm run typecheck
```

## Deployment

1. Build the workspace:
   ```bash
   npm run build --workspaces
   ```
2. Build and push the Docker image:
   ```bash
   gcloud builds submit --config cloudbuild.yaml --substitutions _SERVICE=hh-embed-svc
   ```
3. Deploy to Cloud Run:
   ```bash
   gcloud run deploy hh-embed-svc \
     --image gcr.io/$PROJECT_ID/hh-embed-svc:latest \
     --region $REGION \
     --set-env-vars "SERVICE_NAME=hh-embed-svc,EMBEDDING_PROVIDER=vertex-ai,..."
   ```

Ensure the Cloud SQL instance is reachable (VPC connector or Cloud SQL proxy) and that Vertex AI credentials are available via workload identity or service account.

## Troubleshooting

- **401/403 responses**: check that the Authorization header is valid and the tenant exists.
- **`Embedding dimensionality mismatch`**: verify the client-supplied vector length matches the provider’s configured dimensions.
- **Database connection errors**: confirm Cloud SQL proxy connectivity and that `PGVECTOR_*` env vars are correct.
- **Slow queries**: tune `EMBEDDING_QUERY_LIMIT`, `EMBEDDING_SIMILARITY_THRESHOLD`, and `PGVECTOR_HNSW_EF_SEARCH` (higher = more accurate) to balance recall and latency.

## Related Resources

- [`functions/src/vector-search.ts`](../../functions/src/vector-search.ts) for the legacy implementation that inspired this service.
- [`@hh/common`](../common) shared server utilities and middleware.
- `docs/TDD_PROTOCOL.md` for the team’s testing expectations.
