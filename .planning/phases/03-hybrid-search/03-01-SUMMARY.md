---
phase: 03-hybrid-search
plan: 01
subsystem: search
tags: [fts-fix, hybrid-search, full-outer-join, text-score, rrf-preparation, pgvector]

# Dependency graph
requires:
  - phase: 02-05
    provides: All Phase 2 scores integrated into retrieval_score
provides:
  - FTS diagnostic logging for debugging textScore=0 issue
  - text_candidates CTE fixed with FULL OUTER JOIN pattern
  - Text scores properly contribute to hybrid search results
  - vector_rank and text_rank columns ready for RRF implementation
affects: [phase-03-02-rrf-scoring, phase-03-03-tuning]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FULL OUTER JOIN pattern for combining vector and text search results"
    - "FTS diagnostic logging before main query execution"
    - "ROW_NUMBER() OVER for rank calculation (RRF preparation)"

key-files:
  created: []
  modified:
    - services/hh-search-svc/src/pgvector-client.ts
    - services/hh-search-svc/src/types.ts

key-decisions:
  - "Use FULL OUTER JOIN instead of UNION ALL to preserve score associations"
  - "Add FTS diagnostic query before main hybrid search"
  - "Add vector_rank and text_rank for RRF preparation"
  - "Simplify scored CTE by removing GROUP BY (not needed with FULL OUTER JOIN)"

patterns-established:
  - "Pattern: FTS debug logging with parsed tsquery analysis"
  - "Pattern: FULL OUTER JOIN for merging two retrieval methods"
  - "Pattern: ROW_NUMBER() OVER for rank-based fusion preparation"

# Metrics
duration: 3min
completed: 2026-01-24
---

# Phase 3 Plan 1: Fix textScore=0 and Add FTS Diagnostic Logging Summary

**Fixed text search contribution to hybrid results via FULL OUTER JOIN and added diagnostic logging for FTS debugging**

## Performance

- **Duration:** 3 min
- **Started:** 2026-01-24T23:41:58Z
- **Completed:** 2026-01-24T23:44:37Z
- **Tasks:** 3 (all auto tasks completed)
- **Files modified:** 2

## Accomplishments

- FTS diagnostic logging added to hybridSearch function for debugging textScore=0 issues
- text_candidates CTE fixed with FULL OUTER JOIN pattern (replacing UNION ALL)
- Text scores now properly propagate through the query chain
- vector_rank and text_rank columns added for RRF preparation (Plan 03-02)
- PgHybridSearchRow type updated with new rank fields

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add FTS diagnostic logging | 70098c4 | pgvector-client.ts |
| 2 | Fix text_candidates CTE with FULL OUTER JOIN | d303cd5 | pgvector-client.ts |
| 3 | Add vector_rank and text_rank for RRF | d303cd5 | pgvector-client.ts, types.ts |

## Files Modified

- `services/hh-search-svc/src/pgvector-client.ts` - FTS logging, FULL OUTER JOIN, rank columns
- `services/hh-search-svc/src/types.ts` - Added vector_rank and text_rank to PgHybridSearchRow

## Verification Results

All verification criteria passed:

1. **TypeScript compiles without errors:**
   - `npm run build` - SUCCESS

2. **FTS diagnostic logging exists:**
   - Count: 2 logging statements
   - Line 99: "FTS debug: query parameters"
   - Line 116: "FTS debug: search_document analysis"

3. **text_candidates uses FULL OUTER JOIN pattern:**
   - Count: 1 instance
   - Pattern: `FULL OUTER JOIN text_candidates tc ON vc.candidate_id = tc.candidate_id`

4. **Both vector_rank and text_rank are computed:**
   - Count: 8 references across CTEs and SELECT
   - Lines: 218 (vector_rank in CTE), 230 (text_rank in CTE), 243/247 (combined CTE), 268/270 (scored CTE), 297/298 (final SELECT)

## Technical Details

### FTS Diagnostic Logging

Added two logging points:

```typescript
// Query parameters
this.logger.info({
  textQuery: query.textQuery,
  textQueryEmpty: !query.textQuery || query.textQuery.trim() === '',
  limit: query.limit
}, 'FTS debug: query parameters');

// FTS analysis
this.logger.info({
  ftsCheck: {
    total_candidates,
    has_fts,
    matches_query,
    parsed_query
  },
  dictionary: 'portuguese'
}, 'FTS debug: search_document analysis');
```

### FULL OUTER JOIN Pattern

**Before (UNION ALL):**
```sql
combined AS (
  SELECT candidate_id, vector_score, metadata FROM vector_candidates
  UNION ALL
  SELECT candidate_id, NULL::double precision AS vector_score, NULL::jsonb AS metadata FROM text_candidates
)
```

**After (FULL OUTER JOIN):**
```sql
combined AS (
  SELECT
    COALESCE(vc.candidate_id, tc.candidate_id) AS candidate_id,
    vc.vector_score,
    vc.vector_rank,
    vc.metadata,
    vc.updated_at,
    tc.text_score,
    tc.text_rank
  FROM vector_candidates vc
  FULL OUTER JOIN text_candidates tc ON vc.candidate_id = tc.candidate_id
)
```

### Rank Columns for RRF

```sql
-- In vector_candidates:
ROW_NUMBER() OVER (ORDER BY ce.embedding <=> $2 ASC) AS vector_rank

-- In text_candidates:
ROW_NUMBER() OVER (ORDER BY ts_rank_cd(cp.search_document, plainto_tsquery('portuguese', $4)) DESC) AS text_rank
```

## Deviations from Plan

None - plan executed exactly as written.

## Why This Fixes textScore=0

The UNION ALL approach had two problems:

1. **Lost association:** Text candidates were added with `NULL` vector_score but the text_score from the CTE wasn't being passed through
2. **Duplicate candidates:** Same candidate could appear twice (once from vector, once from text) but GROUP BY with MAX() didn't properly merge the text_score

With FULL OUTER JOIN:
- Each candidate appears exactly once
- Both vector_score and text_score are preserved from their respective CTEs
- No GROUP BY needed - the join handles deduplication
- COALESCE ensures candidates from either method are included

## Next Phase Readiness

Ready for Plan 03-02 (RRF Scoring Implementation):
- vector_rank and text_rank columns are now available
- Rank positions are computed using ROW_NUMBER() OVER
- RRF formula can now be applied: `1/(k + vector_rank) + 1/(k + text_rank)`

---
*Phase: 03-hybrid-search*
*Plan: 01*
*Completed: 2026-01-24*
