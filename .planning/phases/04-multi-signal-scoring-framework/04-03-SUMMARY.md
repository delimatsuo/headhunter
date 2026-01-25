---
phase: 04-multi-signal-scoring-framework
plan: 03
subsystem: search-service
tags: [signal-scoring, search-integration, response-enrichment, weighted-scoring, typescript]

# Dependency graph
requires:
  - phase: 04-01
    provides: SignalWeightConfig types and role-type presets
  - phase: 04-02
    provides: SignalScores interface and scoring computation utilities
provides:
  - Signal weight resolution in hybridSearch flow
  - Weighted score computation from extracted signals
  - Response enrichment with signalScores, weightsApplied, roleTypeUsed
  - Debug output with signalScoringConfig and per-candidate breakdown
  - Logging of roleType and avgWeightedScore
affects: [phase-05-skills-infrastructure, phase-07-signal-scoring-implementation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "resolveWeights() called at search start for weight resolution"
    - "extractSignalScores() + computeWeightedScore() in hydrateResult"
    - "Signal scoring metadata in response for transparency"
    - "Debug output includes signalScoringConfig and per-candidate signals"

key-files:
  created: []
  modified:
    - services/hh-search-svc/src/search-service.ts

key-decisions:
  - "Resolve weights early in hybridSearch for consistent application"
  - "Pass resolvedWeights and roleType to hydrateResult"
  - "Use weighted score as base, then apply skill coverage and confidence modifiers"
  - "Clamp final hybridScore to 0-1 range"
  - "Firestore fallback uses completeSignalScores with 0.5 neutral defaults"
  - "Response metadata includes signalWeights config"
  - "Debug output shows signalScoringConfig with requestOverrides"

patterns-established:
  - "Pattern: Signal weight resolution at search entry point"
  - "Pattern: Signal scores included in every search result item"
  - "Pattern: avgWeightedScore in completion log for monitoring"

# Metrics
duration: 8min
completed: 2026-01-25
---

# Phase 4 Plan 3: Response Enrichment Summary

**Integrated signal weight resolution and weighted scoring into SearchService with full transparency in response metadata and debug output**

## Performance

- **Duration:** 8 min
- **Started:** 2026-01-25 03:09 UTC
- **Completed:** 2026-01-25 03:17 UTC
- **Tasks:** 3 (all auto tasks completed)
- **Files modified:** 1

## Accomplishments

- Signal weight resolution from request.signalWeights or roleType defaults at search start
- Weights logged for debugging with requestId and roleType
- hydrateResult updated to accept resolvedWeights and roleType parameters
- Signal scores extracted from database rows via extractSignalScores
- Weighted score computed via computeWeightedScore with modifiers applied
- signalScores, weightsApplied, roleTypeUsed included in all result items
- Firestore fallback includes neutral signal scores (0.5 defaults)
- Response metadata includes signalWeights configuration
- Debug output enhanced with signalScoringConfig and per-candidate signal breakdown
- Completion log includes roleType and avgWeightedScore for monitoring

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1-2 | Signal weight resolution and weighted scoring | 1df4394 | search-service.ts |
| 3 | Response metadata and debug output | 21accd5 | search-service.ts |

## Files Modified

- `services/hh-search-svc/src/search-service.ts` - Integrated signal scoring (45 lines added)
  - Added imports for signal-weights and scoring utilities
  - Signal weight resolution after limit/offset parsing
  - Updated hydrateResult signature with resolvedWeights, roleType
  - extractSignalScores + normalizeVectorScore for signal extraction
  - computeWeightedScore for weighted score computation
  - Skill coverage boost and confidence penalty applied to weighted score
  - Clamped hybridScore to 0-1 range
  - signalScores, weightsApplied, roleTypeUsed in return object
  - Firestore fallback with completeSignalScores(0.5)
  - Response metadata includes signalWeights config
  - Debug output includes signalScoringConfig and per-candidate signals
  - Completion log includes roleType and avgWeightedScore

## Verification Results

All verification criteria passed:

1. **TypeScript compiles without errors:**
   - `npm run typecheck --prefix services/hh-search-svc` - SUCCESS

2. **resolveWeights imported and used:**
   ```typescript
   import { resolveWeights, type SignalWeightConfig, type RoleType } from './signal-weights';
   const resolvedWeights = resolveWeights(request.signalWeights, roleType);
   ```

3. **signalScores field in results:**
   - extractSignalScores(row) called in hydrateResult
   - signalScores included in return object

4. **computeWeightedScore used:**
   - `const weightedScore = computeWeightedScore(signalScores, resolvedWeights);`

5. **signalScoringConfig in debug output:**
   - Includes roleType, weightsApplied, requestOverrides

6. **avgWeightedScore in logging:**
   - Computed from response.results and logged with completion message

## Technical Details

### Signal Weight Resolution Flow

```typescript
// At search start, after limit/offset parsing
const roleType: RoleType = request.roleType ?? 'default';
const resolvedWeights = resolveWeights(request.signalWeights, roleType);

this.logger.info(
  { requestId: context.requestId, roleType, weightsApplied: resolvedWeights },
  'Signal weights resolved for search.'
);
```

### hydrateResult Signal Scoring

```typescript
private hydrateResult(
  row: PgHybridSearchRow,
  request: HybridSearchRequest,
  resolvedWeights: SignalWeightConfig,
  roleType: RoleType
): HybridSearchResultItem {
  // Extract and normalize signal scores from row
  const signalScores = extractSignalScores(row);
  signalScores.vectorSimilarity = normalizeVectorScore(row.vector_score);

  // Compute weighted score from signals
  const weightedScore = computeWeightedScore(signalScores, resolvedWeights);

  // Apply existing modifiers (skill coverage, confidence)
  let hybridScore = weightedScore;
  if (coverage > 0) hybridScore += coverage * 0.1;
  if (confidence < confidenceFloor) hybridScore *= 0.9;
  hybridScore = Math.max(0, Math.min(1, hybridScore));

  return {
    // ... existing fields
    signalScores,
    weightsApplied: resolvedWeights,
    roleTypeUsed: roleType
  };
}
```

### Response Metadata Structure

```typescript
metadata: {
  vectorWeight: config.search.vectorWeight,
  textWeight: config.search.textWeight,
  minSimilarity: config.search.minSimilarity,
  signalWeights: {
    roleType,
    weightsApplied: resolvedWeights
  }
}
```

### Debug Output Structure

```typescript
debug: {
  candidateCount: ranked.length,
  filtersApplied: request.filters,
  minSimilarity: config.search.minSimilarity,
  rrfConfig: { enabled, k, perMethodLimit },
  signalScoringConfig: {
    roleType,
    weightsApplied: resolvedWeights,
    requestOverrides: request.signalWeights ?? null
  },
  scoreBreakdown: ranked.slice(0, 5).map(r => ({
    candidateId: r.candidateId,
    score: r.score,
    vectorScore: r.vectorScore,
    textScore: r.textScore,
    rrfScore: r.rrfScore,
    vectorRank: r.vectorRank,
    textRank: r.textRank,
    signalScores: r.signalScores
  }))
}
```

### Completion Log

```typescript
this.logger.info(
  {
    requestId: context.requestId,
    tenantId: context.tenant.id,
    timings,
    resultCount: response.results.length,
    roleType,
    avgWeightedScore: response.results.length > 0
      ? (response.results.reduce((sum, r) => sum + r.score, 0) / response.results.length).toFixed(3)
      : 0
  },
  'Hybrid search with signal scoring completed.'
);
```

## Deviations from Plan

None - plan executed exactly as written.

## Success Criteria Met

- [x] SCOR-01: vectorSimilarity is normalized to 0-1 and included in signalScores
- [x] SCOR-07: Weights are resolved from request.signalWeights or role-type defaults
- [x] SCOR-08: Final score is computed as weighted combination via computeWeightedScore
- [x] Response includes signalScores, weightsApplied, roleTypeUsed for transparency
- [x] Debug output shows signal scoring configuration and per-candidate breakdown

## Next Phase Readiness

Phase 4 (Multi-Signal Scoring Framework) is now COMPLETE:

- Plan 04-01: SignalWeightConfig types and role-type presets
- Plan 04-02: SignalScores interface and scoring utilities
- Plan 04-03: SearchService integration (this plan)

Ready for Phase 5 (Skills Infrastructure):
- Signal scoring framework fully operational
- All search results include signal breakdowns
- Weights can be customized per-search or via role-type presets
- skillsMatch signal slot reserved for skill-aware searches

---
*Phase: 04-multi-signal-scoring-framework*
*Plan: 03*
*Completed: 2026-01-25*
