# Codebase Structure

**Analysis Date:** 2026-01-24

## Directory Layout

```
/Volumes/Extreme Pro/myprojects/headhunter/
├── services/                          # Fastify microservices mesh (8 services)
│   ├── common/                        # Shared utilities and middleware
│   ├── hh-admin-svc/                  # Tenant mgmt, scheduling, policies (port 7107)
│   ├── hh-eco-svc/                    # ECO data pipelines (port 7105)
│   ├── hh-embed-svc/                  # Embedding generation (port 7101)
│   ├── hh-enrich-svc/                 # Long-running enrichment (port 7108)
│   ├── hh-evidence-svc/               # Provenance artifacts (port 7104)
│   ├── hh-msgs-svc/                   # Pub/Sub messaging (port 7106)
│   ├── hh-rerank-svc/                 # LLM reranking (port 7103)
│   ├── hh-search-svc/                 # Hybrid search orchestration (port 7102)
│   ├── package.json                   # Workspace root configuration
│   └── tsconfig.base.json             # Shared TypeScript config
├── functions/                         # Cloud Functions (legacy, deprecated)
│   └── src/                           # Triggered functions for batch ops
├── scripts/                           # Python worker scripts and utilities
│   ├── together_ai_processor.py       # Main Together AI enrichment
│   ├── firebase_streaming_processor.py
│   ├── sourcing_embeddings.py
│   ├── backfill_specialty_*.py        # Specialty field backfill variants
│   └── [50+ Python pipeline scripts]
├── headhunter-ui/                     # React frontend SPA
│   ├── src/
│   │   ├── components/                # React components (Search, Candidate, etc.)
│   │   ├── services/                  # API client, auth service
│   │   ├── contexts/                  # React contexts (auth, search state)
│   │   ├── config/                    # Environment config, API endpoints
│   │   ├── types/                     # TypeScript types and interfaces
│   │   ├── App.tsx                    # Root component with routing
│   │   └── index.tsx                  # React DOM render entry
│   ├── public/
│   └── package.json
├── config/                            # Infrastructure and deployment config
│   ├── cloud-run/                     # Cloud Run service manifests
│   ├── gateway/                       # API Gateway configuration
│   ├── infrastructure/                # Terraform, IaC modules
│   ├── monitoring/                    # Cloud Monitoring setup
│   └── security/                      # Security policies, secrets
├── docs/                              # Documentation
│   ├── ARCHITECTURE.md                # Detailed system design
│   ├── PRODUCTION_DEPLOYMENT_GUIDE.md # Deployment procedures
│   ├── MONITORING_RUNBOOK.md          # Observability operations
│   ├── HANDOVER.md                    # Operator runbook
│   ├── TDD_PROTOCOL.md                # Test-driven development
│   └── openapi/                       # OpenAPI specifications
├── tests/                             # Integration and end-to-end tests
│   ├── integration/                   # Service-to-service tests
│   ├── e2e/                           # Full workflow tests
│   └── fixtures/                      # Test data
├── docker/                            # Docker images and configs
│   ├── postgres/                      # PostgreSQL with pgvector
│   ├── mock-oauth/                    # JWT mock issuer
│   ├── mock-together/                 # Together AI mock API
│   └── python-worker/                 # Python enrichment worker
├── data/                              # Sample and processed datasets
│   ├── enriched/                      # Output of enrichment pipelines
│   ├── processed/                     # Cleaned/normalized data
│   ├── sourcing/                      # Candidate sourcing data
│   └── rescrape/                      # Re-scraped profile updates
├── .planning/                         # GSD planning documents
│   └── codebase/                      # Architecture/tech analysis
├── .deployment/                       # Deployment artifacts (gitignored)
│   ├── build-logs/
│   ├── deploy-logs/
│   ├── manifests/
│   └── performance-reports/
├── .taskmaster/                       # Task tracking and PRD
│   ├── tasks/                         # Task definitions
│   ├── docs/                          # PRD and specifications
│   └── reports/                       # Task analysis reports
├── .infrastructure/                   # Infrastructure provisioning snapshots
├── .monitoring/                       # Monitoring setup logs
├── docker-compose.local.yml           # Local dev stack (postgres, redis, emulators)
├── CLAUDE.md                          # Instructions for Claude agents
├── CLAUDE-FLOW.md                     # Commit/deploy workflow
├── ARCHITECTURE.md                    # Root-level architecture overview
├── README.md                          # Project overview and quick start
└── .env.example                       # Environment variable template
```

## Directory Purposes

**services/:**
- Purpose: Eight independent Fastify microservices
- Contains: TypeScript sources, route handlers, service logic, database clients
- Key files: `index.ts` (entry point), `*-service.ts` (business logic), `*-client.ts` (data access)

**services/common/:**
- Purpose: Shared code reused across all services
- Contains: Logger factory, Fastify server builder, config helpers, auth/tenant middleware
- Key exports: `buildServer()`, `getLogger()`, `getConfig()`, auth validators, error types

**services/hh-search-svc/src/:**
- Purpose: Hybrid search orchestration and vector recall
- Key files:
  - `index.ts`: Bootstrap, lazy initialization of dependencies
  - `search-service.ts`: `SearchService` class, hybrid search logic
  - `pgvector-client.ts`: PostgreSQL + pgvector queries, pooling, health checks
  - `embed-client.ts`: RPC to hh-embed-svc with retry/timeout
  - `rerank-client.ts`: RPC to hh-rerank-svc with resilience
  - `routes.ts`: Fastify route handlers for `/search`, `/hybrid-search`, `/health`, `/readiness`
  - `schemas.ts`: Zod validation schemas for request bodies

**services/hh-rerank-svc/src/:**
- Purpose: LLM-driven candidate reranking with caching
- Key files:
  - `rerank-service.ts`: `RerankService` class, Together AI / Gemini integration
  - `together-client.ts`: Together AI API client with retry/timeout
  - `gemini-client.ts`: Google Gemini API client
  - `redis-client.ts`: Redis-based rerank cache (`rerank:{tenantId}:{jdHash}:{docsetHash}`)
  - `routes.ts`: POST `/rerank` handler

**services/hh-embed-svc/src/:**
- Purpose: Embedding generation (Gemini, VertexAI, Together, local)
- Key files:
  - `embeddings-service.ts`: `EmbeddingsService` class, provider selection logic
  - `embedding-provider.ts`: Multi-provider abstraction (Gemini, VertexAI, etc.)
  - `pgvector-client.ts`: Store embeddings in PostgreSQL
  - `routes.ts`: POST `/embed` handler

**services/hh-enrich-svc/src/:**
- Purpose: Long-running enrichment jobs (polling, Python workers)
- Key files:
  - `enrichment-service.ts`: Job polling, subprocess spawning, worker coordination
  - `job-store.ts`: PostgreSQL enrichment_jobs table queries
  - `routes.ts`: POST `/enrich` handler
  - Workers spawned via `subprocess`: calls Python scripts from `scripts/` directory

**services/hh-admin-svc/src/:**
- Purpose: Tenant management, job scheduling, policies
- Key files:
  - `admin-service.ts`: Tenant CRUD, policy enforcement
  - `pubsub-client.ts`: Pub/Sub job publishing for scheduler
  - `routes.ts`: PUT `/tenants`, POST `/jobs/schedule`, GET `/policies`

**functions/src/:**
- Purpose: Cloud Functions (mostly deprecated, kept for reference)
- Files: CRUD functions, batch operations, legacy processors
- Status: Replaced by Fastify service mesh; retained in git for audit trail only

**scripts/:**
- Purpose: Python worker scripts for async enrichment and data pipelines
- Key files:
  - `together_ai_processor.py`: Main enrichment using Together AI LLM
  - `sourcing_embeddings.py`: Bulk embedding generation
  - `sourcing_gemini_enrichment.py`: Gemini-based enrichment
  - `backfill_specialty*.py`: Fill missing specialty field (multiple strategies)
  - `classify_rescraped.py`: Auto-classify rescraped candidate data
  - `build_linkedin_url_mapping.py`: LinkedIn profile URL mapping
- Bind-mounted into: `hh-enrich-svc` as `/app/scripts/` for subprocess calls
- Dependencies: `scripts/requirements*.txt`

**headhunter-ui/src/components/:**
- Purpose: React component hierarchy
- Structure:
  - `Search/`: SearchPage, SearchInput, SearchResults, filter UI
  - `Candidate/`: SkillAwareCandidateCard, CandidateDetail, profile display
  - `Dashboard/`: Dashboard page, analytics, metrics
  - `Admin/`: Tenant management, job scheduling UI
  - `Auth/`: Login, logout, auth flow components
  - `Navigation/`: Header, sidebar, routing

**headhunter-ui/src/services/:**
- Purpose: API clients and utility services
- Files: HTTP client for calling backend services, auth service, cache utilities

**config/infrastructure/:**
- Purpose: Terraform modules and IaC for GCP resources
- Structure: Modules for Cloud SQL, Redis, Pub/Sub, Secret Manager, Cloud Run

**docs/openapi/:**
- Purpose: OpenAPI 3.0 specifications for service APIs
- Files: One spec per service (search-api.yaml, rerank-api.yaml, etc.)

## Key File Locations

**Entry Points:**
- `services/hh-search-svc/src/index.ts`: hh-search-svc bootstrap
- `services/hh-rerank-svc/src/index.ts`: hh-rerank-svc bootstrap
- `services/hh-embed-svc/src/index.ts`: hh-embed-svc bootstrap
- `services/hh-enrich-svc/src/index.ts`: hh-enrich-svc bootstrap
- `services/hh-admin-svc/src/index.ts`: hh-admin-svc bootstrap
- `headhunter-ui/src/index.tsx`: React app DOM render
- `headhunter-ui/src/App.tsx`: React root component with routing

**Configuration:**
- `services/*/src/config.ts`: Per-service config parsing (environment variables)
- `services/common/src/config.ts`: Shared config and ServiceConfig interface
- `headhunter-ui/src/config/*.ts`: Frontend API endpoint config
- `.env.example`: Environment variable template (copy to `.env`)
- `docker-compose.local.yml`: Local stack composition (postgres, redis, emulators)

**Core Logic:**
- `services/hh-search-svc/src/search-service.ts`: Hybrid search orchestration
- `services/hh-rerank-svc/src/rerank-service.ts`: Reranking logic
- `services/hh-embed-svc/src/embeddings-service.ts`: Embedding generation
- `services/hh-enrich-svc/src/enrichment-service.ts`: Job queue polling
- `scripts/together_ai_processor.py`: Main Python enrichment worker

**Testing:**
- `services/*/src/__tests__/`: Jest/Vitest unit tests (co-located with source)
- `tests/integration/`: Service-to-service integration tests
- `tests/fixtures/`: Mock data, sample payloads
- `jest.config.js`: Root jest config
- `services/hh-search-svc/src/__tests__/search-service.test.ts`: Example test file

**Database:**
- `docker/postgres/initdb/`: PostgreSQL initialization SQL scripts
- Schema definitions: `001_embeddings_table.sql`, `002_candidates_table.sql`, etc.
- Migrations: Applied via `PgVectorClient.migrateSchema()` on service startup

## Naming Conventions

**Files:**
- Services: `hh-{name}-svc/src/{name}-service.ts` (e.g., `search-service.ts`)
- Clients: `hh-{name}-svc/src/{dependency}-client.ts` (e.g., `pgvector-client.ts`, `rerank-client.ts`)
- Routes: `routes.ts` (Fastify route handlers)
- Config: `config.ts` (environment parsing and validation)
- Schemas: `schemas.ts` (Zod validation schemas)
- Types: `types.ts` (TypeScript interfaces and types)
- Tests: `*.test.ts` or `*.spec.ts` (co-located with source in `__tests__/`)

**Directories:**
- Service dirs: `hh-{short-name}-svc` (e.g., `hh-search-svc`, `hh-rerank-svc`)
- Component dirs: PascalCase (e.g., `Search/`, `Candidate/`, `Dashboard/`)
- Utility dirs: lowercase-with-hyphens (e.g., `common/`, `utils/`, `middleware/`)

**TypeScript Classes:**
- Service classes: `{Feature}Service` (e.g., `SearchService`, `RerankService`)
- Client classes: `{External}Client` (e.g., `PgVectorClient`, `TogetherClient`)
- Error classes: `{Error}Error` (e.g., `ValidationError`, `TimeoutError`)

**React Components:**
- Functional components: PascalCase (e.g., `SearchResults.tsx`, `CandidateCard.tsx`)
- Hooks: `use{Feature}` (e.g., `useSearch.ts`, `useAuth.ts`)

## Where to Add New Code

**New Feature (e.g., new search filter):**
- Primary code: `services/hh-search-svc/src/search-service.ts`
- Types: Update `services/hh-search-svc/src/types.ts`
- Validation: Add schema to `services/hh-search-svc/src/schemas.ts`
- Routes: Add handler to `services/hh-search-svc/src/routes.ts`
- Tests: Add test file `services/hh-search-svc/src/__tests__/search-feature.test.ts`

**New Service Endpoint:**
- Create route handler in `services/{svc}/src/routes.ts`
- Implement logic in `services/{svc}/src/{svc}-service.ts`
- Define request/response types in `services/{svc}/src/types.ts`
- Validate with Zod schema in `services/{svc}/src/schemas.ts`
- Add test in `services/{svc}/src/__tests__/{feature}.test.ts`

**New Shared Utility:**
- File location: `services/common/src/{feature}.ts`
- Example: `services/common/src/logger.ts`, `services/common/src/auth.ts`
- Export from: `services/common/src/index.ts` barrel file
- Usage: Import from `@hh/common` in any service

**New React Component:**
- File location: `headhunter-ui/src/components/{Category}/{ComponentName}.tsx`
- Styles: Co-locate CSS as `{ComponentName}.css` (CSS Modules or plain CSS)
- Types: Add to `headhunter-ui/src/types/index.ts` if shared

**New Python Worker Script:**
- File location: `scripts/{feature}_{variant}.py`
- Convention: Prefix with category (backfill_, process_, etc.)
- Entry point: `if __name__ == '__main__':` block
- Called from: `hh-enrich-svc` via subprocess in `enrichment-service.ts`
- Dependencies: Add to `scripts/requirements.txt` or versioned variant

**Integration Test:**
- File location: `tests/integration/{feature}.test.ts`
- Pattern: Import multiple services, test end-to-end flow
- Fixtures: Use data from `tests/fixtures/`

## Special Directories

**`.deployment/` (gitignored):**
- Purpose: Deployment artifacts and logs
- Generated by: `./scripts/deploy-production.sh`
- Contents: Build logs, manifests, performance reports, error logs
- Committed: No (gitignored)
- Lifecycle: Cleaned before each deployment; retention policy in deploy scripts

**`.infrastructure/` (gitignored):**
- Purpose: Infrastructure provisioning snapshots
- Generated by: `./scripts/provision-gcp-infrastructure.sh`
- Contents: Pre-deployment state, resource IDs, configuration backups
- Committed: No (gitignored)
- Used for: Rollback and disaster recovery

**`.planning/codebase/` (committed):**
- Purpose: GSD codebase analysis documents
- Contents: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, CONCERNS.md, STACK.md, INTEGRATIONS.md
- Written by: Claude agents via `/gsd:map-codebase` command
- Read by: `/gsd:plan-phase` and `/gsd:execute-phase` commands

**`node_modules/` and `.git/` (gitignored):**
- Purpose: Dependencies and version control
- Regenerated: `npm install --workspaces` and git cloning

## Architecture Conventions

**Lazy Initialization Pattern:**
- All services follow: `bootstrap()` → register routes → listen → `setImmediate()` initialize dependencies
- Purpose: Fast Cloud Run cold start (listen before dependencies ready)
- Pattern found in: All 8 `hh-*/src/index.ts` files
- Benefits: Container ready for requests; dependencies initialized in background

**Dependency Injection:**
- Services receive dependencies via constructor (no singletons)
- Example: `SearchService` constructor accepts `{ pgClient, embedClient, rerankClient, ... }`
- Benefits: Testability, loose coupling, easy to mock

**Health Checks:**
- Each service exposes `/health` (liveness) and `/readiness` (dependencies ready)
- Readiness checks all critical dependencies (databases, external APIs)
- Health check interval: 10 seconds (configurable in under-pressure plugin)

**Error Handling:**
- Typed errors from `@hh/common` (BadRequestError, NotFoundError, etc.)
- All route handlers wrap in try-catch, return appropriate HTTP status
- External API calls wrapped in Promise.race() for timeout protection

---

*Structure analysis: 2026-01-24*
