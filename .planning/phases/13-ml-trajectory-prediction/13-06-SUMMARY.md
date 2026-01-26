---
phase: 13-ml-trajectory-prediction
plan: 06
subsystem: ui
tags: [react, typescript, tailwind, mui, ml-ui-components]

# Dependency graph
requires:
  - phase: 13-03
    provides: ONNX inference engine and TrajectoryPredictor
provides:
  - MLTrajectoryPrediction TypeScript interface
  - ConfidenceIndicator component with color-coded badges
  - TrajectoryPrediction display component
  - Candidate card integration for ML predictions
affects: [13-07, ui, search-results]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Confidence-based color coding (green/yellow/red thresholds)"
    - "Graceful null handling for optional ML features"
    - "Conditional UI sections for progressive enhancement"

key-files:
  created:
    - headhunter-ui/src/components/Candidate/ConfidenceIndicator.tsx
    - headhunter-ui/src/components/Candidate/TrajectoryPrediction.tsx
  modified:
    - headhunter-ui/src/types/index.ts
    - headhunter-ui/src/components/Candidate/SkillAwareCandidateCard.tsx

key-decisions:
  - "Confidence thresholds: Green >=80%, Yellow 60-79%, Red <60%"
  - "Hireability score labels: High >=0.7, Moderate >=0.4, Lower <0.4"
  - "Warning indicator only shown for <60% confidence with uncertaintyReason"
  - "ML predictions displayed in expanded card details section"
  - "Backward compatible - cards render correctly without mlTrajectory data"

patterns-established:
  - "Confidence indicator pattern: Reusable badge component with tooltip warning for low confidence"
  - "ML feature integration: Conditional sections with graceful degradation"
  - "Icon-based visual distinction: Arrow (next role), Clock (tenure), Star (hireability)"

# Metrics
duration: 2min 32sec
completed: 2026-01-25
---

# Phase 13 Plan 06: ML Trajectory UI Components Summary

**React components display ML trajectory predictions with confidence indicators, tenure estimates, and hireability scores on candidate cards**

## Performance

- **Duration:** 2min 32sec
- **Started:** 2026-01-25T23:59:58Z
- **Completed:** 2026-01-26T00:02:30Z
- **Tasks:** 3
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments
- MLTrajectoryPrediction TypeScript interface with next role, confidence, tenure, and hireability fields
- ConfidenceIndicator component with green/yellow/red color coding and warning tooltips
- TrajectoryPrediction component displays all three predictions with icons and uncertainty banner
- Candidate card integration shows ML predictions in expanded details section
- Graceful degradation - UI works with or without ML prediction data

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend search types and create confidence indicator** - `b9a0b8b` (feat)
   - Added MLTrajectoryPrediction interface to types
   - Extended CandidateProfile with optional mlTrajectory field
   - Created ConfidenceIndicator component

2. **Task 2: Create trajectory prediction display component** - `5f0fcfd` (feat)
   - Created TrajectoryPrediction component with next role, tenure, hireability display
   - Low confidence warning banner with uncertainty reason
   - Icon-based visual design with Tailwind CSS

3. **Task 3: Integrate trajectory prediction into candidate card** - `745cf56` (feat)
   - Imported TrajectoryPrediction component
   - Added ML Trajectory section in expanded card details
   - Conditional render with backward compatibility

## Files Created/Modified
- `headhunter-ui/src/types/index.ts` - Added MLTrajectoryPrediction interface, extended CandidateProfile
- `headhunter-ui/src/components/Candidate/ConfidenceIndicator.tsx` - Color-coded confidence badge with warning state
- `headhunter-ui/src/components/Candidate/TrajectoryPrediction.tsx` - Comprehensive ML prediction display
- `headhunter-ui/src/components/Candidate/SkillAwareCandidateCard.tsx` - Integrated TrajectoryPrediction in expanded details

## Decisions Made

**Confidence color thresholds:**
- Green (>=80%): High confidence, strong prediction
- Yellow (60-79%): Medium confidence, reasonable prediction
- Red (<60%): Low confidence, show warning indicator
- Rationale: Aligns with TRAJ-07 requirement for <60% warning threshold

**Hireability score interpretation:**
- High (>=0.7): "High likelihood to join"
- Moderate (>=0.4): "Moderate likelihood"
- Lower (<0.4): "Lower likelihood"
- Rationale: Three-tier system provides actionable recruiter guidance

**UI placement:**
- Display in expanded details section after career trajectory
- Rationale: Related contextual information, doesn't clutter collapsed card view

**Graceful degradation:**
- Component returns null if no prediction data
- Conditional section in candidate card
- Rationale: Backward compatibility with existing candidates, progressive enhancement pattern

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. Build completed successfully with all TypeScript types validated.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for integration with hh-search-svc:**
- UI components ready to display ML predictions
- Types match backend TrajectoryPrediction schema
- Confidence thresholds align with ML model calibration

**Blockers:**
- None

**Next steps (Plan 07):**
- Wire hh-search-svc to call hh-trajectory-svc
- Attach mlTrajectory to search result candidates
- Shadow mode validation in production

---
*Phase: 13-ml-trajectory-prediction*
*Completed: 2026-01-25*
