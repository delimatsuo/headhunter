# [DEPRECATED] Headhunter PRD – reference only

⚠️ **Do not use this file for active planning or delivery.** The authoritative requirements live in `.taskmaster/docs/prd.txt`. All Fastify architecture, service contracts, and current milestones are documented there and in the canonical documentation set (`README.md`, `ARCHITECTURE.md`, `docs/HANDOVER.md`).

## Where to Find Source of Truth

- Product requirements and backlog: `.taskmaster/docs/prd.txt`
- Architecture and service topology: `ARCHITECTURE.md`
- Operational runbook: `docs/HANDOVER.md`
- Bootstrap and workflow guidance: `README.md`

## Current Architecture Snapshot (2025 Fastify Mesh)


- **Fastify services**: Eight HTTP services (`hh-embed-svc`, `hh-search-svc`, `hh-rerank-svc`, `hh-evidence-svc`, `hh-eco-svc`, `hh-msgs-svc`, `hh-admin-svc`, `hh-enrich-svc`) exposing ports 7101–7108. Responsibilities and dependencies are described in `ARCHITECTURE.md`.
- **Shared infrastructure**: Redis (redis:7-alpine), Postgres with pgvector (ankane/pgvector:v0.5.1), Firestore + Pub/Sub emulators (Cloud SDK), mock Together AI, mock OAuth, and Python enrichment workers. Topology is defined in `docker-compose.local.yml`.
- **Integration baseline**: `SKIP_JEST=1 npm run test:integration --prefix services` must report `cacheHitRate=1.0` and rerank latency ≈ 0 ms before code is promoted. Metrics are exported via `/metrics` on each Fastify service.
- **Bootstrap automation**: `scripts/prepare-local-env.sh` is planned to consolidate dependency installs, env hydration, emulator seeding, compose startup, and integration smoke tests. Until it lands, follow the manual procedures in `README.md` and `docs/HANDOVER.md` and annotate gaps with `TODO prepare-local-env`.

## Migration Context – Why Fastify?

The platform moved from Cloud Functions to the Fastify mesh to address:

- **Multi-tenant isolation**: Shared middleware (`@hh/common`) enforces issuer/audience validation, per-tenant cache namespaces, and schema guards that were cumbersome in Functions.
- **Latency and determinism**: Redis-backed rerank caching delivers near-zero latency; Functions cold starts routinely violated SLOs.
- **Local parity**: `docker-compose.local.yml` mirrors production services, allowing deterministic integration tests and offline work (mock Together AI, mock OAuth, emulators).
- **Operational control**: Cloud Run deployments expose consistent `/health`/`/metrics` endpoints, easing observability and incident response.
- **Extensibility**: The enrichment service integrates Python workers through bind mounts, enabling rapid iteration on ML-heavy tasks without redeploying Functions.

## Legacy Content (Cloud Functions Era)

The remainder of this document is preserved for historical reference only. Use it to understand legacy decisions or compare past scope; do not base current implementation work on these sections.

---

# Headhunter v2.0 - AI-Powered Recruitment Analytics Platform

Note: This document contains legacy content from earlier iterations. The authoritative PRD is maintained at `.taskmaster/docs/prd.txt` and reflects the current single-pass Qwen 2.5 32B architecture, unified search pipeline, and the “no mock fallbacks” policy.

# Product Requirements Document (PRD) - Headhunter AI

## 1. Executive Summary
Headhunter AI is an intelligent recruitment platform that uses LLMs to enrich candidate profiles, perform semantic search, and rank candidates against job descriptions.
**Update (Dec 2025):** The platform now operates on an **Agency Model**, featuring a centralized candidate database ("Ella Executive Search") accessible to all Ella employees, with support for isolated Client Organizations.

## 2. User Roles
- **Ella Recruiter (Admin):** Access to the central `org_ella_main` database (29k+ candidates). Can create and manage Client Organizations.
- **Client User:** Access to their specific private organization. Can view candidates explicitly shared or added to their org.

## 3. Key Features
### 3.1 Agency Model & Centralization
- **Central Hub:** All 29k+ candidates reside in `org_ella_main`.
- **Auto-Onboarding:** Users with `@ella.com.br` or `@ellaexecutivesearch.com` emails are automatically assigned to `org_ella_main`.
- **Client Isolation:** External users are assigned to new, private organizations.
- **Multi-Org Data Model (Dec 2025):**
  - Candidates have `org_ids[]` array for multi-org access
  - `source_orgs[]` tracks who added each candidate
  - `canonical_email` enables global deduplication
  - Ella sees ALL candidates; clients see only their `org_ids`

### 3.2 Search & Discovery
- **Hybrid Search:** Vector (Embeddings) + Keyword search.
- **Global Search:** Ella Recruiters search the entire central pool.
- **[NEW] AI Job Analysis:** One-click analysis of Job Descriptions to extract structured requirements (Skills, Level, Summary) before searching.
- **Reranking:** LLM-based candidate scoring.
  - **Reasoning Engine:** Uses "Few-Shot" examples to mimic human recruiter intuition (e.g. Scope vs Skills).
  - **Disqualification Logic:** Automatically deprioritizes candidates with mismatched seniority (e.g. IC vs Executive).
- **[NEW] Neural Match Architecture:**
  - **Cognitive Decomposition:** Breaks JDs into Identity, Domain, Scope, and Environment.
  - **Semantic Anchor:** Searches using a weighted intent query, ensuring "Generalist" roles don't match "Specialist" candidates.

### 3.3 User Interface
- **Simplified Navigation:** Dashboard and Search only.
- **Admin Portal:** For managing users and organizations.

## 4. Technical Architecture

### 4.1 Hybrid Infrastructure
The platform uses a hybrid architecture to optimize for both search performance and ease of management:
- **Search & Rerank:** 8 Fastify microservices on Cloud Run (optimized for high-concurrency, low-latency search).
- **Agency Management:** Firebase Cloud Functions (handling User Onboarding, Organization Logic, and Data Migration).

### 4.2 AI Processing Pipeline
- **Enrichment:** Candidates are processed to extract structured data (Skills, Experience, etc.).
- **Embeddings:** VertexAI `text-embedding-004` (768 dimensions).
- **Reranking:** **Gemini 1.5 Pro** (Primary) with Together AI (Fallback).

### 4.3 Data Storage
- **Firestore:** Stores enriched candidate profiles and user/org data.
- **Cloud SQL (pgvector):** Stores candidate embeddings for fast vector search.
- **Redis:** Caches search results and embeddings for performance.

## 5. Success Metrics
- **Search Latency:** p95 < 1.2s.
- **Rerank Quality:** "Senior Recruiter" level reasoning via Gemini.
- **Migration:** 100% of candidates in `org_ella_main`.
