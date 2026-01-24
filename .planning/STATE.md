# Project State: Headhunter AI Leader-Level Search

**Initialized:** 2026-01-24
**Current Status:** Phase 1 in progress

---

## Project Reference

**Core Value:** Find candidates who are actually qualified, not just candidates who happen to have the right keywords.

**Current Focus:** Fix reranking bypass bug, then systematically improve search recall and scoring.

**Key Files:**
- `.planning/PROJECT.md` - Project definition and constraints
- `.planning/REQUIREMENTS.md` - All requirements with traceability
- `.planning/ROADMAP.md` - Phase structure and success criteria
- `.planning/research/SUMMARY.md` - Research findings informing approach

---

## Current Position

**Phase:** 1 of 10 (Reranking Fix)
**Plan:** 1 of 4 complete
**Status:** In progress
**Last activity:** 2026-01-24 - Completed 01-01-PLAN.md (Backend Score Propagation Fix)

**Progress:** [#.........] 10%

**Next Action:** Execute 01-02-PLAN.md (Frontend Score Display)

---

## Phase Progress

| Phase | Name | Status | Plans | Progress |
|-------|------|--------|-------|----------|
| 1 | Reranking Fix | In Progress | 1/4 | 25% |
| 2 | Search Recall Foundation | Pending | 0/? | 0% |
| 3 | Hybrid Search | Pending | 0/? | 0% |
| 4 | Multi-Signal Scoring Framework | Pending | 0/? | 0% |
| 5 | Skills Infrastructure | Pending | 0/? | 0% |
| 6 | Skills Intelligence | Pending | 0/? | 0% |
| 7 | Signal Scoring Implementation | Pending | 0/? | 0% |
| 8 | Career Trajectory | Pending | 0/? | 0% |
| 9 | Match Transparency | Pending | 0/? | 0% |
| 10 | Pipeline Integration | Pending | 0/? | 0% |

**Overall:** 0/10 phases complete (0%)

---

## Performance Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| v1 Requirements | 28 | 0 done | Pending |
| Phases Complete | 10 | 0 | Pending |
| Search Recall | 50+ candidates | ~10 | Failing |
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

### Technical Notes

- **Existing reranking code:** Together AI or Gemini LLM reranking exists but is bypassed
- **EllaAI skills file:** `/Volumes/Extreme Pro/myprojects/EllaAI/react-spa/src/data/skills-master.ts`
- **Target location:** `functions/src/shared/skills-master.ts`
- **Key files to modify:** `functions/src/engines/legacy-engine.ts`, `functions/src/vector-search.ts`
- **Score propagation fixed:** raw_vector_similarity now preserved through transformation chain (01-01)

### Blockers

None currently identified.

### TODOs

- [x] Create Phase 1 execution plan (4 plans in 3 waves)
- [x] Identify specific files implementing reranking bypass (legacy-engine.ts, api.ts)
- [x] Complete 01-01: Backend Score Propagation Fix
- [ ] Complete 01-02: Frontend Score Display
- [ ] Complete 01-03: Reranking Integration
- [ ] Complete 01-04: Verification
- [ ] Verify EllaAI skills-master.ts format before copying (Phase 5)

---

## Session Continuity

**Last session:** 2026-01-24T22:56:52Z
**Stopped at:** Completed 01-01-PLAN.md
**Resume file:** .planning/phases/01-reranking-fix/01-02-PLAN.md

### Context for Next Session

Plan 01-01 (Backend Score Propagation Fix) is complete. The backend now preserves raw_vector_similarity through the entire transformation chain and exposes it in match_metadata alongside gemini_score.

Next: Execute 01-02-PLAN.md to update the frontend to display both Similarity Score and Match Score as separate values.

Commits from 01-01:
- 72954b0: Preserve raw vector similarity in vectorPool initialization
- 05b5110: Propagate raw similarity through candidate transformations
- ed14f64: Expose raw similarity in match_metadata and response
- 2e7a888: Add type definitions for new match_metadata fields

---

*State initialized: 2026-01-24*
*Last updated: 2026-01-24T22:56:52Z*
