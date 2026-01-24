# External Integrations

**Analysis Date:** 2026-01-24

## APIs & External Services

**AI Processing - Reranking:**
- Together AI (Qwen 2.5-32B-Instruct)
  - What it's used for: Candidate profile reranking, intelligent scoring with reasons
  - SDK/Client: `together` Python package (scripts/), `axios` for HTTP calls (hh-rerank-svc)
  - Auth: `TOGETHER_API_KEY` environment variable
  - Fallback: Gemini API via `@google/generative-ai` when Together times out
  - Base URL: `process.env.TOGETHER_API_BASE_URL` (default: https://api.together.xyz/v1)
  - Model override: `process.env.TOGETHER_MODEL` (default: qwen2.5-32b-instruct)
  - Circuit breaker: Failures threshold `TOGETHER_CB_FAILURES` (4), cooldown `TOGETHER_CB_COOLDOWN_MS` (60s)

**AI Processing - Embeddings:**
- Google Gemini API (`gemini-embedding-001` or `gemini-2.5-flash`)
  - What it's used for: Text embeddings for vector search in pgvector
  - SDK/Client: `@google-cloud/aiplatform` (production), `@google/generative-ai` (functions)
  - Location: `process.env.GEMINI_LOCATION` (default: us-central1)
  - Project: `process.env.GEMINI_PROJECT_ID` (default: headhunter-ai-0088)
  - Timeout: `GEMINI_TIMEOUT_MS` (5000ms), retries: 2

- Vertex AI (text-embedding-004)
  - What it's used for: Alternative embeddings provider (fallback)
  - SDK/Client: `@google-cloud/aiplatform` (services), `@google-cloud/vertexai` (functions)
  - Location: `VERTEX_AI_LOCATION` env var (us-central1)
  - Used by: `hh-embed-svc` when configured

**Profile Enrichment:**
- Together AI Llama models (via scripts)
  - What it's used for: Career trajectory analysis, skill assessment, recruiter insights
  - Scripts: `scripts/together_ai_processor.py`, `scripts/intelligent_skill_processor.py`
  - Candidates enriched with structured metadata (leadership_scope, company_pedigree, etc.)

## Data Storage

**Databases:**
- PostgreSQL + pgvector (Cloud SQL production, Docker local)
  - Host: `process.env.PGVECTOR_HOST` (localhost:5432 local, Cloud SQL in production)
  - User/Password: `PGVECTOR_USER`, `PGVECTOR_PASSWORD`
  - Database: `PGVECTOR_DATABASE` (default: headhunter)
  - Connection: `pg` npm package with connection pooling
  - Schemas:
    - `search` - Candidate embeddings, profiles, search indices
    - `public` - System tables
    - `sourcing` - Sourcing pipeline tables
  - Tables:
    - `candidate_embeddings` - Vector embeddings (1536 dims from Gemini)
    - `candidate_profiles` - Profile metadata for search
    - Messages, job postings, company data in hh-msgs-svc schema
  - SSL: `PGVECTOR_SSL` (true in production, false locally)
  - Pool: `PGVECTOR_POOL_MAX` (10), `PGVECTOR_POOL_MIN` (0)

**Firestore (Operational Data):**
- Google Cloud Firestore (emulator locally)
  - Project: `FIREBASE_PROJECT_ID` or `GOOGLE_CLOUD_PROJECT`
  - Emulator: `FIRESTORE_EMULATOR_HOST` (localhost:8080 local, real Firestore in production)
  - Client: `@google-cloud/firestore` (Node.js), `google-cloud-firestore` (Python)
  - Collections:
    - `profiles` - Candidate profiles with enrichment metadata
    - `tenants` - Multi-tenant configuration
    - `evidence` - Provenance and evidence artifacts
    - `audit_logs` - Change tracking
  - Real-time updates: Yes, subscriptions used in hh-evidence-svc

**File Storage:**
- Google Cloud Storage (production)
  - Bucket naming: Per-tenant organization
  - Access: `@google-cloud/storage` npm package
  - Used for: Resume storage, document uploads (handled by hh-enrich-svc)
- Local filesystem: Development only

**Caching:**
- Redis (Cloud Memorystore production, redis:7-alpine Docker local)
  - Host: `process.env.REDIS_HOST` (localhost:6379 local)
  - Connection: `ioredis` npm package with TLS support
  - Keyspaces:
    - `hh:hybrid` - Search result caching (hh-search-svc)
    - `hh:rerank` - Rerank cache for deterministic scoring (hh-rerank-svc)
    - `hh:evidence` - Evidence artifact caching (hh-evidence-svc)
    - `hh:msgs` - Messaging service cache (hh-msgs-svc)
  - TTL: `CACHE_TTL_SECONDS` (180-300s typical)
  - TLS: `REDIS_TLS` (true in production, false locally)
  - Auth: `REDIS_PASSWORD` env var

## Authentication & Identity

**Auth Provider - Multi-mode:**
- Mode: `AUTH_MODE` env var (firebase | gateway | hybrid | none)
  - `firebase` - Firebase Authentication tokens only
  - `gateway` - API Gateway tokens only (recommended production)
  - `hybrid` - Accept both Firebase and gateway tokens (default)
  - `none` - No application-level auth (requires API Gateway protection)

**Gateway Authentication:**
- Supported: OpenID Connect compatible issuers
- Configuration: `ALLOWED_TOKEN_ISSUERS` (comma-separated issuer URIs)
- Audience validation: `GATEWAY_AUDIENCE` required for gateway tokens
- JWKS endpoint: `ISSUER_CONFIGS` or auto-resolved from issuer .well-known/jwks.json
- Token clock skew: `TOKEN_CLOCK_SKEW_SECONDS` (30s default)

**Firebase Authentication:**
- Project: `FIREBASE_PROJECT_ID`
- Issuer: `https://securetoken.google.com/{PROJECT_ID}`
- Token verification: Via `firebase-admin` SDK
- Revocation checking: `AUTH_CHECK_REVOKED` (true by default)
- Service account: Loaded from `GOOGLE_APPLICATION_CREDENTIALS` or local `service-account.json`

**JWT Validation:**
- Library: `jose` for gateway tokens, `firebase-admin` for Firebase tokens
- Token caching: `ENABLE_TOKEN_CACHE` (true), TTL: `TOKEN_CACHE_TTL_SECONDS` (300s)
- Validation endpoint: `/auth/validate` in hh-admin-svc

**Local Development Mock OAuth:**
- Docker service: `mock-oauth:8081` in docker-compose.local.yml
- Issues: Test JWTs for all tenants (tenant-alpha, tenant-beta, tenant-gamma, tenant-delta)
- Audience: `headhunter-local`

## Monitoring & Observability

**Error Tracking:**
- Sentry - Not detected (logs only)
- Manual tracking: Error logs to stdout/Cloud Logging

**Logs:**
- Local: Structured JSON logs to stdout via `pino` logger
- Production: Google Cloud Logging (automatic from Cloud Run)
- Log level: `LOG_LEVEL` env var (info, debug, error)
- Request logging: `ENABLE_REQUEST_LOGGING` (true enables detailed request/response logging)
- Fields: `tenantId`, `requestId`, `traceId`, `userId` in all logs

**Tracing:**
- Cloud Trace integration: Automatic via Cloud Run
- Header propagation: `X-Cloud-Trace-Context` header (configurable via `TRACE_HEADER`)
- Trace project: `TRACE_PROJECT_ID` or inferred from `FIREBASE_PROJECT_ID`

**Metrics:**
- Prometheus-style export at `/metrics` endpoint (services)
- Pino logger metrics integration
- Custom metrics exported from:
  - `hh-rerank-svc`: `rerank_cache_hit_rate` (target: 1.0), rerank latency histogram
  - `hh-search-svc`: Hybrid search latency, vector vs text weight analysis
  - All services: Request latency, error rate, connection pool status

**Health Checks:**
- Endpoint: `/health` on all services
- Status: Simple 200 OK for container orchestration
- Liveness: HTTP GET, 30s interval
- Readiness: Service-specific dependency validation

## CI/CD & Deployment

**Hosting:**
- Google Cloud Run (serverless container orchestration, production)
- Docker containers locally (docker-compose.local.yml for development)
- Services deployed independently:
  - `hh-embed-svc` on Cloud Run (port 7101 local)
  - `hh-search-svc` on Cloud Run (port 7102 local)
  - `hh-rerank-svc` on Cloud Run (port 7103 local)
  - `hh-evidence-svc` on Cloud Run (port 7104 local)
  - `hh-eco-svc` on Cloud Run (port 7105 local)
  - `hh-admin-svc` on Cloud Run (port 7106 local)
  - `hh-msgs-svc` on Cloud Run (port 7107 local)
  - `hh-enrich-svc` on Cloud Run (port 7108 local)
  - React UI on Cloud Storage + Cloud CDN / Cloud Run

**CI Pipeline:**
- Git repository: Main branch protected
- Cloud Build (GCP)
  - Build triggers on commits
  - Docker image build per service
  - Push to Artifact Registry (`us-central1-docker.pkg.dev/headhunter-ai-0088/...`)
- Deployment scripts: `scripts/deploy-cloud-run-services.sh`, `scripts/deploy-production.sh`

**Infrastructure:**
- Cloud SQL PostgreSQL (managed database with pgvector)
- Cloud Memorystore Redis (managed cache)
- Cloud Pub/Sub (async messaging)
- Cloud Scheduler (job orchestration)
- API Gateway (external API frontend with auth)
- Cloud Firestore (operational data)
- Service Accounts with granular IAM roles per service

## Environment Configuration

**Required env vars (Common):**
- `FIREBASE_PROJECT_ID` - GCP project ID (headhunter-ai-0088 production)
- `NODE_ENV` - production | development
- `REDIS_HOST`, `REDIS_PORT` - Redis connection
- `FIRESTORE_EMULATOR_HOST` - Local Firestore (localhost:8080 development only)
- `ALLOWED_TOKEN_ISSUERS` - Comma-separated OAuth issuer URIs

**Required env vars (Search/Embed/Rerank):**
- `PGVECTOR_HOST`, `PGVECTOR_USER`, `PGVECTOR_PASSWORD` - PostgreSQL connection
- `TOGETHER_API_KEY` - Together AI authentication
- `EMBED_SERVICE_URL`, `RERANK_SERVICE_URL` - Inter-service URLs

**Secrets location:**
- Production: Google Secret Manager
  - Secret names: `HH_SECRET_*` (e.g., `HH_SECRET_TOGETHER_AI_API_KEY`)
  - Retrieved at runtime via Secret Manager client
- Local development: `.env.local` files (gitignored)
- CI/CD: GitHub Actions / Cloud Build secrets

**Feature Flags:**
- `ENABLE_RERANK` - Enable/disable reranking (default: true)
- `ENABLE_AUTO_MIGRATE` - Auto-migrate pgvector schema (default: false)
- `SEARCH_FIRESTORE_FALLBACK` - Fall back to Firestore if pgvector fails (default: false)
- `SEARCH_CACHE_PURGE` - Disable search cache (default: false)
- `TOGETHER_ENABLE`, `GEMINI_ENABLE` - Enable AI models (default: true)

## Webhooks & Callbacks

**Incoming:**
- Pub/Sub webhooks from Cloud Scheduler (hh-admin-svc receives refresh triggers)
- HTTP endpoints for external job submissions (hh-enrich-svc accepts enrichment jobs)
- Firestore changestream triggers (internal to Firestore emulator)

**Outgoing:**
- Cloud Scheduler push notifications to Cloud Run services (for job distribution)
- Pub/Sub publications from hh-admin-svc to trigger enrichment workflows
- Webhook calls to external candidate data sources (LinkedIn API, company enrichment services)
  - Scripts: `scripts/apify_linkedin_pipeline.py`, `scripts/company_enrichment_pipeline.py`
  - Handled via `httpx`, `aiohttp` async clients

**Event Streams:**
- Pub/Sub topics managed by hh-admin-svc:
  - `projects/{PROJECT_ID}/topics/hh-enrich-jobs`
  - `projects/{PROJECT_ID}/topics/hh-candidate-updates`
- Subscriptions: Cloud Run services subscribed to relevant topics
- Emulator: `pubsub-emulator:8681` in docker-compose.local.yml

---

*Integration audit: 2026-01-24*
