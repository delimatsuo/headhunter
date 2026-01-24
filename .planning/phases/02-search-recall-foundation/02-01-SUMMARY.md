# Phase 2 Plan 1: Lower Similarity Thresholds Summary

**One-liner:** Lowered vector similarity thresholds from 0.5-0.7 to 0.25 across all search paths for broad candidate retrieval.

---

## Execution Overview

| Attribute | Value |
|-----------|-------|
| Plan | 02-01 |
| Phase | 02-search-recall-foundation |
| Type | execute |
| Status | Complete |
| Duration | ~79 seconds |
| Completed | 2026-01-24 |

---

## Changes Made

### Task 1: Lower VectorSearchService threshold
**Commit:** `baa8c24`
**File:** `functions/src/vector-search.ts`

Changes:
- Line 463: Changed `similarityThreshold = 0.5` to `similarityThreshold = 0.25`
- Line 464: Changed default limit from `100` to `500` candidates
- Line 647: Updated Firestore fallback path to match (limit `100` to `500`)

### Task 2: Lower PgVectorClient default threshold
**Commit:** `62b5eb8`
**File:** `functions/src/pgvector-client.ts`

Changes:
- Line 331: Changed default parameter from `similarityThreshold: number = 0.7` to `similarityThreshold: number = 0.25`
- Added debug logging: `[PgVectorClient] searchSimilar: threshold=${similarityThreshold}, maxResults=${maxResults}`

### Task 3: Lower hh-search-svc config threshold
**Commit:** `3a7f5ab`
**File:** `services/hh-search-svc/src/config.ts`

Changes:
- Line 236: Changed default from `0.45` to `0.25` for `SEARCH_MIN_SIMILARITY`

---

## Verification Results

| Check | Status | Details |
|-------|--------|---------|
| Threshold 0.25 in vector-search.ts | PASS | Line 463 |
| Threshold 0.25 in pgvector-client.ts | PASS | Line 331 |
| Threshold 0.25 in config.ts | PASS | Line 236 |
| Default limit 500 in vector-search.ts | PASS | Lines 464, 647 |
| Services TypeScript compilation | PASS | `npm run typecheck --prefix services` |
| Functions TypeScript compilation | PASS | `npx tsc --noEmit` |
| No hardcoded high thresholds | PASS | `grep -rn "similarityThreshold.*0\.[5-9]"` returns no results |

---

## Artifacts

### Files Modified
- `functions/src/vector-search.ts`
- `functions/src/pgvector-client.ts`
- `services/hh-search-svc/src/config.ts`

### Commits
| Hash | Message |
|------|---------|
| baa8c24 | feat(02-01): lower VectorSearchService threshold |
| 62b5eb8 | feat(02-01): lower PgVectorClient default threshold |
| 3a7f5ab | feat(02-01): lower hh-search-svc config threshold |

---

## Deviations from Plan

None - plan executed exactly as written.

---

## Runtime Configuration

The `SEARCH_MIN_SIMILARITY` environment variable can still override the threshold at runtime:
```bash
# Override to use a different threshold
export SEARCH_MIN_SIMILARITY=0.30
```

---

## Expected Impact

With these changes:
- Vector search will now retrieve candidates with similarity scores as low as 0.25 (was 0.5-0.7)
- Default limit increased to 500 candidates per search (was 100)
- More candidates will reach the scoring/reranking stages where Gemini AI evaluates match quality
- Expected retrieval: 500-800 candidates per typical query (was ~300)

---

## Next Steps

- Deploy changes to verify retrieval improvement
- Monitor search latency with increased candidate pool
- Proceed to 02-02-PLAN.md when ready for next phase task
