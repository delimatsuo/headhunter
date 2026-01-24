# Phase 3 Plan 3: RRF Scoring SQL - Summary

**One-liner:** Implemented Reciprocal Rank Fusion (RRF) scoring in PostgreSQL, combining vector and text search results using rank-based fusion.

## Execution Results

| Task | Name | Status | Commit |
|------|------|--------|--------|
| 1 | Implement RRF scoring SQL in hybridSearch | Done | 16a6aa5 |
| 2 | Update types to include RRF fields | Done | ce4c4cf |
| 3 | Update result transformation to use RRF | Done | 4b0c79e |

**Duration:** ~15 minutes
**Completed:** 2026-01-24

## What Was Built

### RRF Scoring SQL Implementation

Added two SQL builder methods to `PgVectorClient`:

1. **`buildRrfSql()`** - RRF scoring with formula: `1/(k + vector_rank) + 1/(k + text_rank)`
   - Uses `rrf_scored` CTE for rank-based fusion
   - FULL OUTER JOIN ensures candidates from EITHER method appear (union, not intersection)
   - Results ordered by `rrf_score DESC`

2. **`buildWeightedSumSql()`** - Legacy weighted sum for A/B testing
   - Original formula: `(vectorWeight * vector_score) + (textWeight * text_score)`
   - Enables gradual rollout with `enableRrf` flag

### Conditional SQL Selection

```typescript
const sql = query.enableRrf
  ? this.buildRrfSql(filterClause)
  : this.buildWeightedSumSql(filterClause);
```

### Type Updates

**HybridSearchResultItem additions:**
- `rrfScore?: number` - Explicit RRF score when enabled
- `vectorRank?: number` - Position in vector search results (1-based)
- `textRank?: number` - Position in text search results (1-based)

**PgHybridSearchRow additions:**
- `rrf_score?: number | null` - Raw RRF score from SQL

### Debug Output

When `includeDebug: true`, response includes:
```json
{
  "debug": {
    "rrfConfig": {
      "enabled": true,
      "k": 60,
      "perMethodLimit": 100
    },
    "scoreBreakdown": [
      {
        "candidateId": "...",
        "score": 0.032,
        "vectorScore": 0.85,
        "textScore": 0.045,
        "rrfScore": 0.032,
        "vectorRank": 1,
        "textRank": 3
      }
    ]
  }
}
```

## Verification Results

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| TypeScript compiles | No errors | No errors | PASS |
| rrf_scored CTE count | 2+ | 2 | PASS |
| rrfScore in types | Present | Present | PASS |
| enableRrf in search-service | Present | Present | PASS |
| RRF formula correct | 1/(k+rank) | Implemented | PASS |

## Key Technical Details

### RRF SQL Structure

```sql
WITH vector_candidates AS (
  -- Top N by vector similarity with ROW_NUMBER()
),
text_candidates AS (
  -- Top N by FTS score with ROW_NUMBER()
),
rrf_scored AS (
  SELECT
    COALESCE(vc.candidate_id, tc.candidate_id) AS candidate_id,
    COALESCE(1.0 / ($10 + vc.vector_rank), 0) AS rrf_vector,
    COALESCE(1.0 / ($10 + tc.text_rank), 0) AS rrf_text,
    COALESCE(1.0 / ($10 + vc.vector_rank), 0) +
    COALESCE(1.0 / ($10 + tc.text_rank), 0) AS rrf_score
  FROM vector_candidates vc
  FULL OUTER JOIN text_candidates tc ON vc.candidate_id = tc.candidate_id
)
SELECT ... ORDER BY rrf_score DESC;
```

### RRF Score Interpretation

With k=60:
- Rank 1: 1/(60+1) = 0.0164
- Rank 10: 1/(60+10) = 0.0143
- Rank 100: 1/(60+100) = 0.00625

Max possible RRF score (rank 1 in both): 0.0164 + 0.0164 = 0.0328

### Why RRF?

1. **No score normalization needed** - Uses rank positions, not raw scores
2. **Robust to score scale differences** - Vector similarity (0-1) vs FTS rank (0-0.1)
3. **Industry standard** - Used by Elasticsearch, OpenSearch, Vespa
4. **Simple tuning** - Single k parameter controls top-rank favoritism

## Files Modified

| File | Changes |
|------|---------|
| `services/hh-search-svc/src/pgvector-client.ts` | Added buildRrfSql(), buildWeightedSumSql(), conditional SQL selection |
| `services/hh-search-svc/src/types.ts` | Added rrfScore, vectorRank, textRank fields |
| `services/hh-search-svc/src/search-service.ts` | Updated hydrateResult, added RRF debug output |

## Deviations from Plan

None - plan executed exactly as written.

## Dependencies for Next Plan

**Plan 03-04 (Hybrid Search Verification)** can now:
- Run end-to-end search queries with RRF enabled
- Verify RRF scores appear in results
- Compare RRF vs weighted sum performance
- Validate FULL OUTER JOIN union behavior

## A/B Testing Capability

To switch between RRF and weighted sum:
```bash
# Enable RRF (default)
export SEARCH_ENABLE_RRF=true

# Disable RRF for A/B testing
export SEARCH_ENABLE_RRF=false
```

---

*Executed by: Claude Opus 4.5*
*Plan: 03-03-PLAN.md*
