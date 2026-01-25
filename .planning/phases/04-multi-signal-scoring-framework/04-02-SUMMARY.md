---
phase: 04-multi-signal-scoring-framework
plan: 02
subsystem: scoring
tags: [signal-scoring, weighted-scores, type-extension, computation-utilities, typescript]

# Dependency graph
requires:
  - phase: 04-01
    provides: SignalWeightConfig types and role-type presets
provides:
  - SignalScores interface for individual signal breakdown (0-1 normalized)
  - Extended HybridSearchRequest with signalWeights and roleType fields
  - Extended HybridSearchResultItem with signalScores, weightsApplied, roleTypeUsed fields
  - computeWeightedScore function for weighted signal combination
  - extractSignalScores function to extract scores from database rows
affects: [phase-04-03-response-enrichment, phase-07-signal-scoring-implementation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SignalScores interface for transparent score breakdown"
    - "computeWeightedScore with 0.5 default for missing signals"
    - "extractSignalScores extracts Phase 2 scores from metadata"
    - "normalizeVectorScore handles 0-100 and 0-1 scales"

key-files:
  created:
    - services/hh-search-svc/src/scoring.ts
  modified:
    - services/hh-search-svc/src/types.ts

key-decisions:
  - "SignalScores mirrors SignalWeightConfig structure (7 core + 1 optional)"
  - "Missing signals default to 0.5 (neutral) to prevent NaN scores"
  - "extractSignalScores reads from metadata._*_score fields (Phase 2 pattern)"
  - "normalizeVectorScore handles both 0-100 and 0-1 input scales"
  - "weightsApplied field enables score transparency and debugging"
  - "roleTypeUsed field tracks which preset was applied"

patterns-established:
  - "Pattern: computeWeightedScore(signals, weights) for final score"
  - "Pattern: extractSignalScores(row) for database row extraction"
  - "Pattern: completeSignalScores(partial, default) for ensuring all fields present"

# Metrics
duration: 6min
completed: 2026-01-25
---

# Phase 4 Plan 2: Scoring Implementation Summary

**Extended search types and created scoring utilities for weighted signal combination with transparent score breakdown**

## Performance

- **Duration:** 6 min
- **Started:** 2026-01-25 00:06 UTC
- **Completed:** 2026-01-25 00:12 UTC
- **Tasks:** 2 (all auto tasks completed)
- **Files created:** 1
- **Files modified:** 1

## Accomplishments

- SignalScores interface with all 7 core signals plus optional skillsMatch
- HybridSearchRequest extended with signalWeights and roleType fields
- HybridSearchResultItem extended with signalScores, weightsApplied, roleTypeUsed
- computeWeightedScore function handles all 7 signals plus optional skillsMatch
- extractSignalScores extracts Phase 2 scores from PgHybridSearchRow metadata
- normalizeVectorScore utility for 0-100/0-1 scale handling
- completeSignalScores utility for ensuring all fields present
- Missing signals default to 0.5 (neutral) preventing NaN scores

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extend HybridSearchRequest and HybridSearchResultItem types | 6fe692c | types.ts |
| 2 | Create scoring.ts computation module | 176829f | scoring.ts |

## Files Created

- `services/hh-search-svc/src/scoring.ts` - Scoring computation utilities (144 lines)
  - computeWeightedScore(): Weighted combination of all signals
  - extractSignalScores(): Extract scores from database row
  - normalizeVectorScore(): Handle 0-100/0-1 scale normalization
  - completeSignalScores(): Ensure all signal fields present

## Files Modified

- `services/hh-search-svc/src/types.ts` - Extended search types
  - Added import for SignalWeightConfig and RoleType
  - Added SignalScores interface
  - Extended HybridSearchRequest with signalWeights, roleType
  - Extended HybridSearchResultItem with signalScores, weightsApplied, roleTypeUsed

## Verification Results

All verification criteria passed:

1. **TypeScript compiles without errors:**
   - `npm run typecheck --prefix services/hh-search-svc` - SUCCESS

2. **signalWeights field in HybridSearchRequest:**
   - Confirmed: `signalWeights?: Partial<SignalWeightConfig>;`

3. **SignalScores interface defined:**
   - All 7 core signals: vectorSimilarity, levelMatch, specialtyMatch, techStackMatch, functionMatch, trajectoryFit, companyPedigree
   - Plus optional skillsMatch

4. **Import chain verified:**
   - scoring.ts imports SignalWeightConfig from signal-weights.ts
   - scoring.ts imports SignalScores, PgHybridSearchRow from types.ts

5. **Phase 2 score field names match:**
   - _level_score, _specialty_score, _tech_stack_score, _function_title_score, _trajectory_score, _company_score

## Technical Details

### SignalScores Interface

```typescript
export interface SignalScores {
  vectorSimilarity: number;  // 0-1 normalized vector score
  levelMatch: number;        // 0-1 level alignment
  specialtyMatch: number;    // 0-1 specialty match
  techStackMatch: number;    // 0-1 tech stack compatibility
  functionMatch: number;     // 0-1 function alignment
  trajectoryFit: number;     // 0-1 trajectory fit
  companyPedigree: number;   // 0-1 company pedigree
  skillsMatch?: number;      // 0-1 optional skills match
}
```

### computeWeightedScore Implementation

```typescript
export function computeWeightedScore(
  signals: Partial<SignalScores>,
  weights: SignalWeightConfig
): number {
  // Default missing signals to 0.5 (neutral)
  const vs = signals.vectorSimilarity ?? 0.5;
  const lm = signals.levelMatch ?? 0.5;
  // ... etc for all 7 signals

  let score = 0;
  score += vs * weights.vectorSimilarity;
  score += lm * weights.levelMatch;
  // ... etc for all 7 signals

  // Handle optional skillsMatch
  if (signals.skillsMatch !== undefined && weights.skillsMatch) {
    score += signals.skillsMatch * weights.skillsMatch;
  }

  return score;
}
```

### extractSignalScores Metadata Mapping

| SignalScore Field | Metadata Field | Default |
|-------------------|----------------|---------|
| vectorSimilarity | row.vector_score | 0 |
| levelMatch | metadata._level_score | 0.5 |
| specialtyMatch | metadata._specialty_score | 0.5 |
| techStackMatch | metadata._tech_stack_score | 0.5 |
| functionMatch | metadata._function_title_score | 0.5 |
| trajectoryFit | metadata._trajectory_score | 0.5 |
| companyPedigree | metadata._company_score | 0.5 |

### Request/Response Type Extensions

**HybridSearchRequest additions:**
- `signalWeights?: Partial<SignalWeightConfig>` - Override weights per-search
- `roleType?: RoleType` - Select preset ('executive', 'manager', 'ic', 'default')

**HybridSearchResultItem additions:**
- `signalScores?: SignalScores` - Individual signal breakdown
- `weightsApplied?: SignalWeightConfig` - Weights used for transparency
- `roleTypeUsed?: RoleType` - Preset that was applied

## Deviations from Plan

None - plan executed exactly as written.

## Success Criteria Met

- [x] HybridSearchRequest accepts signalWeights and roleType fields
- [x] HybridSearchResultItem includes signalScores, weightsApplied, roleTypeUsed fields
- [x] computeWeightedScore correctly computes weighted sum with missing signal defaults
- [x] extractSignalScores normalizes vector scores to 0-1 range
- [x] All TypeScript types compile without errors

## Next Phase Readiness

Ready for Plan 04-03 (Response Enrichment):
- SignalScores type available for populating response items
- computeWeightedScore ready to compute final weighted scores
- extractSignalScores ready to extract scores from database rows
- Type extensions in place for request/response signal scoring

The scoring computation module is complete. Plan 04-03 will integrate these utilities into the search flow to populate signalScores and weightsApplied in response items.

---
*Phase: 04-multi-signal-scoring-framework*
*Plan: 02*
*Completed: 2026-01-25*
