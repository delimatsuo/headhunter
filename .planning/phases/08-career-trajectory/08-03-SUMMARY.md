---
phase: 08-career-trajectory
plan: 03
subsystem: search
tags: [trajectory, scoring, role-alignment, career-fit, typescript, vitest]

# Dependency graph
requires:
  - phase: 08-01
    provides: "Direction classifier with mapTitleToLevel and calculateTrajectoryDirection"
  - phase: 08-02
    provides: "Velocity and type classifiers (calculateTrajectoryVelocity, classifyTrajectoryType)"
  - phase: 07-04
    provides: "Signal integration in extractSignalScores with SignalComputationContext"
provides:
  - "calculateTrajectoryFit function with 0-1 role alignment scoring"
  - "computeTrajectoryMetrics convenience wrapper for all trajectory metrics"
  - "TrajectoryContext interface for role requirements"
  - "Trajectory fit signal integrated into extractSignalScores"
  - "Phase 8 trajectory fit computation in search scoring pipeline"
affects: [09-match-transparency, 10-pipeline-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Scoring matrices for direction+velocity combinations"
    - "Track alignment scoring (technical vs management)"
    - "Growth type modifiers (high-growth, stable, turnaround)"
    - "Career pivot handling with allowPivot flag"

key-files:
  created: []
  modified:
    - services/hh-search-svc/src/trajectory-calculators.ts
    - services/hh-search-svc/src/scoring.ts
    - services/hh-search-svc/src/trajectory-calculators.test.ts

key-decisions:
  - "Direction+velocity matrix as base score, then apply track alignment and growth modifiers"
  - "Track alignment weighted 50% with base score for balanced evaluation"
  - "High-growth roles get 1.2x modifier for fast velocity"
  - "Career pivots penalized 0.7x when allowPivot=false"
  - "Score clamped to 0-1 range to prevent modifier overflow"

patterns-established:
  - "TrajectoryContext for role-specific scoring requirements"
  - "TrajectoryMetrics for computed candidate trajectory data"
  - "Scoring matrix pattern for multi-dimensional evaluation"
  - "Growth type modifiers for context-aware scoring"

# Metrics
duration: 4min
completed: 2026-01-24
---

# Phase 8 Plan 3: Trajectory Fit Scorer Summary

**Role-aware trajectory fit scoring with direction+velocity matrices, track alignment, and growth type modifiers integrated into Phase 7 signal pipeline**

## Performance

- **Duration:** 4 minutes
- **Started:** 2026-01-25T02:20:30Z
- **Completed:** 2026-01-25T02:24:48Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Trajectory fit scorer with 0-1 role alignment scoring (TRAJ-03)
- Direction+velocity scoring matrix (upward+fast=1.0, downward=0.3)
- Track alignment scoring (technical vs management)
- Growth type modifiers (high-growth, stable, turnaround)
- Career pivot handling with allowPivot flag
- Integration into extractSignalScores with Phase 7 signals
- 54 total tests passing (39 from 08-01/08-02, 15 new for 08-03)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add trajectory fit scorer** - `bea7aba` (feat)
2. **Task 2: Integrate trajectory scoring into scoring.ts** - `b0eb10f` (feat)
3. **Task 3: Add unit tests for trajectory fit scorer** - `d0cb4c7` (test)

## Files Created/Modified

- `services/hh-search-svc/src/trajectory-calculators.ts` - Added calculateTrajectoryFit, computeTrajectoryMetrics, TrajectoryContext, TrajectoryMetrics, scoring matrices
- `services/hh-search-svc/src/scoring.ts` - Extended SignalComputationContext with Phase 8 fields, added extractTogetherAITrajectory and inferTargetTrack helpers, integrated trajectory fit into extractSignalScores
- `services/hh-search-svc/src/trajectory-calculators.test.ts` - Added 15 comprehensive tests for trajectory fit scorer

## Decisions Made

1. **Direction+velocity matrix as base score** - Start with direction+velocity combination (upward+fast=1.0, lateral+normal=0.5, downward=0.3) then apply adjustments
2. **Track alignment weighted 50%** - Balance base score and track alignment equally: `(base * 0.5) + (alignment * 0.5)`
3. **High-growth roles boost fast velocity** - 1.2x modifier for fast velocity in high-growth roles, rewards rapid progression
4. **Stable roles favor normal velocity** - 1.1x modifier for normal velocity in stable roles, rewards steady progression
5. **Career pivots penalized when not allowed** - 0.7x penalty when `allowPivot=false` to discourage career changes unless explicitly acceptable
6. **Score clamped to 0-1** - Prevent modifier overflow by clamping final score to valid range

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

**TypeScript type mismatch (CandidateExperience vs ExperienceEntry)**
- **Issue:** CandidateExperience uses `startDate?: string | Date` but ExperienceEntry expects `startDate?: string`
- **Resolution:** Added type conversion logic to handle both Date objects and strings, converting Date to ISO string
- **Impact:** Ensures compatibility between Phase 7 extractCandidateExperience and Phase 8 calculateTrajectoryVelocity

## Next Phase Readiness

Phase 8 (Career Trajectory) COMPLETE - All 3 plans finished:
- 08-01: Direction classifier (mapTitleToLevel, calculateTrajectoryDirection)
- 08-02: Velocity and type classifiers (calculateTrajectoryVelocity, classifyTrajectoryType)
- 08-03: Trajectory fit scorer and integration (calculateTrajectoryFit, extractSignalScores)

**Ready for Phase 9 (Match Transparency):**
- All trajectory signals computed and integrated into scoring pipeline
- TrajectoryFit signal available in SignalScores for transparency display
- Trajectory metrics (direction, velocity, type) computed from candidate data
- Role context (targetTrack, roleGrowthType, allowPivot) flows through SignalComputationContext

**No blockers identified.**

---
*Phase: 08-career-trajectory*
*Completed: 2026-01-24*
