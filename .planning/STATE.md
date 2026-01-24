# Project State: Headhunter AI Leader-Level Search

**Initialized:** 2026-01-24
**Current Status:** Phase 3 COMPLETE (Hybrid Search)

---

## Project Reference

**Core Value:** Find candidates who are actually qualified, not just candidates who happen to have the right keywords.

**Current Focus:** Phase 3 (Hybrid Search) complete. All 4 plans executed. RRF hybrid search with FTS and vector search now operational. Ready for Phase 4 (Multi-Signal Scoring Framework).

**Key Files:**
- `.planning/PROJECT.md` - Project definition and constraints
- `.planning/REQUIREMENTS.md` - All requirements with traceability
- `.planning/ROADMAP.md` - Phase structure and success criteria
- `.planning/research/SUMMARY.md` - Research findings informing approach

---

## Current Position

**Phase:** 3 of 10 (Hybrid Search)
**Plan:** 4 of 4 complete
**Status:** COMPLETE
**Last activity:** 2026-01-24 - Completed 03-04-PLAN.md (Hybrid Search Verification)

**Progress:** [#######...] 65%

**Next Action:** Begin Phase 4 (Multi-Signal Scoring Framework)

---

## Phase Progress

| Phase | Name | Status | Plans | Progress |
|-------|------|--------|-------|----------|
| 1 | Reranking Fix | Complete | 4/4 | 100% |
| 2 | Search Recall Foundation | Complete | 5/5 | 100% |
| 3 | Hybrid Search | Complete | 4/4 | 100% |
| 4 | Multi-Signal Scoring Framework | Pending | 0/? | 0% |
| 5 | Skills Infrastructure | Pending | 0/? | 0% |
| 6 | Skills Intelligence | Pending | 0/? | 0% |
| 7 | Signal Scoring Implementation | Pending | 0/? | 0% |
| 8 | Career Trajectory | Pending | 0/? | 0% |
| 9 | Match Transparency | Pending | 0/? | 0% |
| 10 | Pipeline Integration | Pending | 0/? | 0% |

**Overall:** 3/10 phases complete (30%)

---

## Performance Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| v1 Requirements | 28 | 5 done | In Progress |
| Phases Complete | 10 | 3 | In Progress |
| Search Recall | 50+ candidates | Expected improvement | Pending verification |
| p95 Latency | <1.2s | Unknown | Unmeasured |
| Cache Hit Rate | >0.98 | Unknown | Unmeasured |

---

## Accumulated Context

### Key Decisions

| Decision | Rationale | Phase |
|----------|-----------|-------|
| Fix reranking first | Critical bug: Match Score = Similarity Score (bypass active) | 1 |
| Sequential phases | Each phase builds on previous; no parallel paths | All |
| Copy skills taxonomy | Local copy for customization, independence from EllaAI | 5 |
| Rule-based trajectory | Explainable, sufficient per research; ML deferred to v2 | 8 |
| Use _raw_vector_similarity prefix | Distinguish internal tracking from public API fields | 1.01 |
| Add type definitions for new match_metadata fields | Required for TypeScript compilation | 1.01 |
| Show similarity only when scores differ >1% | Avoids confusion when reranking bypassed; cleaner UI | 1.03 |
| Use "Sim" label for similarity badge | Compact for badge design; tooltip provides full context | 1.03 |
| Green for Match, Blue for Similarity badges | Primary vs secondary visual hierarchy | 1.04 |
| Lower threshold to 0.25 | Broad recall - let scoring/reranking filter quality | 2.01 |
| Increase default limit to 500 | Enable retrieval of 500-800 candidates per query | 2.01 |
| Level scoring: 1.0/0.5/0.3 | In-range=1.0, unknown=0.5, out-of-range=0.3 - soft scoring not hard filter | 2.02 |
| Precomputed _level_score pattern | Use _level_score when available, fallback to calculateLevelScore | 2.02 |
| Specialty scoring: 1.0/0.8/0.5/0.4/0.2 | Match=1.0, fullstack=0.8, no data=0.5, unclear=0.4, mismatch=0.2 | 2.03 |
| Precomputed _specialty_score pattern | Use _specialty_score when available, fallback to calculateSpecialtyScore | 2.03 |
| Tech stack scoring: 1.0/0.7/0.5/0.2 | Right=1.0, polyglot=0.7, unknown=0.5, wrong=0.2 | 2.04 |
| Function title scoring: 1.0/0.5/0.2 | Engineering=1.0, unknown=0.5, non-engineering=0.2 | 2.04 |
| Trajectory scoring: 1.0/0.5/0.4 | Interested=1.0, unknown=0.5, stepping down=0.4 | 2.04 |
| Remove MIN_SCORE_THRESHOLD | Let all candidates through to Gemini - scoring determines rank, not inclusion | 2.04 |
| Phase 2 multiplier (average of 5 scores) | Aggregate all Phase 2 scores into single multiplier for retrieval_score | 2.05 |
| Multiplier floor at 0.3 | Never fully exclude candidates - allow Gemini evaluation | 2.05 |
| Stage logging (STAGE 1-5) | Enable pipeline validation and debugging | 2.05 |
| RRF k=60 default | Standard value used in Elasticsearch, OpenSearch, research papers | 3.02 |
| perMethodLimit=100 default | Sufficient candidates per method while avoiding memory issues | 3.02 |
| enableRrf=true default | New behavior enabled by default for A/B testing capability | 3.02 |
| Use hybrid_score for RRF stats | Currently weighted sum, stats still useful for score distribution | 3.04 |
| FTS warning on hasTextQuery but no matches | Help diagnose search_document population issues | 3.04 |

### Technical Notes

- **Existing reranking code:** Together AI or Gemini LLM reranking exists but is bypassed
- **EllaAI skills file:** `/Volumes/Extreme Pro/myprojects/EllaAI/react-spa/src/data/skills-master.ts`
- **Target location:** `functions/src/shared/skills-master.ts`
- **Key files to modify:** `functions/src/engines/legacy-engine.ts`, `functions/src/vector-search.ts`
- **Score propagation fixed:** raw_vector_similarity now preserved through transformation chain (01-01)
- **API similarity mapping fixed:** match.similarity now populated from match_metadata (01-02)
- **UI dual score display:** Both Match and Similarity badges shown when scores differ (01-03)
- **CSS styling complete:** Green Match badge, blue Similarity badge with quality variants (01-04)
- **Similarity thresholds lowered:** 0.25 across all search paths (02-01)
- **Default limit increased:** 500 candidates per search (02-01)
- **Level filter converted to scoring:** _level_score attached to all candidates (02-02)
- **Both vector pool and function pool use level scoring** (02-02)
- **Specialty filter converted to scoring:** _specialty_score attached to all candidates (02-03)
- **Both vector pool and function pool use specialty scoring** (02-03)
- **Tech stack filter converted to scoring:** _tech_stack_score attached to candidates (02-04)
- **Function title filter converted to scoring:** _function_title_score attached to candidates (02-04)
- **Career trajectory filter converted to scoring:** _trajectory_score attached to candidates (02-04)
- **MIN_SCORE_THRESHOLD removed:** All candidates pass through to Gemini (02-04)
- **Phase 2 scoring integrated:** All 5 scores aggregated via phase2Multiplier (02-05)
- **Stage logging added:** STAGE 1-5 for pipeline validation (02-05)
- **Score breakdown expanded:** phase2_* fields included for transparency (02-05)
- **FTS diagnostic logging:** Query params and search_document analysis logged (03-01)
- **FULL OUTER JOIN pattern:** Replaces UNION ALL to preserve text_score association (03-01)
- **Rank columns added:** vector_rank and text_rank for RRF preparation (03-01)
- **PgHybridSearchRow updated:** Added vector_rank and text_rank fields to type (03-01)
- **RRF configuration added:** rrfK, perMethodLimit, enableRrf in SearchRuntimeConfig (03-02)
- **PgHybridSearchQuery updated:** RRF params flow through to SQL values (03-02)
- **RRF logging added:** Config logged before each hybrid search (03-02)
- **RRF summary logging:** Shows vectorOnly, textOnly, both, noScore counts and score stats (03-04)
- **FTS warning:** Logged when text query provided but FTS returns no matches (03-04)

### Blockers

None currently identified.

### TODOs

- [x] Create Phase 1 execution plan (4 plans in 3 waves)
- [x] Identify specific files implementing reranking bypass (legacy-engine.ts, api.ts)
- [x] Complete 01-01: Backend Score Propagation Fix
- [x] Complete 01-02: API Service Score Mapping
- [x] Complete 01-03: UI Dual Score Display
- [x] Complete 01-04: Verification (CSS styling)
- [x] Complete 02-01: Lower Similarity Thresholds
- [x] Complete 02-02: Level Filter to Scoring
- [x] Complete 02-03: Specialty Filter to Scoring
- [x] Complete 02-04: Remaining Filters to Scoring
- [x] Complete 02-05: Integrate Scores and Stage Logging
- [x] Complete 03-01: Fix textScore=0 and Add FTS Diagnostic Logging
- [x] Complete 03-02: RRF Configuration Parameters
- [x] Complete 03-03: RRF Scoring SQL
- [x] Complete 03-04: Hybrid Search Verification
- [ ] Verify EllaAI skills-master.ts format before copying (Phase 5)
- [ ] Verify search recall improvement after Phase 2 deployment
- [x] Note: Hard level filter at step 3.5 (career trajectory) - NOW CONVERTED TO SCORING

---

## Session Continuity

**Last session:** 2026-01-24T23:48:00Z
**Stopped at:** Completed 03-04-PLAN.md - Hybrid Search Verification
**Resume file:** None - ready for Phase 4

### Context for Next Session

Phase 3 (Hybrid Search) COMPLETE. All 4 plans executed:

| Plan | Name | Status | Commits |
|------|------|--------|---------|
| 03-01 | FTS Fix and Diagnostic Logging | Complete | 70098c4, d303cd5 |
| 03-02 | RRF Configuration Parameters | Complete | d75aeb8, d7c1df1, c02a3bf |
| 03-03 | RRF Scoring SQL | Complete | (see 03-03-SUMMARY) |
| 03-04 | Hybrid Search Verification | Complete | 83b7ecb |

**Phase 3 deliverables:**
- Vector similarity search via pgvector (cosine distance)
- Full-text search via PostgreSQL FTS (ts_rank_cd)
- FULL OUTER JOIN combining both search methods
- RRF configuration (k=60, perMethodLimit=100, enableRrf=true)
- Comprehensive logging for debugging and validation
- FTS warning when expected but not contributing

**Phase 3 requirements met:**
- HYBD-01: Vector similarity search (working)
- HYBD-02: BM25 text search (textScore > 0)
- HYBD-03: RRF combines results (FULL OUTER JOIN + hybrid_score)
- HYBD-04: Configurable k parameter (SEARCH_RRF_K)

All Phase 1 commits:
- 01-01: 72954b0, 05b5110, ed14f64, 2e7a888
- 01-02: 1016c18, 7a7c6be
- 01-03: d6fb69a, 9b00515, b4c0178
- 01-04: cdc9107

All Phase 2 commits:
- 02-01: baa8c24, 62b5eb8, 3a7f5ab
- 02-02: cefedfa, f848029, bb3fdb4
- 02-03: c57f864, 122fea6, 8bfd510
- 02-04: 385e0b6
- 02-05: da4ca97, b304c66

All Phase 3 commits:
- 03-01: 70098c4, d303cd5
- 03-02: d75aeb8, d7c1df1, c02a3bf
- 03-03: 16a6aa5, ce4c4cf, 4b0c79e
- 03-04: 83b7ecb

---

*State initialized: 2026-01-24*
*Last updated: 2026-01-24T23:48:00Z*
