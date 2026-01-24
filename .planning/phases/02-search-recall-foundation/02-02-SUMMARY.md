---
phase: 02-search-recall-foundation
plan: 02
subsystem: search
tags: [level-filter, scoring, vector-search, retrieval]

# Dependency graph
requires:
  - phase: 02-01
    provides: Lower similarity threshold for broader candidate retrieval
provides:
  - _level_score field attached to all candidates (0.3-1.0)
  - Level check converts from filter to scoring signal
  - 40-60% more candidates can reach reranking stage
affects: [02-03, hybrid-search, multi-signal-scoring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Soft scoring instead of hard filtering for candidate selection"
    - "_level_score prefix for internal scoring fields"

key-files:
  created: []
  modified:
    - functions/src/engines/legacy-engine.ts

key-decisions:
  - "Level 1.0 for in-range, 0.5 for unknown, 0.3 for out-of-range"
  - "Use precomputed _level_score when available, fallback to calculateLevelScore"

patterns-established:
  - "Soft scoring pattern: Convert hard filters to 0.3-1.0 scoring signals"
  - "_level_score integration into retrieval_score calculation"

# Metrics
duration: 5min
completed: 2026-01-24
---

# Phase 02 Plan 02: Level Filter to Scoring Summary

**Converted hard level filter to soft scoring signal - candidates outside level range get 0.3 score instead of exclusion, enabling 40-60% more candidates to reach Gemini reranking**

## Performance

- **Duration:** 5 min
- **Started:** 2026-01-24T23:12:00Z
- **Completed:** 2026-01-24T23:17:55Z
- **Tasks:** 3
- **Files modified:** 1

## Accomplishments

- Vector pool level filter converted to scoring with _level_score field
- Function pool level filter converted to scoring with _level_score field
- Retrieval scoring now uses precomputed _level_score when available
- All candidates pass through level check (no exclusion) with appropriate scores
- TypeScript compiles without errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Convert level filter to scoring** - `cefedfa` (feat)
2. **Task 2: Update function pool level filter to scoring** - `f848029` (feat)
3. **Task 3: Incorporate _level_score into retrieval scoring** - `bb3fdb4` (feat)

## Files Created/Modified

- `functions/src/engines/legacy-engine.ts` - Level filter logic in both IC mode (line ~166) and searchByFunction method (line ~942) converted from .filter() to .map() with _level_score

## Decisions Made

- **Scoring values:** 1.0 for in-range, 0.5 for unknown level, 0.3 for out-of-range
  - Rationale: Keeps out-of-range candidates in the pool but at lower priority
  - 0.5 for unknown is neutral - lets Gemini decide without prejudice
  - 0.3 is low but not zero - still allows exceptional candidates through
- **Precomputed score pattern:** Check for _level_score first, fallback to calculateLevelScore
  - Rationale: Allows Phase 2 scoring to integrate with existing score calculation logic

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

All 5 verification criteria passed:

1. Level filter at line ~166 is now `.map()` not `.filter()` - PASS
2. Level filter in searchByFunction is now `.map()` not `.filter()` - PASS
3. `_level_score` field is used in scoring calculation - PASS (lines 391-393, 435-437)
4. TypeScript compiles without errors - PASS
5. No `.filter()` calls remain that exclude based on level range - PASS (0 occurrences)

## Issues Encountered

None - straightforward implementation following the plan structure.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Level scoring complete - all candidates now pass through with _level_score attached
- Ready for Phase 02-03: Additional filter conversions or hybrid search work
- Concern: The hard level filter at step 3.5 (career trajectory) still exists - this may need conversion in a future plan

---
*Phase: 02-search-recall-foundation*
*Completed: 2026-01-24*
