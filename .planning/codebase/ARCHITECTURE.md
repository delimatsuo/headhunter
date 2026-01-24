# Architecture

**Analysis Date:** 2026-01-24

## Pattern Overview

**Overall:** Microservices mesh with lazy initialization pattern

**Key Characteristics:**
- Eight independent Fastify services (ports 7101-7108) deployed separately to Cloud Run
- Lazy initialization: Services listen immediately, initialize dependencies in background via `setImmediate()`
- Multi-tenant isolation enforced at JWT validation layer
- Hybrid search combining vector search (pgvector) with text search and reranking
- Async enrichment pipeline via Python workers and Together AI
- Pub/Sub-driven scheduler for long-running jobs

## Layers

**API Gateway Layer (Cloud Run):**
- Purpose: HTTP entry point, routing, and tenant isolation
- Location: Services in `services/hh-*/src/`
- Contains: Fastify route handlers, request validation schemas, middleware
- Depends on: Tenant resolver, auth validators, downstream services
- Used by: Frontend (React), external API clients

**Service Layer (Core Business Logic):**
- Purpose: Orchestrate domain operations (search, reranking, embedding, enrichment)
- Location: `services/hh-*/src/*-service.ts`
- Examples: `SearchService`, `RerankService`, `EmbeddingsService`, `EnrichmentService`
- Depends on: Database clients, external AI clients, Redis cache
- Pattern: Constructor injection of dependencies, no global state

**Data Access Layer (Infrastructure Clients):**
- Purpose: Abstract database/cache/external API interactions
- Location: `services/hh-*/src/*-client.ts`
- Examples: `PgVectorClient`, `RedisClient`, `RerankClient`, `TogetherClient`, `GeminiClient`, `FirestoreClient`
- Implements: Connection pooling, health checks, retry logic, timeout handling
- Depends on: Raw database/API libraries

**Shared Common Layer:**
- Purpose: Reusable middleware, logging, auth, config parsing
- Location: `services/common/src/`
- Exports: Logger factory, Fastify server builder, config helpers, auth middleware, error types, tenant utilities
- Depends on: Cloud SDK libraries, Firebase Admin

**Python Worker Layer (Async Processing):**
- Purpose: Long-running enrichment jobs (embedding, LLM processing)
- Location: `scripts/` (bind-mounted into `hh-enrich-svc`)
- Examples: Together AI processors, Gemini enrichment, skill classification
- Triggers: Called from `hh-enrich-svc` via subprocess/job queue
- Depends on: External AI APIs, PostgreSQL

**Frontend Layer:**
- Purpose: User interface for search, results viewing, candidate interaction
- Location: `headhunter-ui/src/`
- Contains: React components, services, contexts, types
- Key areas: Auth flow, Search page, Candidate cards, Dashboard

## Data Flow

**Candidate Search Flow:**

1. Frontend posts to `POST /search` (hh-search-svc:7102)
2. Request validated against `hybridSearchSchema` in `routes.ts`
3. `SearchService.hybridSearch()` orchestrates:
   - Compute cache token from job description hash
   - Check Redis cache (if enabled)
   - Call `EmbedClient` → `hh-embed-svc:7101` to get embedding
   - Query pgvector: `SELECT candidate_id FROM embeddings_table WHERE embedding <-> query_embedding < threshold`
   - Fetch candidate profiles from PostgreSQL
   - Apply filters (tech stack, location, specialty)
   - Optionally call `RerankClient` → `hh-rerank-svc:7103` for scoring
   - Return ranked results with evidence
4. Frontend renders `SearchResults` component with candidate cards

**Candidate Enrichment Flow:**

1. Admin/system initiates enrichment via `hh-admin-svc:7107` or scheduled job
2. Job queued in PostgreSQL `enrichment_jobs` table
3. `hh-enrich-svc:7108` polls for jobs
4. For each job:
   - Calls Python worker script (e.g., `scripts/together_ai_firestore_processor.py`)
   - Worker fetches candidate from Firestore
   - Calls Together AI with candidate resume/profile
   - Returns enriched profile (career trajectory, skills, leadership scope)
   - Stores in Firestore under `/profiles/{tenantId}/{candidateId}`
5. Job marked complete; status available via evidence API

**Embedding Generation Flow:**

1. Frontend/system posts to `POST /embed` (hh-embed-svc:7101)
2. `EmbeddingsService` normalizes candidate profile
3. Determines embedding provider (Gemini, VertexAI, local, Together)
4. Calls external AI service or local embedding
5. Stores embedding + metadata in pgvector table: `(candidate_id, tenant_id, embedding, embedding_provider, created_at)`
6. Returns embedding stats

**Reranking Flow:**

1. Triggered from `hh-search-svc` after vector recall
2. Builds cache key: `rerank:{tenantId}:{jdHash}:{docsetHash}`
3. Check Redis for cached scores (if enabled)
4. If miss: Call `RerankService.rerank()`
5. Service builds Together AI or Gemini rerank prompt
6. AI returns scored ordering
7. Cache result in Redis with TTL
8. Return final ranked candidate list with scores and reasoning

**Pub/Sub Scheduler Flow:**

1. `hh-admin-svc` publishes scheduled messages to Pub/Sub topics
2. Cloud Scheduler triggers topic publications
3. `hh-msgs-svc:7106` subscribes and deserializes messages
4. Routes to appropriate handler (enrichment job, notification, etc.)
5. Pub/Sub guarantees at-least-once delivery with acknowledgment

**State Management:**
- **Operational data (profiles, CRUD)**: Firestore collections (tenant-scoped)
- **Search/embedding data**: PostgreSQL + pgvector (high-velocity, structured)
- **Caching**: Redis (request-level caching, rerank scoring, idempotency)
- **Secrets**: GCP Secret Manager (API keys, credentials)
- **Job state**: PostgreSQL tables (`enrichment_jobs`, `job_results`)

## Key Abstractions

**SearchService (Hybrid Search):**
- Purpose: Unify vector + text + filter search with optional reranking
- File: `services/hh-search-svc/src/search-service.ts`
- Methods: `hybridSearch()`, `candidateSearch()`, `setFirestore()`, `computeCacheToken()`
- Pattern: Dependency injection of pgClient, embedClient, rerankClient, redisClient
- Abstraction: Hides complexity of multi-stage recall + filter + rerank

**RerankService (LLM-Driven Scoring):**
- Purpose: Use Together AI or Gemini to intelligently rank candidates vs job description
- File: `services/hh-rerank-svc/src/rerank-service.ts`
- Methods: `rerank()`, `buildCacheDescriptor()`, `buildChatMessages()`
- Cache Key Pattern: `rerank:{tenantId}:{jdHash}:{docsetHash}` (deterministic)
- Returns: Scored and re-ordered candidate list with AI reasoning

**PgVectorClient (Database Layer):**
- Purpose: Abstract PostgreSQL + pgvector operations (pooling, health checks, migrations)
- File: `services/hh-search-svc/src/pgvector-client.ts`
- Methods: `query()`, `healthCheck()`, `initialize()`, `close()`, `migrateSchema()`
- Pattern: Connection pooling with min/max limits, idempotent initialization
- Health Check: Validates connectivity, checks table schemas, reports degradation

**EmbedClient (Service-to-Service RPC):**
- Purpose: Call hh-embed-svc for embedding generation with resilience
- File: `services/hh-search-svc/src/embed-client.ts`
- Methods: `embed()`, `healthCheck()`
- Pattern: Retry logic, circuit breaker, timeout wrapping, ID token auth
- Resilience: Configurable retries, exponential backoff, max failures before degradation

**RerankClient (Service-to-Service RPC):**
- Purpose: Call hh-rerank-svc for candidate reranking
- File: `services/hh-search-svc/src/rerank-client.ts`
- Methods: `rerank()`, `healthCheck()`
- Pattern: Same as EmbedClient (retry, timeout, ID token)

**EnrichmentService (Long-Running Jobs):**
- Purpose: Coordinate background enrichment jobs (embedding → LLM → storage)
- File: `services/hh-enrich-svc/src/enrichment-service.ts`
- Pattern: Job polling, subprocess spawning, error recovery
- Depends on: PostgreSQL job table, Python worker scripts, Together AI

## Entry Points

**hh-search-svc (Port 7102):**
- Location: `services/hh-search-svc/src/index.ts`
- Triggers: POST /search, POST /hybrid-search, GET /health, GET /readiness
- Responsibilities: Orchestrate hybrid search; coordinate with embed, rerank services
- Lazy Init: Initializes pgClient, redisClient, embedClient, rerankClient in background

**hh-rerank-svc (Port 7103):**
- Location: `services/hh-rerank-svc/src/index.ts`
- Triggers: POST /rerank, GET /health, GET /readiness
- Responsibilities: Score candidates using AI (Together or Gemini); cache results
- Lazy Init: Initializes redisClient, togetherClient, geminiClient in background

**hh-embed-svc (Port 7101):**
- Location: `services/hh-embed-svc/src/index.ts`
- Triggers: POST /embed, GET /health, GET /readiness
- Responsibilities: Generate embeddings for candidate profiles
- Lazy Init: Initializes pgClient, embeddingProvider (local/Gemini/VertexAI)

**hh-enrich-svc (Port 7108):**
- Location: `services/hh-enrich-svc/src/index.ts`
- Triggers: POST /enrich, GET /health, GET /readiness
- Responsibilities: Poll enrichment jobs; spawn Python workers
- Lazy Init: Initializes pgClient, jobStore, enrichmentService

**hh-admin-svc (Port 7107):**
- Location: `services/hh-admin-svc/src/index.ts`
- Triggers: POST /jobs/schedule, PUT /tenants, POST /policies, GET /health
- Responsibilities: Tenant management, job scheduling, policy enforcement
- Lazy Init: Initializes pgClient, pubsubClient, schedulerClient

**hh-msgs-svc (Port 7106):**
- Location: `services/hh-msgs-svc/src/index.ts`
- Triggers: Pub/Sub messages, GET /health
- Responsibilities: Message routing, notifications, fan-out
- Lazy Init: Initializes pubsubClient, redisClient

**React Frontend:**
- Location: `headhunter-ui/src/index.tsx`
- Entry: App.tsx → App routes (Auth, Search, Dashboard, Admin)
- Contexts: Auth context, Search context (holds query state)
- Services: API client for calling backend services

## Error Handling

**Strategy:** Multi-level resilience with degradation

**Patterns:**
- **Validation**: Zod schemas at route handler (e.g., `hybridSearchSchema` in `schemas.ts`)
- **Service errors**: Throw typed errors (`BadRequestError`, `NotFoundError`, `ServiceUnavailableError`) from `@hh/common`
- **Circuit breaker**: Embed/Rerank clients track failures; fall back to passthrough after threshold
- **Timeout wrapping**: All external calls wrapped with Promise.race() against timeout
- **Health checks**: Route handlers check dependency health before executing; return 503 if degraded
- **Logging**: Structured logging with tenantId, requestId, traceId for observability

## Cross-Cutting Concerns

**Logging:** Pino-based structured logging (JSON output) with request context
- File: `services/common/src/logger.ts`
- Exported: `getLogger({ module: 'name' })` factory function
- Context: `tenantId`, `requestId`, `traceId` automatically added to all logs

**Validation:** Zod schema validation at route layer
- Pattern: Define schema, validate request body/params
- Example: `schemas.ts` in each service defines `hybridSearchSchema`, `rerankRequestSchema`, etc.
- Response: 400 Bad Request with validation errors if invalid

**Authentication:** JWT-based multi-tenant isolation
- File: `services/common/src/auth.ts`
- Flow: Extract JWT from Authorization header → validate signature → extract tenantId
- Middleware: Fastify plugin that validates JWT on every request
- Failure: 401 Unauthorized if missing or invalid

**Rate Limiting:** Redis-backed token bucket (configurable per service)
- File: `services/common/src/rate_limit.ts`
- Pattern: Increment counter in Redis; return 429 Too Many Requests if exceeded
- TTL: Configurable window (default 1 minute)

---

*Architecture analysis: 2026-01-24*
