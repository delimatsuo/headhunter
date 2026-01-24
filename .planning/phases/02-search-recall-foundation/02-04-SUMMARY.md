---
phase: 02-search-recall-foundation
plan: 04
subsystem: search
tags: [scoring, filters, legacy-engine, retrieval, gemini-reranking]

# Dependency graph
requires:
  - phase: 02-01
    provides: Lowered similarity thresholds (0.25), increased default limit (500)
  - phase: 02-02
    provides: Level filter converted to _level_score
  - phase: 02-03
    provides: Specialty filter converted to _specialty_score
provides:
  - Tech stack filter converted to _tech_stack_score
  - Function title filter converted to _function_title_score
  - Career trajectory filter converted to _trajectory_score
  - MIN_SCORE_THRESHOLD removed entirely
  - Zero candidates excluded at retrieval stage
affects: [phase-3-hybrid-search, phase-4-multi-signal-scoring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Soft scoring signals (0.0-1.0) replace hard filters"
    - "All _*_score fields follow same pattern: 1.0=best, 0.5=neutral, 0.2=worst"
    - "Gemini reranking evaluates all candidates, scoring just determines rank"

key-files:
  created: []
  modified:
    - functions/src/engines/legacy-engine.ts

key-decisions:
  - "Tech stack scoring: 1.0 right, 0.7 polyglot, 0.5 unknown, 0.2 wrong"
  - "Function title scoring: 1.0 engineering, 0.5 unknown, 0.2 non-engineering"
  - "Trajectory scoring: 1.0 interested, 0.5 unknown, 0.4 stepping down"
  - "Score threshold completely removed - let Gemini evaluate all candidates"

patterns-established:
  - "Pattern: Convert .filter() to .map() with _*_score field"
  - "Pattern: 0.5 neutral score for missing/unknown data"
  - "Pattern: 0.2 minimum score (not 0.0) to allow Gemini override"

# Metrics
duration: 4min
completed: 2026-01-24
---

# Phase 2 Plan 4: Remaining Filters to Scoring Summary

**Converted tech stack, function title, and career trajectory filters to soft scoring signals, removed MIN_SCORE_THRESHOLD - zero candidates now excluded at retrieval stage**

## Performance

- **Duration:** 4 min
- **Started:** 2026-01-24T23:20:00Z
- **Completed:** 2026-01-24T23:24:15Z
- **Tasks:** 3
- **Files modified:** 1

## Accomplishments

- Tech stack filter converted: Java-only devs scored 0.2 for Node.js roles (instead of excluded)
- Function title filter converted: PMs/QAs scored 0.2 in engineering searches (instead of excluded)
- Career trajectory filter converted: Overqualified candidates scored 0.4 (instead of excluded)
- MIN_SCORE_THRESHOLD (30) completely removed - all candidates pass through to Gemini

## Task Commits

All tasks committed atomically in single commit:

1. **Task 1: Convert tech stack filter to scoring** - `385e0b6` (feat)
2. **Task 2: Convert function title exclusion to scoring** - `385e0b6` (feat)
3. **Task 3: Convert career trajectory filter + remove threshold** - `385e0b6` (feat)

## Files Modified

- `functions/src/engines/legacy-engine.ts` - All filter-to-scoring conversions

## Verification Results

All 4 verification criteria passed:

1. **All 4 remaining filters converted to scoring:**
   - `_tech_stack_score`: lines 290, 321
   - `_function_title_score`: lines 355, 364
   - `_trajectory_score`: lines 543, 552
   - Score threshold: removed at line 684

2. **TypeScript compiles:** `npm run build --prefix functions` - SUCCESS (exit 0)

3. **No exclusionary .filter() calls remain:**
   - Remaining filters are deduplication (structural) and sparse fallback (ID matching)
   - All 7 quality criteria now use scoring

4. **Console logs confirm scoring applied:**
   - Line 324: "Tech stack scoring applied (not filtered)"
   - Line 367: "Function title scoring applied (not filtered)"
   - Line 555: "Trajectory scoring applied (not filtered)"
   - Line 694: "Score threshold REMOVED - all N candidates pass through"

## Decisions Made

1. **Tech stack scoring values (1.0/0.7/0.5/0.2):**
   - Right stack only: 1.0 (ideal candidate)
   - Both stacks (polyglot): 0.7 (can adapt, valuable experience)
   - No data: 0.5 (neutral - let Gemini evaluate)
   - Wrong stack only: 0.2 (poor fit but Gemini can override)

2. **Function title scoring values (1.0/0.5/0.2):**
   - Engineering title: 1.0 (good match)
   - No title: 0.5 (neutral)
   - Non-engineering (PM, QA, etc.): 0.2 (poor fit but edge cases exist)

3. **Trajectory scoring values (1.0/0.5/0.4):**
   - Not stepping down: 1.0 (interested)
   - Unknown level: 0.5 (neutral)
   - Stepping down: 0.4 (unlikely but not impossible - startups, pivots, etc.)

4. **Complete threshold removal:**
   - MIN_SCORE_THRESHOLD = 30 was removing candidates
   - Now all candidates pass through regardless of combined score
   - Scoring determines rank, not inclusion

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all tasks completed successfully on first attempt.

## Phase 2 Completion Status

With this plan complete, Phase 2 (Search Recall Foundation) is now finished:

| Plan | Name | Status |
|------|------|--------|
| 02-01 | Lower Similarity Thresholds | Complete |
| 02-02 | Level Filter to Scoring | Complete |
| 02-03 | Specialty Filter to Scoring | Complete |
| 02-04 | Remaining Filters to Scoring | Complete |

**All 7 exclusionary criteria now converted:**

1. Similarity threshold: lowered to 0.25 (02-01)
2. Default limit: increased to 500 (02-01)
3. Level filter: `_level_score` (02-02)
4. Specialty filter: `_specialty_score` (02-03)
5. Tech stack filter: `_tech_stack_score` (02-04)
6. Function title filter: `_function_title_score` (02-04)
7. Career trajectory filter: `_trajectory_score` (02-04)
8. MIN_SCORE_THRESHOLD: removed (02-04)

## Next Phase Readiness

Phase 2 complete. System now retrieves ALL potentially relevant candidates and scores them for Gemini reranking.

**Ready for Phase 3 (Hybrid Search):**
- All filters are now soft scoring signals
- Candidates no longer excluded based on heuristics
- Gemini reranking has full candidate pool to evaluate
- Foundation set for multi-signal scoring framework

**Expected improvement:**
- Recall should increase significantly (from ~10 to 50+ candidates)
- False negatives reduced (startup CTOs, career changers, etc.)
- Precision maintained via Gemini intelligent reranking

---
*Phase: 02-search-recall-foundation*
*Completed: 2026-01-24*
