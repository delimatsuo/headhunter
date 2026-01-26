---
phase: 14
plan: 05
subsystem: headhunter-ui
tags: [react, bias-reduction, blind-hiring, diversity, ui-components]
dependency-graph:
  requires: [14-01, 14-04]
  provides: [anonymized-candidate-card, search-controls, diversity-indicator]
  affects: [15-admin-dashboard]
tech-stack:
  added: []
  patterns: [conditional-rendering, localStorage-persistence]
key-files:
  created:
    - headhunter-ui/src/components/Candidate/AnonymizedCandidateCard.tsx
    - headhunter-ui/src/components/Candidate/AnonymizedCandidateCard.css
    - headhunter-ui/src/components/Search/SearchControls.tsx
    - headhunter-ui/src/components/Search/SearchControls.css
    - headhunter-ui/src/components/Search/DiversityIndicator.tsx
    - headhunter-ui/src/components/Search/DiversityIndicator.css
  modified:
    - headhunter-ui/src/types/index.ts
    - headhunter-ui/src/components/Search/SearchResults.tsx
decisions:
  - id: use-localstorage-persistence
    rationale: Toggle state persists across page refreshes within session for consistent UX
  - id: convert-candidate-in-frontend
    rationale: Convert CandidateMatch to AnonymizedCandidate in frontend to avoid API changes
  - id: filter-company-signals
    rationale: Exclude companyPedigree and companyRelevance from anonymized signal scores
metrics:
  duration: ~4 minutes
  completed: 2026-01-26
---

# Phase 14 Plan 05: Anonymization UI Components Summary

**One-liner:** React components for blind hiring toggle and diversity warnings enabling bias-free candidate evaluation.

## What Was Built

### Task 1: Anonymized Types for UI
Added TypeScript types to `headhunter-ui/src/types/index.ts`:
- `AnonymizedCandidate` - Candidate data with PII removed for blind hiring
- `DimensionDistribution` - Distribution data for diversity dimensions
- `DiversityWarning` - Warning structure for concentration alerts
- `SlateDiversityAnalysis` - Complete slate diversity analysis data

### Task 2: AnonymizedCandidateCard Component
Created `headhunter-ui/src/components/Candidate/AnonymizedCandidateCard.tsx` (221 lines):
- Displays candidate with personally identifying information removed
- Shows skills, experience level, industries, match reasons
- Hides name, photo, company names, school names, location
- Signal score breakdown (excluding company pedigree signals)
- ML trajectory predictions in expanded view
- Privacy notice explaining anonymization purpose
- Professional purple/blue gradient blind hiring badge

### Task 3: SearchControls and DiversityIndicator Components
Created three new components and updated SearchResults:

**SearchControls** (`SearchControls.tsx`, 59 lines):
- Anonymization toggle switch with tooltip explanation
- Active badge when blind hiring mode enabled
- Description text when toggle is active

**DiversityIndicator** (`DiversityIndicator.tsx`, 116 lines):
- Displays diversity score (0-100)
- Shows warnings for concentration issues (>70% threshold)
- Expandable distribution breakdown by dimension
- Color-coded severity levels (info/warning/alert)
- Visual bar charts for dimension distributions

**SearchResults Integration**:
- Added imports for new components
- Added anonymizedView state with localStorage persistence
- Added convertToAnonymizedCandidate helper function
- Conditional rendering: AnonymizedCandidateCard vs SkillAwareCandidateCard
- DiversityIndicator shown when diversityAnalysis present in response

## Commits

| Commit | Type | Description |
|--------|------|-------------|
| 671cad1 | feat | Add anonymized types to UI |
| 2012455 | feat | Create AnonymizedCandidateCard component |
| 42a7180 | feat | Add SearchControls and DiversityIndicator components |

## Key Implementation Details

### PII Removal Strategy
The `convertToAnonymizedCandidate` function removes:
- Name and photo (not passed through)
- Company names (filtered from match reasons)
- School names (filtered from match reasons)
- Company pedigree signals (set to undefined)
- Company relevance signals (set to undefined)

Preserves:
- Skills and expertise
- Years of experience (band, not exact)
- Industry experience
- Match reasons (filtered)
- ML trajectory predictions (role-focused, not company-focused)

### Toggle Persistence
Anonymized view state stored in localStorage:
- Key: `hh_search_anonymizedView`
- Value: `'true'` or `'false'`
- Persists across page refreshes within browser session

### Diversity Indicator Behavior
- Diverse slate (score >= 60, no concentration): Shows green checkmark
- Warning (70-85% concentration): Shows yellow warning
- Alert (>85% concentration): Shows red alert
- Expandable to show dimension breakdowns with visual bars

## Deviations from Plan

None - plan executed exactly as written.

## Testing Notes

Verification performed:
- TypeScript compilation passes (`npx tsc --noEmit`)
- AnonymizedCandidateCard: 221 lines (exceeds 100 line minimum)
- All exports present (SearchControls, DiversityIndicator)
- Key links verified (anonymizedView conditional rendering in SearchResults)

## Next Phase Readiness

**Ready for:**
- Phase 14 Plan 06 (Admin bias dashboard) - can display these components
- Phase 15 (Compliance Tooling) - bias reduction UI complete

**Dependencies satisfied:**
- BIAS-01 (Resume anonymization toggle) - UI complete
- BIAS-05 (Diversity indicators) - UI complete
