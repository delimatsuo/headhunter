---
phase: 14-bias-reduction
plan: 04
subsystem: search
tags: [bias, diversity, entropy, slate-analysis, fairness, BIAS-05]

# Dependency graph
requires:
  - phase: 14-01
    provides: Anonymization types and patterns in bias module
  - phase: 14-03
    provides: Selection event logging with dimension inference
provides:
  - Slate diversity analysis after search ranking
  - Warning generation when >70% candidates from same group
  - Entropy-based diversity score (0-100)
  - API integration returning diversityAnalysis when issues detected
affects: [15-compliance-tooling, headhunter-ui, admin-dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Shannon entropy for diversity scoring
    - Dimension inference (company tier, experience band, specialty)
    - Conditional response enrichment (only include when warnings present)

key-files:
  created:
    - services/hh-search-svc/src/bias/slate-diversity.ts
    - services/hh-search-svc/src/bias/slate-diversity.test.ts
  modified:
    - services/hh-search-svc/src/bias/types.ts
    - services/hh-search-svc/src/bias/index.ts
    - services/hh-search-svc/src/routes.ts

key-decisions:
  - "70% concentration threshold for warnings (industry standard)"
  - "Three severity levels: info (70%), warning (80%), alert (90%)"
  - "Shannon entropy for diversity scoring - normalizes across dimension cardinality"
  - "Only include diversityAnalysis in response when shouldShowDiversityWarning returns true"
  - "Separate inference functions from selection-events (inferCompanyTier vs inferSelectionCompanyTier)"

patterns-established:
  - "Post-ranking analysis pattern - diversity check runs after search results ranked"
  - "Conditional response enrichment - only add optional fields when relevant"
  - "Entropy-based scoring - normalize concentration to 0-100 scale using Shannon entropy"

# Metrics
duration: 6min
completed: 2026-01-26
---

# Phase 14 Plan 04: Slate Diversity Analysis Summary

**Shannon entropy-based slate diversity analysis detecting homogeneous candidate pools with 70% concentration threshold and dimension-specific recruiter guidance**

## Performance

- **Duration:** 6 min
- **Started:** 2026-01-26T16:22:45Z
- **Completed:** 2026-01-26T16:28:34Z
- **Tasks:** 4
- **Files modified:** 5

## Accomplishments
- Diversity analysis module with 3-dimension inference (company tier, experience band, specialty)
- Warning generation with severity levels and dimension-specific suggestions
- Entropy-based diversity scoring normalized to 0-100 scale
- Search API integration with conditional diversityAnalysis response field
- 30 comprehensive unit tests (480 lines)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create slate diversity types** - `85d5511` (feat)
2. **Task 2: Implement slate diversity analysis** - `3a8aa0e` (feat)
3. **Task 3: Add slate diversity tests** - `c8b707a` (test)
4. **Task 4: Integrate diversity analysis into search API** - `5f098ba` (feat)

## Files Created/Modified

- `services/hh-search-svc/src/bias/types.ts` - Added DiversityDimension, DimensionDistribution, DiversityWarning, SlateDiversityAnalysis, DiversityConfig types
- `services/hh-search-svc/src/bias/slate-diversity.ts` - Core analysis module with inference, warning generation, and entropy scoring
- `services/hh-search-svc/src/bias/slate-diversity.test.ts` - 30 unit tests covering all functionality
- `services/hh-search-svc/src/bias/index.ts` - Updated barrel export
- `services/hh-search-svc/src/routes.ts` - Search API integration with EnrichedSearchResponse type

## Decisions Made

1. **70% concentration threshold** - Industry standard for flagging homogeneous slates, configurable via DiversityConfig
2. **Shannon entropy for scoring** - Normalizes diversity across dimensions with different cardinality, produces intuitive 0-100 score
3. **Separate inference functions** - Created inferCompanyTier, inferExperienceBand, inferSpecialty separate from selection-events versions to avoid naming conflicts
4. **Conditional response enrichment** - Only include diversityAnalysis when shouldShowDiversityWarning returns true (concentration issue OR score < 50)
5. **Three severity levels** - info (70-79%), warning (80-89%), alert (90%+) for graduated recruiter feedback

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- **Missing @hh/common mock in tests** - Tests initially failed due to Firebase config requirement in logger. Fixed by adding vi.mock('@hh/common') following pattern from anonymization.test.ts.
- **selection-events.ts already existed** - Plan referenced this file which was created in 14-03. Used separate function names (inferCompanyTier vs inferSelectionCompanyTier) to avoid export conflicts.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for:**
- Phase 15 (Compliance Tooling) can build on bias module foundation
- UI integration can display diversityAnalysis warnings to recruiters
- Admin dashboard can aggregate diversity metrics

**BIAS-05 requirement complete:**
- Slate diversity analysis runs after search results are ranked
- Warnings generated when >70% of candidates from same group
- Multiple dimensions analyzed (company tier, experience, specialty)
- Diversity indicators included in search response

---
*Phase: 14-bias-reduction*
*Completed: 2026-01-26*
