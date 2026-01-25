# Project State: Headhunter AI v2.0 Advanced Intelligence

**Initialized:** 2026-01-24
**Current Status:** Phase 12 In Progress - Plan 03 complete

---

## Project Reference

**Core Value:** Find candidates who are actually qualified, not just candidates who happen to have the right keywords.

**Current Focus:** v2.0 Advanced Intelligence - Performance optimization, NLP search, ML trajectory, bias reduction, compliance tooling.

**Key Files:**
- `.planning/PROJECT.md` - Project definition and constraints
- `.planning/REQUIREMENTS.md` - All requirements with traceability
- `.planning/ROADMAP.md` - Phase structure and success criteria
- `.planning/MILESTONES.md` - Archived v1.0 milestone
- `.planning/research/v2/SUMMARY.md` - v2.0 research findings

---

## Current Position

**Milestone:** v2.0 Advanced Intelligence
**Phase:** 12 - Natural Language Search (IN PROGRESS)
**Plan:** 3 of 5 executed
**Status:** Plan 12-03 complete (Query Expansion)
**Last activity:** 2026-01-25 - Completed 12-03-PLAN.md (Query Expansion)

**Progress:** [##########] v1.0 100% | [######----] v2.0 Phase 12: 60%

**Next Action:** Execute 12-04-PLAN.md (Search Integration)

---

## v2.0 Phase Progress

| Phase | Name | Status | Requirements | Progress |
|-------|------|--------|--------------|----------|
| 11 | Performance Foundation | Complete | 5 | 100% |
| 12 | Natural Language Search | In Progress | 5 | 60% |
| 13 | ML Trajectory Prediction | Pending | 5 | 0% |
| 14 | Bias Reduction | Pending | 5 | 0% |
| 15 | Compliance Tooling | Pending | 6 | 0% |

**Overall v2.0:** 1/5 phases complete, 1 in progress (20%)

---

## v1.0 Phase Progress (Archived)

| Phase | Name | Status | Plans | Progress |
|-------|------|--------|-------|----------|
| 1 | Reranking Fix | Complete | 4/4 | 100% |
| 2 | Search Recall Foundation | Complete | 5/5 | 100% |
| 3 | Hybrid Search | Complete | 4/4 | 100% |
| 4 | Multi-Signal Scoring Framework | Complete | 5/5 | 100% |
| 5 | Skills Infrastructure | Complete | 4/4 | 100% |
| 6 | Skills Intelligence | Complete | 4/4 | 100% |
| 7 | Signal Scoring Implementation | Complete | 5/5 | 100% |
| 8 | Career Trajectory | Complete | 4/4 | 100% |
| 9 | Match Transparency | Complete | 7/7 | 100% |
| 10 | Pipeline Integration | Complete | 4/4 | 100% |

**v1.0 Total:** 10/10 phases complete (100%) - MILESTONE COMPLETE

---

## Performance Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| v1 Requirements | 28 | 28 done | Complete |
| v2 Requirements | 26 | 0 done | In Progress |
| p95 Latency | <500ms (v2) | ~1.2s (v1) | Phase 11 target |
| Search Recall | 50+ candidates | Achieved | Verified |
| Cache Hit Rate | >0.98 | Unknown | Unmeasured |

---

## Accumulated Context

### Key Decisions (v2.0)

| Decision | Rationale | Phase |
|----------|-----------|-------|
| Performance before features | Latency budget must be established before adding NLP/ML overhead | 11 |
| pgvectorscale over Pinecone | Stay on existing PostgreSQL, 28x improvement documented | 11 |
| Side-by-side HNSW + DiskANN indices | Feature flag enables A/B testing; instant rollback if issues | 11 |
| Default to HNSW, opt-in to DiskANN | HNSW proven stable; DiskANN requires Cloud SQL compatibility verification | 11 |
| Runtime tunable search_list_size | Allows recall/latency tradeoff without redeployment | 11 |
| poolMax=20, poolMin=5 | Cloud Run concurrency + warm connections for sub-500ms p95 | 11 |
| Parallel pool warmup | Minimize cold-start latency with Promise.all connection acquisition | 11 |
| Multi-layer cache with TTL jitter | 4 layers (search/rerank/specialty/embedding) with ±20% jitter to prevent cache stampede | 11 |
| Cache layer TTLs by staleness tolerance | Search 10min, Rerank 6hr, Specialty 24hr based on data volatility | 11 |
| Semantic Router for NLP | 5-100ms vector-based routing, not LLM-based parsing | 12 |
| Confidence threshold 0.6 default | Balances precision vs recall for intent classification | 12 |
| Portuguese utterances in routes | Brazilian recruiter market support | 12 |
| 150ms extraction timeout | Per RESEARCH.md latency budget, fallback to empty on timeout | 12 |
| Post-extraction hallucination filter | Validate skills against query text instead of relying on LLM | 12 |
| Bidirectional abbreviation matching | Support js->JavaScript and JavaScript->js lookups | 12 |
| Copy skills ontology to services workspace | Enables direct imports without cross-workspace path issues | 12 |
| Default confidence threshold 0.8 for expansion | Balance between recall and precision for skill expansion | 12 |
| Weight 0.6x for expanded skills | Explicit skills dominate scoring; expanded skills boost recall | 12 |
| ONNX Runtime for inference | Sub-50ms CPU inference, no GPU dependency, portable | 13 |
| Shadow mode for ML transition | 4-6 weeks side-by-side to validate ML matches rule-based baseline | 13 |
| Fairlearn for bias metrics | Actively maintained, simpler API than AIF360 | 14 |
| PostgreSQL for audit logs | No new databases, 4-year retention in existing infrastructure | 15 |

### Key Decisions (v1.0 - Archived)

| Decision | Rationale | Phase |
|----------|-----------|-------|
| Fix reranking first | Critical bug: Match Score = Similarity Score (bypass active) | 1 |
| Sequential phases | Each phase builds on previous; no parallel paths | All |
| Copy skills taxonomy | Local copy for customization, independence from EllaAI | 5 |
| Rule-based trajectory | Explainable, sufficient per research; ML deferred to v2 | 8 |
| 3-stage pipeline | Retrieval (500) -> Scoring (100) -> Rerank (50) | 10 |

### Technical Notes

**v2.0 Infrastructure Additions:**
- hh-trajectory-svc on port 7109 (new service for ML trajectory)
- pgvectorscale extension (replaces HNSW with StreamingDiskANN)
- BigQuery export for long-term audit storage

**Phase 12 Deliverables (In Progress):**
- IntentRouter class with semantic routing (NLNG-01)
- EntityExtractor class with Together AI JSON mode (NLNG-02)
- QueryExpander class with skills ontology expansion (NLNG-03)
- NLP types: IntentType, IntentRoute, ParsedQuery, ExtractedEntities
- Vector utilities: cosineSimilarity, averageEmbeddings
- Skills ontology (200+ skills) in services workspace
- 75 passing unit tests (19 intent + 33 entity + 23 query expander)

**v1.0 Deliverables:**
- 3-stage pipeline with 500/100/50 funnel
- Hybrid search (vector + BM25 via RRF)
- 8-signal weighted scoring framework
- 468-skill taxonomy with inference and transferability
- Career trajectory (direction, velocity, fit)
- Match transparency (breakdown, chips, rationale)

### Blockers

None currently identified.

### TODOs

**v2.0:**
- [x] Plan Phase 11 (Performance Foundation) - 5 plans created
- [x] Execute 11-01-PLAN.md (pgvectorscale + StreamingDiskANN)
- [x] Execute 11-02-PLAN.md (Connection pool tuning)
- [x] Execute 11-03-PLAN.md (Parallel query execution)
- [x] Execute 11-04-PLAN.md (Multi-layer Redis caching)
- [x] Execute 11-05-PLAN.md (Performance tracking + backfill)
- [x] Plan Phase 12 (Natural Language Search) - 5 plans created
- [x] Execute 12-01-PLAN.md (Semantic Router Lite)
- [x] Execute 12-02-PLAN.md (Entity Extraction)
- [x] Execute 12-03-PLAN.md (Query Expansion)
- [ ] Execute 12-04-PLAN.md (Search Integration)
- [ ] Execute 12-05-PLAN.md (Verification & Tuning)
- [ ] Verify pgvectorscale Cloud SQL compatibility
- [ ] Run embedding backfill in production after Cloud SQL migration
- [ ] Prepare training data for trajectory LSTM (Phase 13 blocker)
- [ ] Identify independent auditor for NYC LL144 (Phase 15 blocker)

**v1.0 (deferred):**
- [ ] Verify search recall improvement in production
- [ ] Measure actual p95 latency baseline

---

## Session Continuity

**Last session:** 2026-01-25
**Stopped at:** Completed 12-03-PLAN.md (Query Expansion)
**Resume file:** None

### Context for Next Session

**Phase 12 Plan 03 (Query Expansion) COMPLETE:**

All 3 tasks executed successfully:

- Task 0: Copy skills ontology to services workspace - `c63bf88`
- Task 1: Implement QueryExpander - `0d1f314`
- Task 2: Unit tests (23 passing) - `397ae1b`

**Deliverables:**
- `services/hh-search-svc/src/shared/skills-master.ts` - 200+ skills database
- `services/hh-search-svc/src/shared/skills-graph.ts` - BFS expansion with LRU cache
- `services/hh-search-svc/src/nlp/query-expander.ts` - QueryExpander class
- `services/hh-search-svc/src/nlp/__tests__/query-expander.spec.ts` - Unit tests

**Key Features:**
- Configurable depth, confidence threshold, max expansions
- Explicit skills get confidence 1.0, expanded get 0.6x
- Only high-confidence direct relations (>=0.8)
- In-memory graph lookup completes in <5ms
- Graceful fallback for unknown skills

**Ready for:**
- 12-04: Search Integration (orchestrates intent + extraction + expansion)
- 12-05: Verification & Tuning

---

v2.0 Roadmap complete. 5 phases defined with 26 requirements mapped:

| Phase | Name | Requirements | Research Needed |
|-------|------|--------------|-----------------|
| 11 | Performance Foundation | PERF-01 to PERF-05 | Low |
| 12 | Natural Language Search | NLNG-01 to NLNG-05 | Medium |
| 13 | ML Trajectory Prediction | TRAJ-05 to TRAJ-09 | HIGH |
| 14 | Bias Reduction | BIAS-01 to BIAS-05 | Medium |
| 15 | Compliance Tooling | COMP-01 to COMP-06 | Medium |

**Phase 12 Success Criteria:**
1. Natural language queries parsed into structured search parameters
2. Intent classification in <20ms (semantic router)
3. Entity extraction with >90% accuracy on test set
4. Skill expansion using ontology graph
5. Fallback to keyword search when confidence low

---

*State initialized: 2026-01-24*
*Last updated: 2026-01-25 - Completed Phase 12 Plan 03 (Query Expansion)*
