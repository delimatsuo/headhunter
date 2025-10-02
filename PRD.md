# [DEPRECATED] Headhunter PRD – reference only

⚠️ **Do not use this file for active planning or delivery.** The authoritative requirements live in `.taskmaster/docs/prd.txt`. All Fastify architecture, service contracts, and current milestones are documented there and in the canonical documentation set (`README.md`, `ARCHITECTURE.md`, `docs/HANDOVER.md`).

## Where to Find Source of Truth

- Product requirements and backlog: `.taskmaster/docs/prd.txt`
- Architecture and service topology: `ARCHITECTURE.md`
- Operational runbook: `docs/HANDOVER.md`
- Bootstrap and workflow guidance: `README.md`

## Current Architecture Snapshot (2025 Fastify Mesh)

- **Canonical repository**: `/Volumes/Extreme Pro/myprojects/headhunter` (all automation scripts source `scripts/utils/repo_guard.sh`; deprecated clones under `/Users/delimatsuo/Documents/Coding/headhunter` exit on invocation).
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

## Overview  
Headhunter v2.0 transforms Ella Executive Search's candidate database into an intelligent, semantic search engine powered by **cloud-based AI processing and vector embeddings**. It solves the inefficiency of keyword-based ATS queries by deeply analyzing 20,000+ candidates using Together AI's Llama 3.2 3B model, creating comprehensive profiles with 15+ detailed fields, and enabling semantic similarity search for recruiter workflows.

**Core Value Proposition**: Recruiters can upload job descriptions and instantly find the most relevant candidates from a database of enhanced profiles with semantic understanding, reducing time-to-longlist from hours to minutes while uncovering hidden matches that keyword search would miss.

## Business Requirements

### Primary Users & Workflows

**Persona: Alex (Senior Recruiter)**
- **Current Pain Points**: 
  - Hours spent on manual keyword searches
  - Missing ideal candidates due to limited search terms
  - Inconsistent profile data quality
  - No semantic understanding of candidate-role fit

- **Target Workflows**:
  1. **Semantic Job Search**: Upload job description → Get ranked candidate matches with similarity scores
  2. **Profile Management**: Update LinkedIn profiles → Re-process and refresh search results
  3. **Batch Processing**: Upload CSV files → Process thousands of candidates with AI analysis
  4. **Advanced Search**: Combine semantic search with structured filters (location, experience, skills)

### Success Metrics
- **Time-to-Longlist**: < 5 minutes (vs current 2+ hours)
- **Search Quality**: 90%+ relevant matches in top 20 results
- **Database Coverage**: Process all 29,000 historical candidates
- **User Adoption**: > 20 searches per recruiter per week
- **Satisfaction**: > 4.5/5 user rating

## Technical Architecture

### Multi-Stage AI Processing Pipeline

**Core Components:**
- **Stage 1 AI**: Together AI Llama 3.2 3B ($0.20/1M tokens) - Basic Enhancement
- **Stage 2 AI**: Together AI Qwen2.5 Coder 32B ($0.80/1M tokens) - Contextual Intelligence
- **Stage 3 AI**: VertexAI text-embedding-004 - Vector Embeddings
- **Orchestration**: Multi-stage pipeline with Cloud Run workers
- **Vector Database**: Cloud SQL + pgvector for semantic search
- **Structured Storage**: Firestore for rich candidate profiles
- **API Layer**: FastAPI + Cloud Run for search and CRUD operations

### 3-Stage Data Processing Pipeline

```
Stage 1: Basic Enhancement
Resume Text + Comments → Llama 3.2 3B → Enhanced Profile Structure (15+ fields)

Stage 2: Contextual Intelligence 
Enhanced Profile → Qwen2.5 Coder 32B → Trajectory-Based Skill Inference
- Company context analysis (Google vs startup patterns)
- Industry intelligence (FinTech vs consulting expertise)
- Role progression mapping (VP vs team lead skills)
- Educational context weighting (MIT vs state school signals)

Stage 3: Vector Generation
Enriched Profile → VertexAI Embeddings → 768-dim vectors for semantic search

Storage & Retrieval:
Profiles → Firestore (structured data) + Cloud SQL pgvector (semantic search)
Job Description → Vector similarity → Ranked candidate matches
```

## Comprehensive Candidate Profile Schema

### 15+ Detailed Profile Fields

**Personal Information**
- Full contact details and current role
- LinkedIn profile and location data

**Career Trajectory Analysis** 
- Current level (junior → executive)
- Progression speed and career velocity
- Role transitions and promotion patterns
- Years of experience breakdown

**Leadership Assessment**
- Management experience and team size
- Leadership style and cross-functional collaboration
- Mentorship experience and direct reports

**Company Pedigree**
- Company tier (startup → FAANG)
- Career trajectory across companies
- Industry focus and stability patterns

**Technical Skills Matrix**
- Primary languages and frameworks with confidence scores (0-100%)
- Cloud platforms and databases with evidence arrays
- Specializations and skill depth with fuzzy matching
- Learning velocity assessment and skill categorization

**Domain Expertise**
- Industry experience and business functions
- Vertical knowledge and regulatory experience
- Domain transferability scores

**Soft Skills Evaluation**
- Communication and collaboration strength
- Problem-solving and adaptability
- Leadership and emotional intelligence

**Cultural Signals**
- Work style and team dynamics
- Values alignment and cultural strengths
- Change adaptability and feedback receptiveness

**Compensation Intelligence**
- Salary range and total compensation
- Equity preferences and negotiation flexibility
- Compensation motivators

**Recruiter Insights**
- Engagement history and placement likelihood
- Best-fit roles and company types
- Interview strengths and potential concerns

**Search Optimization**
- Primary and secondary keywords with probability weights
- Skill tags with confidence levels and synonym matching
- Industry tags and seniority indicators
- Skill-aware search ranking with composite scoring

**Matching Intelligence**
- Ideal role types and company preferences with skill gap analysis
- Technology stack compatibility scores with confidence weighting
- Leadership readiness and cultural fit scores
- Skill probability assessment with evidence-based validation

**Executive Summary**
- One-line pitch and key differentiators
- Career narrative and ideal next role
- Overall rating and recommendation tier

## Semantic Search Architecture

### Vector Database Design

**Storage Strategy**: Hybrid dual-database approach
- **Cloud SQL + pgvector**: 768-dimensional vectors for fast similarity search
