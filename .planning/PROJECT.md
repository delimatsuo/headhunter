# Headhunter AI

## What This Is

An AI-powered recruitment analytics system that helps recruiters find the right candidates from a database of 23,000+ profiles. The system uses semantic understanding, career trajectory analysis, and multi-signal scoring to surface qualified candidates — not just keyword matches.

## Core Value

**Find candidates who are actually qualified, not just candidates who happen to have the right keywords.** When search returns results, they should be people a recruiter would actually want to contact.

## Current Milestone: v2.0 Advanced Intelligence

**Goal:** Add predictive trajectory modeling, natural language search, and compliance tooling to the leader-level search foundation.

**Target features:**
- RNN-based career trajectory prediction ("Support → QA → Backend → ?")
- Natural language search interface for recruiters
- Bias reduction and compliance tools (NYC Local Law 144, EU AI Act)
- Performance optimization for sub-500ms latency

## Requirements

### Validated

v1.0 capabilities (shipped and verified):

- ✓ 3-stage pipeline: retrieval (500+) → scoring (100) → reranking (50) — v1.0
- ✓ Hybrid search: Vector + BM25 with RRF fusion — v1.0
- ✓ Multi-signal scoring: 8 weighted signals — v1.0
- ✓ Skills intelligence: 468 skills with inference and transferability — v1.0
- ✓ Career trajectory: direction, velocity, fit scoring — v1.0
- ✓ Match transparency: score breakdowns, skill chips, LLM rationale — v1.0
- ✓ Hybrid search combining vector embeddings with text search — existing
- ✓ LLM-based reranking via Together AI or Gemini — existing
- ✓ Multi-tenant isolation via JWT authentication — existing
- ✓ Embedding generation via Gemini/VertexAI — existing
- ✓ Redis caching for rerank results — existing
- ✓ PostgreSQL + pgvector for vector search — existing
- ✓ Firestore for candidate profile storage — existing
- ✓ React frontend with search interface — existing
- ✓ 8 Fastify microservices deployed to Cloud Run — existing

### Active

v2.0 improvements:

- [ ] RNN-based next-title prediction for career trajectory
- [ ] Hireability prediction (will they join a company like ours?)
- [ ] Success signal detection from career patterns
- [ ] Natural language search interface for recruiters
- [ ] Query auto-classification into structured parameters
- [ ] Anonymization mode for bias reduction
- [ ] Diversity indicators in search results
- [ ] Bias audit tooling for compliance
- [ ] p95 latency under 500ms (vs current 1.2s target)
- [ ] Embedding pre-computation for entire candidate pool
- [ ] Real-time scoring cache invalidation

### Out of Scope

- Real-time chat with candidates — different product focus
- Candidate application tracking — this is search/discovery, not ATS
- Job posting/requisition management — out of scope for search improvements
- Mobile native app — web-first approach
- Agentic AI (autonomous outreach) — requires outreach integration
- Multi-channel sourcing (GitHub, etc.) — focus on existing candidates first

## Context

**The problem:** Current search returns only ~10 candidates from 23,000+ because hard filters cascade exclusions. Candidates without specialty data, missing skills, or incomplete profiles get filtered out before scoring even happens.

**Research findings:** Industry leaders (Eightfold, Findem, LinkedIn) use:
- Multi-stage retrieval (recall → rank → re-rank)
- Career trajectory prediction via RNNs
- Skills ontology with inference
- Hybrid search (BM25 + vector)
- Multi-signal weighted scoring

**Existing asset:** EllaAI skills taxonomy at `/Volumes/Extreme Pro/myprojects/EllaAI/react-spa/src/data/skills-master.ts` has 200+ skills with `relatedSkillIds`, `aliases`, `tags` for skill inference.

**Current architecture:** 8 Fastify microservices with lazy initialization, pgvector for embeddings, Redis for caching, Together AI for LLM processing.

## Constraints

- **Tech stack**: Must use existing PostgreSQL + pgvector, Redis, Fastify services — no new databases
- **AI provider**: Together AI for production LLM processing (per PRD)
- **Embeddings**: Gemini (gemini-embedding-001) with VertexAI fallback
- **Performance**: p95 latency <1.2s, cache hit rate >0.98, error rate <1%
- **Multi-tenant**: All changes must respect tenant isolation via JWT

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use EllaAI skills taxonomy | Already built, 200+ skills with adjacency graph | ✓ Good |
| 3-stage pipeline over single pass | Industry research shows this is how leaders build search | ✓ Good |
| Scoring-first over filter-first | Filters exclude potential matches; scoring includes with lower weight | ✓ Good |
| Copy skills-master.ts to headhunter | Maintain local copy for customization | ✓ Good |
| Rule-based trajectory (v1) | Explainable, sufficient per research; ML for v2 | ✓ Good |

---
*Last updated: 2026-01-25 after v1.0 completion, v2.0 milestone started*
