# Technology Stack

**Analysis Date:** 2026-01-24

## Languages

**Primary:**
- TypeScript 5.4+ - All 8 Fastify microservices and web UI
- JavaScript - Runtime for Node.js 20+ services
- Python 3.11+ - Data processing scripts, enrichment pipelines, webhook integration

**Secondary:**
- SQL - PostgreSQL with pgvector for vector search
- YAML - docker-compose.local.yml configuration

## Runtime

**Environment:**
- Node.js 20 LTS (specified in service Dockerfiles and docker-compose.local.yml)
- Python 3.11+ (for scripts and enrichment workers)

**Package Managers:**
- npm workspaces - TypeScript services workspace root at `services/package.json`
- pip - Python dependencies via `requirements.txt`, `requirements-pgvector.txt`, `scripts/requirements_webhook.txt`

**Lockfiles:**
- package-lock.json - Present in all service and UI directories
- Workspace dependency caching via npm workspaces

## Frameworks

**Core - API/Backend:**
- Fastify 4.26+ - HTTP framework for all 8 Cloud Run services (`services/*/src/index.ts`)
  - `@fastify/cors` 9.0.0 - CORS support
  - `@fastify/helmet` 11.0.0 - Security headers
  - `@fastify/rate-limit` 10.3.0 - Rate limiting
  - `@fastify/under-pressure` 8.5.0 - Load monitoring
  - fastify-plugin 4.5.1 - Plugin registration
- Express 4.21+ - HTTP framework in Cloud Functions (`functions/src/`)

**Frontend:**
- React 18.3+ - UI library (`headhunter-ui/src/`)
- Material-UI (@mui/material) 5.15+ - Component library
- @emotion/react, @emotion/styled - CSS-in-JS styling
- react-scripts 5.0.1 - Create React App build tooling

**Testing:**
- Jest 29.7+ - Unit/integration test runner (workspace root and services)
- Vitest 4.0+ - Faster test runner for individual services
- @testing-library/react 16.3+ - React component testing
- @testing-library/jest-dom - DOM matchers

**Build/Dev:**
- TypeScript Compiler (tsc) - Workspace builds at `services/package.json`
- ts-node 10.9+ - TypeScript execution for development
- tsx 4.7+ - Fast TypeScript runner (hh-msgs-svc)
- ESLint 8.57+ - Linting with TypeScript support
- Prettier 9.1.0 - Code formatting (config via eslint-config-prettier)

## Key Dependencies

**Critical - Data Storage:**
- `pg` 8.11+ - PostgreSQL client for pgvector integration (all search/enrichment services)
- `pgvector` 0.2.1 - Vector type client for embeddings
- `@google-cloud/firestore` 7.8+ - Firestore client for profiles and metadata
- `firebase-admin` 12+ - Firebase Admin SDK for operational data

**Critical - AI Processing:**
- `together` 0.2+ - Together AI Python client for enrichment pipelines
- `@google-cloud/aiplatform` 3.6+ - Vertex AI embeddings (hh-embed-svc)
- `@google/generative-ai` 0.24+ - Google Gemini API (functions)
- `@google-cloud/vertexai` 1.10+ - VertexAI client (functions)

**Critical - Infrastructure:**
- `ioredis` 5.3+ - Redis client for caching and session management
- `@google-cloud/pubsub` 5.2+ - Pub/Sub for async messaging (hh-admin-svc, hh-msgs-svc)
- `@google-cloud/scheduler` 5.3+ - Cloud Scheduler integration (hh-admin-svc)
- `@google-cloud/cloud-sql-connector` 1.3+ - Cloud SQL Proxy (hh-admin-svc)
- `@google-cloud/monitoring` 5.3+ - Cloud Monitoring metrics (hh-admin-svc)
- `@google-cloud/run` 3.0+ - Cloud Run integration (hh-admin-svc)

**Authentication:**
- `firebase` 12.4+ - Firebase SDK for web client
- `firebase-functions` 6.1+ - Firebase Functions runtime
- `jose` 4.15+ - JWT signing and verification
- `google-auth-library` 9.10+ - GCP authentication utilities

**Utilities:**
- `axios` 1.6+ - HTTP client (headhunter main, hh-search-svc)
- `pino` 8.17+ - JSON logging (services common)
- `uuid` 9.0+ - UUID generation
- `lodash` 4.17+ - Utility functions
- `lru-cache` 10.2+ - In-memory caching
- `p-retry` 7.0+ - Promise retry utility
- `p-timeout` 7.0+ - Promise timeout wrapper
- `date-fns` 4.1+ - Date utilities
- `zod` 3.22+ - TypeScript schema validation (hh-msgs-svc, functions)
- `remove-accents` 0.5+ - String normalization
- `simple-statistics` 7.8+ - Statistical calculations

**Python Utilities:**
- `google-cloud-firestore` 2.11+ - Python Firestore client
- `google-cloud-storage` 2.10+ - Cloud Storage access
- `google-cloud-aiplatform` 1.25+ - Vertex AI Python SDK
- `google-auth` 2.20+ - GCP authentication
- `pandas` 2.0+ - Data manipulation
- `numpy` 1.24+ - Numerical computing
- `pydantic` 2.0+ - Data validation
- `httpx` 0.24+ - Async HTTP client
- `aiohttp` 3.8+ - Async HTTP client
- `psycopg2-binary` 2.9+ - PostgreSQL adapter
- `asyncpg` 0.29+ - Async PostgreSQL
- `SQLAlchemy` 2.0+ - ORM for databases

## Configuration

**Environment:**
- Root `.env` file with shared secrets and connection strings
- Per-service `.env.local` files in `services/hh-*-svc/.env.local`
- Per-service `.env.example` files documenting required variables
- `docker-compose.local.yml` - Local development stack configuration with environment overrides

**Build:**
- `services/tsconfig.base.json` - Base TypeScript configuration
- Individual service tsconfig.json files inheriting from base
- `.eslintrc` files for linting rules
- `jest.config.js` at workspace root
- `Dockerfile` in each service directory using Node 20-slim

**Key Configuration Files:**
- `services/common/src/config.ts` - Shared service configuration (auth, Redis, Firestore, monitoring)
- `services/hh-search-svc/src/config.ts` - Search service config (pgvector, Redis, embed/rerank services)
- `services/hh-rerank-svc/src/config.ts` - Rerank service config (Together AI, Gemini, Redis)
- `services/hh-msgs-svc/src/config.ts` - Messaging service config (PostgreSQL, Redis)

## Platform Requirements

**Development:**
- Node.js 20+ (specified in Dockerfile FROM clauses)
- Docker Desktop with docker-compose
- Python 3.11+ with pip
- GCP SDK emulators (Firestore, Pub/Sub) via Cloud SDK image
- PostgreSQL 15+ with pgvector extension (`ankane/pgvector:v0.5.1`)
- Redis 7-alpine for caching
- Mock OAuth server (local-only) for JWT testing

**Production:**
- Google Cloud Platform (Cloud Run, Cloud SQL, Firestore, Pub/Sub, Cloud Scheduler, Secret Manager)
- Cloud SQL PostgreSQL with pgvector extension
- Cloud Memorystore for Redis
- Cloud Storage for file uploads
- Secret Manager for credential storage
- Service accounts with appropriate IAM roles per service

**Cloud Services Integration:**
- Together AI API (qwen2.5-32b-instruct model)
- Google Gemini API for reranking fallback
- Vertex AI for embeddings alternative
- Cloud Logging for structured logs
- Cloud Monitoring for observability
- Cloud Trace for distributed tracing

---

*Stack analysis: 2026-01-24*
