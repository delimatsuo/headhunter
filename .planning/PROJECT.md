# Headhunter AI

## What This Is

An AI-powered recruitment analytics system that helps recruiters find the right candidates from a database of 23,000+ profiles. The system uses semantic understanding, career trajectory analysis, and multi-signal scoring to surface qualified candidates — not just keyword matches.

## Core Value

**Find candidates who are actually qualified, not just candidates who happen to have the right keywords.** When search returns results, they should be people a recruiter would actually want to contact.

## Requirements

### Validated

These capabilities exist and are working in the current codebase:

- ✓ Hybrid search combining vector embeddings with text search — existing
- ✓ LLM-based reranking via Together AI or Gemini — existing
- ✓ Candidate profile enrichment with career trajectory data — existing
- ✓ Multi-tenant isolation via JWT authentication — existing
- ✓ Embedding generation via Gemini/VertexAI — existing
- ✓ Redis caching for rerank results — existing
- ✓ PostgreSQL + pgvector for vector search — existing
- ✓ Firestore for candidate profile storage — existing
- ✓ React frontend with search interface — existing
- ✓ 8 Fastify microservices deployed to Cloud Run — existing

### Active

These are the improvements we're building to achieve leader-level search:

- [ ] Remove hard filters that exclude candidates with missing data
- [ ] Implement multi-signal scoring (8 weighted signals instead of pass/fail)
- [ ] Add career trajectory analysis to predict candidate potential
- [ ] Build skills inference using EllaAI taxonomy (200+ skills with adjacency graph)
- [ ] Implement hybrid BM25 + vector search for better recall
- [ ] 3-stage search pipeline: broad retrieval → scoring → LLM reranking
- [ ] Treat missing data as neutral signal (0.5 score) not exclusion
- [ ] Surface transferable skills from related skill relationships

### Out of Scope

- Real-time chat with candidates — different product focus
- Candidate application tracking — this is search/discovery, not ATS
- Job posting/requisition management — out of scope for search improvements
- Mobile native app — web-first approach

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
| Use EllaAI skills taxonomy | Already built, 200+ skills with adjacency graph | — Pending |
| 3-stage pipeline over single pass | Industry research shows this is how leaders build search | — Pending |
| Scoring-first over filter-first | Filters exclude potential matches; scoring includes with lower weight | — Pending |
| Copy skills-master.ts to headhunter | Maintain local copy for customization | — Pending |

---
*Last updated: 2026-01-24 after initialization*
