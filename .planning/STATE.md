# Project State: Headhunter AI Leader-Level Search

**Initialized:** 2026-01-24
**Current Status:** Phase 2 in progress

---

## Project Reference

**Core Value:** Find candidates who are actually qualified, not just candidates who happen to have the right keywords.

**Current Focus:** Phase 2 - Search Recall Foundation. Completed 02-01 (Lower Similarity Thresholds).

**Key Files:**
- `.planning/PROJECT.md` - Project definition and constraints
- `.planning/REQUIREMENTS.md` - All requirements with traceability
- `.planning/ROADMAP.md` - Phase structure and success criteria
- `.planning/research/SUMMARY.md` - Research findings informing approach

---

## Current Position

**Phase:** 2 of 10 (Search Recall Foundation) - IN PROGRESS
**Plan:** 1 of ? complete
**Status:** In progress
**Last activity:** 2026-01-24 - Completed 02-01-PLAN.md (Lower Similarity Thresholds)

**Progress:** [####......] 40%

**Next Action:** Execute next Phase 2 plan

---

## Phase Progress

| Phase | Name | Status | Plans | Progress |
|-------|------|--------|-------|----------|
| 1 | Reranking Fix | Complete | 4/4 | 100% |
| 2 | Search Recall Foundation | In Progress | 1/? | ~25% |
| 3 | Hybrid Search | Pending | 0/? | 0% |
| 4 | Multi-Signal Scoring Framework | Pending | 0/? | 0% |
| 5 | Skills Infrastructure | Pending | 0/? | 0% |
| 6 | Skills Intelligence | Pending | 0/? | 0% |
| 7 | Signal Scoring Implementation | Pending | 0/? | 0% |
| 8 | Career Trajectory | Pending | 0/? | 0% |
| 9 | Match Transparency | Pending | 0/? | 0% |
| 10 | Pipeline Integration | Pending | 0/? | 0% |

**Overall:** 1/10 phases complete (10%)

---

## Performance Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| v1 Requirements | 28 | 1 done | In Progress |
| Phases Complete | 10 | 1 | In Progress |
| Search Recall | 50+ candidates | ~10 (pre-02-01) | Pending verification |
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
- [ ] Verify EllaAI skills-master.ts format before copying (Phase 5)
- [ ] Verify search recall improvement after 02-01 deployment

---

## Session Continuity

**Last session:** 2026-01-24T23:17:00Z
**Stopped at:** Completed 02-01-PLAN.md
**Resume file:** None - ready for next Phase 2 plan

### Context for Next Session

Phase 2 Plan 1 (Lower Similarity Thresholds) complete. Changes made:

1. **functions/src/vector-search.ts:** threshold 0.5 -> 0.25, limit 100 -> 500
2. **functions/src/pgvector-client.ts:** default threshold 0.7 -> 0.25, added debug logging
3. **services/hh-search-svc/src/config.ts:** minSimilarity default 0.45 -> 0.25

All TypeScript compilation passes. SEARCH_MIN_SIMILARITY env var can override at runtime.

Commits from 02-01:
- baa8c24: feat(02-01): lower VectorSearchService threshold
- 62b5eb8: feat(02-01): lower PgVectorClient default threshold
- 3a7f5ab: feat(02-01): lower hh-search-svc config threshold

All Phase 1 commits:
- 01-01: 72954b0, 05b5110, ed14f64, 2e7a888
- 01-02: 1016c18, 7a7c6be
- 01-03: d6fb69a, 9b00515, b4c0178
- 01-04: cdc9107

---

*State initialized: 2026-01-24*
*Last updated: 2026-01-24T23:17:00Z*
