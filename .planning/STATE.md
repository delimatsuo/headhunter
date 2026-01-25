# Project State: Headhunter AI Leader-Level Search

**Initialized:** 2026-01-24
**Current Status:** Phase 4 COMPLETE (Multi-Signal Scoring Framework)

---

## Project Reference

**Core Value:** Find candidates who are actually qualified, not just candidates who happen to have the right keywords.

**Current Focus:** Phase 4 (Multi-Signal Scoring Framework) COMPLETE AND VERIFIED. All 5 plans finished - SignalWeightConfig types, role-type presets, scoring utilities, response enrichment, API layer with module exports, and verification. Ready for Phase 5 (Skills Infrastructure).

**Key Files:**
- `.planning/PROJECT.md` - Project definition and constraints
- `.planning/REQUIREMENTS.md` - All requirements with traceability
- `.planning/ROADMAP.md` - Phase structure and success criteria
- `.planning/research/SUMMARY.md` - Research findings informing approach

---

## Current Position

**Phase:** 4 of 10 (Multi-Signal Scoring Framework) - COMPLETE AND VERIFIED
**Plan:** 5 of 5 complete
**Status:** Phase Complete and Verified
**Last activity:** 2026-01-25 - Completed 04-05-PLAN.md (Verification)

**Progress:** [########..] 76%

**Next Action:** Begin Phase 5 (Skills Infrastructure)

---

## Phase Progress

| Phase | Name | Status | Plans | Progress |
|-------|------|--------|-------|----------|
| 1 | Reranking Fix | Complete | 4/4 | 100% |
| 2 | Search Recall Foundation | Complete | 5/5 | 100% |
| 3 | Hybrid Search | Complete | 4/4 | 100% |
| 4 | Multi-Signal Scoring Framework | Complete | 5/5 | 100% |
| 5 | Skills Infrastructure | Pending | 0/? | 0% |
| 6 | Skills Intelligence | Pending | 0/? | 0% |
| 7 | Signal Scoring Implementation | Pending | 0/? | 0% |
| 8 | Career Trajectory | Pending | 0/? | 0% |
| 9 | Match Transparency | Pending | 0/? | 0% |
| 10 | Pipeline Integration | Pending | 0/? | 0% |

**Overall:** 4/10 phases complete (40%)

---

## Performance Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| v1 Requirements | 28 | 12 done | In Progress |
| Phases Complete | 10 | 4 | In Progress |
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
| 7 core signals in SignalWeightConfig | vectorSimilarity, levelMatch, specialtyMatch, techStackMatch, functionMatch, trajectoryFit, companyPedigree | 4.01 |
| Optional skillsMatch signal | Reserved for skill-aware searches (Phase 6) | 4.01 |
| Executive preset: function/pedigree weighted | Function (0.25) and companyPedigree (0.20) matter most for exec searches | 4.01 |
| IC preset: specialty/techStack weighted | Specialty (0.20) and techStack (0.20) matter most for IC searches | 4.01 |
| GEMINI_BLEND_WEIGHT default 0.7 | Rerank score blending weight configurable | 4.01 |
| SignalScores mirrors SignalWeightConfig | Same 7 core signals + optional skillsMatch | 4.02 |
| Missing signals default to 0.5 | Neutral value prevents NaN scores | 4.02 |
| extractSignalScores reads Phase 2 metadata | Uses _*_score fields from metadata object | 4.02 |
| normalizeVectorScore handles both scales | 0-100 and 0-1 input normalization | 4.02 |
| weightsApplied field for transparency | Enables debugging which weights were used | 4.02 |
| Schema validation for signal weights | 0-1 range, enum for roleType | 4.04 |
| Module exports from index.ts | Enable external consumers (tests, other services) | 4.04 |

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
- **SignalWeightConfig created:** 7 core signals + optional skillsMatch (04-01)
- **ROLE_WEIGHT_PRESETS:** executive, manager, ic, default with appropriate weight distributions (04-01)
- **Signal weight env vars:** SIGNAL_WEIGHT_* for default customization (04-01)
- **normalizeWeights():** Ensures weights sum to 1.0 (04-01)
- **resolveWeights():** Merges request overrides with role presets (04-01)
- **getSignalWeightDefaults():** Returns env-configured defaults (04-01)
- **SignalScores interface:** All 7 core signals + optional skillsMatch (04-02)
- **computeWeightedScore():** Computes final weighted score from signals (04-02)
- **extractSignalScores():** Extracts Phase 2 scores from PgHybridSearchRow (04-02)
- **normalizeVectorScore():** Handles 0-100/0-1 scale normalization (04-02)
- **completeSignalScores():** Ensures all signal fields present (04-02)
- **HybridSearchRequest extended:** signalWeights, roleType fields added (04-02)
- **HybridSearchResultItem extended:** signalScores, weightsApplied, roleTypeUsed fields added (04-02)
- **Signal weight integration:** Weights resolved and applied in hybridSearch() (04-03)
- **Response enrichment:** signalScores returned in search results (04-03)
- **API schema validation:** signalWeights (0-1), roleType enum in schemas.ts (04-04)
- **Module exports:** signal-weights, scoring, types exported from index.ts (04-04)

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
- [x] Complete 04-01: SignalWeightConfig Types and Role-Type Presets
- [x] Complete 04-02: Scoring Implementation
- [x] Complete 04-03: Response Enrichment
- [x] Complete 04-04: API Layer and Module Exports
- [x] Complete 04-05: Verification (build/compile/exports verified)
- [ ] Verify EllaAI skills-master.ts format before copying (Phase 5)
- [ ] Verify search recall improvement after Phase 2 deployment
- [x] Note: Hard level filter at step 3.5 (career trajectory) - NOW CONVERTED TO SCORING

---

## Session Continuity

**Last session:** 2026-01-25
**Stopped at:** Completed 04-05-PLAN.md - Verification
**Resume file:** None - ready for Phase 5

### Context for Next Session

Phase 4 (Multi-Signal Scoring Framework) COMPLETE AND VERIFIED. All 5 plans finished:

| Plan | Name | Status | Commits |
|------|------|--------|---------|
| 04-01 | SignalWeightConfig Types | Complete | a6d048a, 724c3d6 |
| 04-02 | Scoring Implementation | Complete | 6fe692c, 176829f |
| 04-03 | Response Enrichment | Complete | 1df4394, 21accd5 |
| 04-04 | API Layer and Module Exports | Complete | 10dc61a, 6b2d3bc |
| 04-05 | Verification | Complete | (no commit - verification only) |

**Phase 4 deliverables:**
- SignalWeightConfig type with 7 core signals + optional skillsMatch
- Role-type presets (executive, manager, ic, default)
- Weight resolution merging request overrides with presets
- computeWeightedScore() for weighted signal combination
- extractSignalScores() to extract Phase 2 scores from database rows
- signalScores, weightsApplied, roleTypeUsed in search results
- API schema validation for signalWeights (0-1 range) and roleType enum
- Module exports for external consumers (tests, other services)

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

All Phase 4 commits:
- 04-01: a6d048a, 724c3d6
- 04-02: 6fe692c, 176829f
- 04-03: 1df4394, 21accd5
- 04-04: 10dc61a, 6b2d3bc
- 04-05: (no commit - verification only)

---

*State initialized: 2026-01-24*
*Last updated: 2026-01-25*
