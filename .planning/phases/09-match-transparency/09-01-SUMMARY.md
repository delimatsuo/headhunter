---
phase: 09-match-transparency
plan: 01
subsystem: frontend-match-transparency
tags: [react, typescript, ui-components, signal-scores]

dependency-graph:
  requires:
    - "Phase 4: Multi-Signal Scoring Framework (SignalScores backend types)"
    - "Phase 7: Signal Scoring Implementation (Phase 7 signals)"
  provides:
    - SignalScores and SignalWeightConfig frontend types
    - SignalScoreBreakdown React component
    - API service signalScores passthrough
  affects:
    - 09-02 (SkillChip component may use SignalScores)
    - 09-03 (Card integration will use SignalScoreBreakdown)

tech-stack:
  added: []
  patterns:
    - "Type mirroring between backend/frontend"
    - "MUI Tooltip integration for hover details"
    - "CSS color coding with semantic classes"

key-files:
  created:
    - headhunter-ui/src/components/Match/SignalScoreBreakdown.tsx
    - headhunter-ui/src/components/Match/SignalScoreBreakdown.css
  modified:
    - headhunter-ui/src/types/index.ts
    - headhunter-ui/src/services/api.ts

decisions:
  - decision: "Use 3-color scheme for score visualization"
    rationale: "Green (>=70%), Yellow (40-69%), Red (<40%) aligns with industry standard traffic light patterns"
  - decision: "Show top 3 signals when collapsed"
    rationale: "Balances information density with screen real estate; sorted by score to highlight strengths"
  - decision: "Map legacy score_breakdown to SignalScores"
    rationale: "Backward compatibility with existing legacy-engine responses while supporting new hh-search-svc format"

metrics:
  duration: "3 minutes"
  completed: "2026-01-25"
---

# Phase 9 Plan 01: Signal Score Breakdown UI Summary

**One-liner:** SignalScores frontend types and breakdown component with 12-signal horizontal bars and color coding

## What Was Built

### Task 1: Frontend Type Definitions
Added SignalScores and SignalWeightConfig interfaces to `headhunter-ui/src/types/index.ts`:
- All 7 core signals (vectorSimilarity, levelMatch, specialtyMatch, techStackMatch, functionMatch, trajectoryFit, companyPedigree)
- All 5 Phase 7 signals (skillsExactMatch, skillsInferred, seniorityAlignment, recencyBoost, companyRelevance)
- Optional skillsMatch signal
- Extended CandidateMatch with signalScores, weightsApplied, roleTypeUsed fields

### Task 2: SignalScoreBreakdown Component
Created new component at `headhunter-ui/src/components/Match/`:
- Displays signal scores as horizontal progress bars
- Color coding: green (>=70%), yellow (40-69%), red (<40%)
- Expand/collapse functionality (top 3 vs all signals)
- MUI Tooltip integration showing weight applied
- Responsive design with smooth animations

### Task 3: API Integration
Updated `headhunter-ui/src/services/api.ts`:
- Added `extractSignalScoresFromBreakdown` helper function
- Maps legacy phase2_* scores to SignalScores format
- Passes through signalScores, weightsApplied, roleTypeUsed on CandidateMatch results

## Commits

| Hash | Message |
|------|---------|
| ba6b223 | feat(09-01): add SignalScores and SignalWeightConfig frontend types |
| 959c34e | feat(09-01): create SignalScoreBreakdown component |
| e87318c | feat(09-01): add signalScores passthrough in API service |

## Verification Results

| Criterion | Status |
|-----------|--------|
| Frontend types mirror backend SignalScores | PASS |
| SignalScoreBreakdown component exports correctly | PASS |
| Color coding logic (green/yellow/red) | PASS |
| TypeScript compilation passes | PASS |
| Component uses MUI Tooltip | PASS |
| Build succeeds | PASS |

## Deviations from Plan

None - plan executed exactly as written.

## Next Phase Readiness

Ready for 09-02 (SkillChip component) and 09-03 (card integration). The SignalScoreBreakdown component is standalone and ready to be integrated into SkillAwareCandidateCard.

**Files to integrate in 09-03:**
- Import SignalScoreBreakdown into SkillAwareCandidateCard
- Pass signalScores from match result to component
- Position within card layout (likely below match score badges)
