# Project State: Headhunter AI Leader-Level Search

**Initialized:** 2026-01-24
**Current Status:** Phase 6 COMPLETE (Skills Intelligence) - Ready for Phase 7

---

## Project Reference

**Core Value:** Find candidates who are actually qualified, not just candidates who happen to have the right keywords.

**Current Focus:** Phase 7 (Signal Scoring Implementation) - Plan 2/5 complete. All 5 signal calculators (SCOR-02 through SCOR-06) implemented.

**Key Files:**
- `.planning/PROJECT.md` - Project definition and constraints
- `.planning/REQUIREMENTS.md` - All requirements with traceability
- `.planning/ROADMAP.md` - Phase structure and success criteria
- `.planning/research/SUMMARY.md` - Research findings informing approach

---

## Current Position

**Phase:** 7 of 10 (Signal Scoring Implementation) - IN PROGRESS
**Plan:** 2 of 5 complete (07-01, 07-02)
**Status:** In progress
**Last activity:** 2026-01-25 - Completed 07-02-PLAN.md (Seniority, Recency, Company Calculators)

**Progress:** [████████░░] 78%

**Next Action:** Continue Phase 7 - Plan 07-03 (next signal scoring task)

---

## Phase Progress

| Phase | Name | Status | Plans | Progress |
|-------|------|--------|-------|----------|
| 1 | Reranking Fix | Complete | 4/4 | 100% |
| 2 | Search Recall Foundation | Complete | 5/5 | 100% |
| 3 | Hybrid Search | Complete | 4/4 | 100% |
| 4 | Multi-Signal Scoring Framework | Complete | 5/5 | 100% |
| 5 | Skills Infrastructure | Complete | 4/4 | 100% |
| 6 | Skills Intelligence | Complete | 4/4 | 100% |
| 7 | Signal Scoring Implementation | In Progress | 2/5 | 40% |
| 8 | Career Trajectory | Pending | 0/? | 0% |
| 9 | Match Transparency | Pending | 0/? | 0% |
| 10 | Pipeline Integration | Pending | 0/? | 0% |

**Overall:** 6/10 phases complete (60%)

---

## Performance Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| v1 Requirements | 28 | 14 done | In Progress |
| Phases Complete | 10 | 6 | In Progress |
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
| O(1) alias normalization via Map | ALIAS_TO_CANONICAL built at module load for hot path safety | 5.01 |
| Passthrough unknown skills | Return original input rather than throwing errors | 5.01 |
| Remove local skill normalization | Centralize in skills-service to eliminate duplication | 5.03 |
| 3+ character guard for partial matching | Prevent "go" → "Django" false matches in vector-search | 5.02 |
| Rule-based skill inference | 21 job title patterns, explainable, no ML needed | 6.02 |
| Confidence categories | highly_probable (0.85+), probable (0.65-0.84), likely (0.5-0.64) | 6.02 |
| Bidirectional transferable skills | Java->Kotlin AND Kotlin->Java explicitly defined | 6.02 |
| SkillMatchResult tracks matchType | exact/alias/related/partial for transparency | 6.03 |
| Confidence decay: candidate * expansion | Multiply candidate confidence by graph expansion confidence | 6.03 |
| Match type scoring multipliers | exact=1.0, related=0.9, inferred=0.85 | 6.03 |
| Top 5 transferable skills per candidate | Limit to prevent result bloat | 6.03 |
| Skill alias matching via getCommonAliases | Handles variations like js/javascript, k8s/kubernetes | 7.01 |
| Rule-based transferable skill scoring | 9 skill transfer rules with 0-1 transferability scores | 7.01 |
| Neutral score default (0.5) | Return 0.5 when required context missing - prevents unfair penalization | 7.01 |
| Seniority tier adjustment | FAANG +1 level, Startup -1 level - account for company quality | 7.02 |
| Recency decay rate | 0.16 per year (5-year decay to 0.2 floor) - linear decay formula | 7.02 |
| Company relevance signals | Average of target match, tier score, industry alignment | 7.02 |
| Recency boost exception | Returns 0.3 (not 0.5) when no skill data found | 7.02 |

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
- **Skills taxonomy copied:** 468 skills from EllaAI across 15 categories (05-01)
- **ALIAS_TO_CANONICAL Map:** 468+ entries for O(1) lookups (05-01)
- **Skills service created:** normalizeSkillName, skillsMatch, getSkillAliases, getCanonicalSkillId (05-01)
- **vector-search refactored:** Removed 6-entry hardcoded synonyms, uses centralized skills-service (05-02)
- **skill-aware-search refactored:** Removed local 8-entry synonym map, uses centralized skills-service (05-03)
- **Skill coverage expanded:** 8-10 → 468 skills across all search paths (05-02, 05-03)
- **Phase 5 verified complete:** All success criteria met, TypeScript compilation passing (05-04)
- **Skills inference created:** 21 job title patterns with confidence scoring (06-02)
- **Transferable skills added:** 39 rules covering language families, paradigms, domains (06-02)
- **Module exports unified:** inferSkillsFromTitle, findTransferableSkills via skills-service.ts (06-02)
- **Skill expansion integrated:** findMatchingSkill uses getCachedSkillExpansion for related matches (06-03)
- **Match type tracking:** SkillMatchResult includes matchType field for transparency (06-03)
- **Skill match details in results:** skill_match_details and transferable_opportunities returned (06-03)
- **Title-based inference in search:** extractSkillProfile infers skills from job titles (06-03)
- **calculateSeniorityAlignment:** Distance-based scoring with company tier adjustment (07-02)
- **calculateRecencyBoost:** Decay formula 1.0 - (years_since * 0.16), floor at 0.2 (07-02)
- **calculateCompanyRelevance:** Averages target match, tier score, industry alignment (07-02)
- **detectCompanyTier:** FAANG=2, Unicorn=1, Startup=0 classification (07-02)
- **areIndustriesRelated:** Industry relationship mapping for relevance scoring (07-02)

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
- [x] Complete 05-01: Skills Infrastructure Setup (EllaAI taxonomy copied)
- [x] Complete 05-02: Vector Search Integration (centralized normalization)
- [x] Complete 05-03: Skill-Aware Search Integration (centralized normalization)
- [x] Complete 05-04: Phase 5 Verification (all success criteria met)
- [x] Complete 06-01: Skill Expansion (skills-graph.ts with expandSkills, getRelatedSkillIds)
- [x] Complete 06-02: Skills Inference (21 job title patterns, 39 transferable skill rules)
- [x] Complete 06-03: Skill Graph Traversal (skill expansion in search, match metadata)
- [x] Complete 06-04: Phase 6 Verification (all 5 success criteria met)
- [ ] Verify search recall improvement after Phase 2 deployment
- [x] Note: Hard level filter at step 3.5 (career trajectory) - NOW CONVERTED TO SCORING

---

## Session Continuity

**Last session:** 2026-01-25
**Stopped at:** Completed 07-02-PLAN.md - Signal Calculators (Seniority, Recency, Company)
**Resume file:** None - continue Phase 7

### Context for Next Session

Phase 7 (Signal Scoring Implementation) IN PROGRESS. Plan 2/5 complete:

| Plan | Name | Status | Commits |
|------|------|--------|---------|
| 07-01 | Skill Signal Calculators | Complete | 45e0541, 5aa6501 |
| 07-02 | Seniority, Recency, Company Calculators | Complete | acbeb88 |
| 07-03 | (Next plan) | Pending | - |
| 07-04 | (Next plan) | Pending | - |
| 07-05 | (Next plan) | Pending | - |

**Phase 7 Plans 01-02 deliverables (COMPLETE):**
- All 5 signal calculators implemented (SCOR-02 through SCOR-06)
- `calculateSkillsExactMatch()`: SCOR-02 with alias matching
- `calculateSkillsInferred()`: SCOR-03 with 9 transferable skill rules
- `calculateSeniorityAlignment()`: SCOR-04 with company tier adjustment
- `calculateRecencyBoost()`: SCOR-05 with decay formula
- `calculateCompanyRelevance()`: SCOR-06 with multi-signal averaging
- Helper functions: detectCompanyTier, areIndustriesRelated
- All functions return 0-1 scores, 0.5 neutral when context missing

---

**Previous Phase 6 Summary:**

Phase 6 (Skills Intelligence) COMPLETE. All 4 plans finished:

| Plan | Name | Status | Commits |
|------|------|--------|---------|
| 06-01 | Skill Expansion | Complete | (see 06-01-SUMMARY.md) |
| 06-02 | Skills Inference | Complete | cab859e, f4045f8 |
| 06-03 | Skill Graph Traversal | Complete | ad67e81, cdb99b5 |
| 06-04 | Phase Verification | Complete | (no commit - verification only) |

**Phase 6 deliverables (COMPLETE):**
- Skill graph with expandSkills() and getRelatedSkillIds()
- LRU-cached skill expansion for hot paths
- Job title inference: 21 patterns, confidence scoring
- Transferable skills: 39 rules with pivot types and learning times
- Unified exports via skills-service.ts
- findMatchingSkill() uses skill graph expansion for related matches
- Skill match details returned in search results (matchType, reasoning)
- Transferable opportunities returned per candidate
- All 5 success criteria VERIFIED

---

**Previous Phase 5 Summary:**

Phase 5 (Skills Infrastructure) COMPLETE. All 4 plans finished:

| Plan | Name | Status | Commits |
|------|------|--------|---------|
| 05-01 | Skills Infrastructure Setup | Complete | 9fb960e |
| 05-02 | Vector Search Integration | Complete | 025aebf |
| 05-03 | Skill-Aware Search Integration | Complete | 074a953 |
| 05-04 | Phase Verification | Complete | (no commit - verification only) |

**Phase 5 deliverables:**
- EllaAI skills taxonomy copied: 468 skills across 15 categories
- O(1) alias normalization: ALIAS_TO_CANONICAL Map with 468+ entries
- Centralized skills service: normalizeSkillName, skillsMatch, getSkillAliases, getCanonicalSkillId
- vector-search.ts refactored: Removed 6-entry hardcoded synonyms
- skill-aware-search.ts refactored: Removed 8-entry local synonym map
- Skill coverage expanded: 8-10 → 468 skills (46.8x improvement)
- All TypeScript compilation passing
- All Phase 5 success criteria verified

---

**Previous Phase 4 Summary:**

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

All Phase 5 commits (complete):
- 05-01: 9fb960e
- 05-02: 025aebf
- 05-03: 074a953
- 05-04: (no commit - verification only)

All Phase 6 commits (complete):
- 06-01: (see 06-01-SUMMARY.md)
- 06-02: cab859e, f4045f8
- 06-03: ad67e81, cdb99b5
- 06-04: (no commit - verification only)

All Phase 7 commits (in progress):
- 07-01: 45e0541, 5aa6501
- 07-02: acbeb88

---

*State initialized: 2026-01-24*
*Last updated: 2026-01-25*
