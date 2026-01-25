# Project State: Headhunter AI v2.0 Advanced Intelligence

**Initialized:** 2026-01-24
**Current Status:** Phase 11 PLANNED - Ready for execution

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
**Phase:** 11 - Performance Foundation (in progress)
**Plan:** 11-02 of 5 complete
**Status:** Executing Phase 11 plans
**Last activity:** 2026-01-25 - Completed 11-02-PLAN.md (Connection pool tuning)

**Progress:** [##########] v1.0 100% | [##========] v2.0 Phase 11: 40%

**Next Action:** Execute 11-03-PLAN.md (Parallel query execution)

---

## v2.0 Phase Progress

| Phase | Name | Status | Requirements | Progress |
|-------|------|--------|--------------|----------|
| 11 | Performance Foundation | Planned | 5 | 0% |
| 12 | Natural Language Search | Pending | 5 | 0% |
| 13 | ML Trajectory Prediction | Pending | 5 | 0% |
| 14 | Bias Reduction | Pending | 5 | 0% |
| 15 | Compliance Tooling | Pending | 6 | 0% |

**Overall v2.0:** 0/5 phases complete (0%)

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
| poolMax=20, poolMin=5 | Cloud Run concurrency + warm connections for sub-500ms p95 | 11 |
| Parallel pool warmup | Minimize cold-start latency with Promise.all connection acquisition | 11 |
| Semantic Router for NLP | 5-100ms vector-based routing, not LLM-based parsing | 12 |
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
- [ ] Execute 11-03-PLAN.md (Parallel query execution)
- [ ] Execute 11-04-PLAN.md (Multi-layer Redis caching)
- [ ] Execute 11-05-PLAN.md (Performance tracking + backfill)
- [ ] Verify pgvectorscale Cloud SQL compatibility
- [ ] Prepare training data for trajectory LSTM (Phase 13 blocker)
- [ ] Identify independent auditor for NYC LL144 (Phase 15 blocker)

**v1.0 (deferred):**
- [ ] Verify search recall improvement in production
- [ ] Measure actual p95 latency baseline

---

## Session Continuity

**Last session:** 2026-01-25
**Stopped at:** Completed 11-02-PLAN.md (Connection pool tuning)
**Resume file:** None - ready for 11-03-PLAN.md

### Context for Next Session

Phase 11 (Performance Foundation) is fully planned with 5 executable plans:

**Wave 1 (Foundation - can run in parallel):**
- 11-01-PLAN.md: pgvectorscale extension and StreamingDiskANN index (PERF-02)
- 11-02-PLAN.md: Connection pool tuning and metrics (PERF-03 partial)

**Wave 2 (Depends on Wave 1):**
- 11-03-PLAN.md: Parallel query execution with Promise.all (PERF-03 complete)
- 11-04-PLAN.md: Multi-layer Redis caching strategy (PERF-05)

**Wave 3 (Integration - depends on all):**
- 11-05-PLAN.md: Performance tracking, observability, embedding backfill (PERF-01, PERF-04)

---

v2.0 Roadmap complete. 5 phases defined with 26 requirements mapped:

| Phase | Name | Requirements | Research Needed |
|-------|------|--------------|-----------------|
| 11 | Performance Foundation | PERF-01 to PERF-05 | Low |
| 12 | Natural Language Search | NLNG-01 to NLNG-05 | Medium |
| 13 | ML Trajectory Prediction | TRAJ-05 to TRAJ-09 | HIGH |
| 14 | Bias Reduction | BIAS-01 to BIAS-05 | Medium |
| 15 | Compliance Tooling | COMP-01 to COMP-06 | Medium |

**Phase 11 Success Criteria:**
1. p95 latency under 500ms (measured via response headers)
2. pgvectorscale with StreamingDiskANN indices
3. Parallel execution of vector/FTS/trajectory scoring
4. Pre-computed embeddings for all 23,000+ candidates
5. Redis cache hits return in under 50ms

**Phase 11 Latency Budget:**
- Embedding query: 50ms
- Vector search: 100ms
- Text search: 50ms
- Scoring/filtering: 100ms
- Reranking: 200ms

---

*State initialized: 2026-01-24*
*Last updated: 2026-01-25 - Completed 11-02-PLAN.md (Connection pool tuning)*
