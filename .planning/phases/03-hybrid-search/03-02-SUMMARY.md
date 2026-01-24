---
phase: 03-hybrid-search
plan: 02
subsystem: search
tags: [rrf-config, hybrid-search, pgvector, configuration, search-service]

# Dependency graph
requires:
  - phase: 02
    provides: Complete Phase 2 scoring integration
provides:
  - RRF configuration parameters (rrfK, perMethodLimit, enableRrf)
  - Environment variable configuration for all RRF parameters
  - RRF parameters in PgHybridSearchQuery interface
  - RRF config logging for debugging
affects: [phase-3-plan-03-rrf-scoring-sql, phase-4-multi-signal-scoring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "RRF k parameter configurable via SEARCH_RRF_K (default 60)"
    - "perMethodLimit configurable via SEARCH_PER_METHOD_LIMIT (default 100)"
    - "enableRrf feature flag via SEARCH_ENABLE_RRF (default true)"

key-files:
  created: []
  modified:
    - services/hh-search-svc/src/config.ts
    - services/hh-search-svc/src/pgvector-client.ts
    - services/hh-search-svc/src/search-service.ts

key-decisions:
  - "rrfK default 60 (standard value used in Elasticsearch, OpenSearch)"
  - "perMethodLimit default 100 (sufficient candidates per method)"
  - "enableRrf default true (new behavior enabled by default for A/B testing capability)"
  - "Parameter $10 reserved for rrfK in SQL values array"

patterns-established:
  - "Pattern: RRF configuration flows from config -> search-service -> pgvector-client"
  - "Pattern: All RRF parameters logged for debugging before SQL execution"

# Metrics
duration: 8min
completed: 2026-01-24
---

# Phase 3 Plan 2: RRF Configuration Parameters Summary

**Added Reciprocal Rank Fusion (RRF) configuration parameters to enable A/B testing and tuning of hybrid search ranking without code changes**

## Performance

- **Duration:** 8 min
- **Started:** 2026-01-24T23:50:00Z
- **Completed:** 2026-01-24T23:58:00Z
- **Tasks:** 3 (all auto)
- **Files modified:** 3

## Accomplishments

- SearchRuntimeConfig interface includes rrfK, perMethodLimit, and enableRrf
- All parameters configurable via environment variables with sensible defaults
- PgHybridSearchQuery interface includes RRF configuration fields
- perMethodLimit now controls both vector_candidates and text_candidates LIMIT (replaces warmup-based calculation)
- RRF k parameter added to SQL values array as $10
- RRF configuration logging added for debugging

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add RRF configuration to SearchRuntimeConfig | d75aeb8 | config.ts |
| 2 | Update PgHybridSearchQuery to accept RRF config | d7c1df1 | pgvector-client.ts, search-service.ts |
| 3 | Add RRF k parameter to SQL values and logging | c02a3bf | pgvector-client.ts |

## Files Modified

- `services/hh-search-svc/src/config.ts` - SearchRuntimeConfig interface and initialization
- `services/hh-search-svc/src/pgvector-client.ts` - PgHybridSearchQuery interface, values array, logging
- `services/hh-search-svc/src/search-service.ts` - Pass RRF config to hybridSearch

## Verification Results

All verification criteria passed:

1. **TypeScript compiles:** `npm run build` - SUCCESS (exit 0)

2. **Config has RRF parameters:** grep -c "rrfK" config.ts = 2 (interface + initialization)

3. **PgHybridSearchQuery has RRF parameters:**
   ```typescript
   interface PgHybridSearchQuery {
     // ... existing fields ...
     // RRF configuration
     rrfK: number;           // RRF k parameter (default 60)
     perMethodLimit: number; // Candidates per method before fusion (default 100)
     enableRrf: boolean;     // Use RRF vs weighted sum
   }
   ```

4. **RRF logging exists:**
   ```typescript
   this.logger.info({
     rrfK: query.rrfK,
     perMethodLimit,
     enableRrf: query.enableRrf,
     limit: query.limit
   }, 'RRF config: hybrid search parameters');
   ```

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| SEARCH_RRF_K | 60 | RRF k parameter (controls top-rank favoritism) |
| SEARCH_PER_METHOD_LIMIT | 100 | Candidates retrieved per search method before fusion |
| SEARCH_ENABLE_RRF | true | Feature flag to toggle RRF vs weighted sum |

### Defaults Rationale

- **rrfK=60**: Standard value used in Elasticsearch, OpenSearch, and research papers
- **perMethodLimit=100**: Sufficient candidates per method while avoiding memory issues
- **enableRrf=true**: New default behavior, can disable for A/B testing against weighted sum

## Decisions Made

1. **Replace warmup-based prefetch with perMethodLimit:**
   - Old: `vectorLimit = Math.max(limit, Math.min(limit * warmupMultiplier, limit + 50))`
   - New: `perMethodLimit` used directly for both CTEs
   - Simpler, more predictable, directly configurable

2. **RRF k as $10 parameter:**
   - Added to SQL values array for use in Plan 03-03 (RRF scoring SQL)
   - Enables dynamic k adjustment without query changes

3. **Feature flag approach:**
   - enableRrf allows gradual rollout and A/B testing
   - Can compare RRF vs weighted sum scoring approaches

## Deviations from Plan

### [Rule 3 - Blocking] Fixed search-service.ts call site

- **Found during:** Task 2
- **Issue:** TypeScript compilation failed - search-service.ts hybridSearch call missing new RRF parameters
- **Fix:** Added rrfK, perMethodLimit, enableRrf to the hybridSearch call in search-service.ts
- **Files modified:** services/hh-search-svc/src/search-service.ts
- **Commit:** d7c1df1 (included in Task 2 commit)

## SQL Values Array Reference

After this plan, the hybridSearch values array is:

```typescript
const values: unknown[] = [
  query.tenantId,       // $1
  toSql(query.embedding), // $2
  perMethodLimit,       // $3 - used for both CTEs
  query.textQuery,      // $4
  query.vectorWeight,   // $5
  query.textWeight,     // $6
  query.minSimilarity,  // $7
  query.limit,          // $8
  query.offset,         // $9
  query.rrfK            // $10 - for RRF scoring calculation
];
```

## Next Plan Readiness

RRF configuration parameters are now in place.

**Ready for Plan 03-03 (RRF Scoring SQL):**
- rrfK parameter available as $10 in SQL values
- perMethodLimit controls CTE candidate counts
- enableRrf flag can toggle between RRF and weighted sum
- Logging will show RRF config for debugging

**Plan 03-03 will:**
- Implement RRF scoring formula: `1 / (k + rank)`
- Add row_number() to CTEs for rank calculation
- Update final scoring to use RRF when enableRrf=true

---
*Phase: 03-hybrid-search*
*Plan: 02*
*Completed: 2026-01-24*
