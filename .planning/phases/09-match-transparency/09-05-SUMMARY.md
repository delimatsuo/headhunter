# Phase 9 Plan 05: Match Rationale Generation Summary

## Execution Details

| Attribute | Value |
|-----------|-------|
| Phase | 09-match-transparency |
| Plan | 05 |
| Type | execute |
| Status | Complete |
| Duration | ~5 minutes |
| Completed | 2026-01-25 |

## One-Liner

LLM-generated match rationales for top candidates via Together AI with Redis caching (24h TTL).

## What Was Built

### 1. MatchRationale Type Definition (Task 1)

Added `MatchRationale` interface to both services:

**services/hh-rerank-svc/src/types.ts:**
```typescript
export interface MatchRationale {
  summary: string;          // 2-3 sentence match explanation
  keyStrengths: string[];   // Top 2-3 key strengths
  signalHighlights: Array<{ // Which signals drove the match
    signal: string;
    score: number;
    reason: string;
  }>;
}
```

**services/hh-search-svc/src/types.ts:**
- Added same `MatchRationale` interface
- Extended `HybridSearchResultItem` with optional `matchRationale` field
- Added `includeMatchRationale` and `rationaleLimit` to `HybridSearchRequest`

### 2. Together Client Extension (Task 2)

**services/hh-rerank-svc/src/together-client.ts:**
- Added `generateMatchRationale()` method for LLM rationale generation
- Temperature 0.7 for creative but coherent output
- Max 300 tokens for concise rationales
- JSON response format for reliable parsing
- Graceful fallback on errors (returns empty rationale)
- Input truncation to prevent context overflow

### 3. Rerank Service Endpoint (Task 3)

**services/hh-rerank-svc/src/routes.ts:**
- Added `POST /v1/search/rationale` endpoint
- Request validation via `matchRationaleSchema`
- Delegates to TogetherClient.generateMatchRationale()

**services/hh-rerank-svc/src/schemas.ts:**
- Added `matchRationaleSchema` for request/response validation

### 4. Search Service Integration (Task 3)

**services/hh-search-svc/src/rerank-client.ts:**
- Added `MatchRationale` and `MatchRationaleRequest` interfaces
- Added `generateMatchRationale()` method to call rerank service

**services/hh-search-svc/src/search-service.ts:**
- Integrated rationale generation into `hybridSearch()` pipeline
- Added `addMatchRationales()` for parallel rationale generation
- Added `getTopSignals()` for human-readable signal names
- Added `buildCandidateSummary()` for concise candidate descriptions
- Redis caching with 24h TTL (86400 seconds)
- Cache key format: `rationale:{candidateId}:{jdHash}`

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Separate endpoint in rerank service | Clean separation of concerns, reusable across services |
| Redis caching with 24h TTL | Avoids redundant LLM calls, balances freshness with cost |
| Parallel rationale generation | Minimizes latency for top 10 candidates |
| Graceful fallback | Search continues even if rationale generation fails |
| Signal name mapping | User-friendly names like "Skills Match" instead of "skillsExactMatch" |
| Input truncation | Prevents context overflow in LLM prompts |

## Commits

| Hash | Message |
|------|---------|
| 05d7910 | feat(09-05): add MatchRationale types for TRNS-03 |
| f468f16 | feat(09-05): add generateMatchRationale to Together client |
| 179da87 | feat(09-05): integrate match rationale into search pipeline |

## Files Modified

### Created/Modified

| File | Changes |
|------|---------|
| services/hh-rerank-svc/src/types.ts | Added MatchRationale interface |
| services/hh-rerank-svc/src/together-client.ts | Added generateMatchRationale method |
| services/hh-rerank-svc/src/schemas.ts | Added matchRationaleSchema |
| services/hh-rerank-svc/src/routes.ts | Added /v1/search/rationale endpoint |
| services/hh-search-svc/src/types.ts | Added MatchRationale, extended HybridSearchRequest/Item |
| services/hh-search-svc/src/rerank-client.ts | Added generateMatchRationale client method |
| services/hh-search-svc/src/search-service.ts | Integrated rationale generation |

## API Usage

### Request
```json
POST /v1/search
{
  "query": "senior backend engineer",
  "jobDescription": "...",
  "includeMatchRationale": true,
  "rationaleLimit": 10
}
```

### Response (top candidate)
```json
{
  "results": [{
    "candidateId": "abc123",
    "score": 0.92,
    "matchRationale": {
      "summary": "Strong backend engineer with 8 years of Python experience and proven leadership at top-tier companies.",
      "keyStrengths": [
        "Extensive Python/Django expertise",
        "Led team of 5 engineers"
      ],
      "signalHighlights": [
        {
          "signal": "Skills Match",
          "score": 0.95,
          "reason": "Exact match on Python, PostgreSQL, AWS"
        }
      ]
    }
  }]
}
```

## Success Criteria Verification

| Criterion | Status |
|-----------|--------|
| TRNS-03: LLM-generated match rationale for top candidates | Complete |
| Top 10 candidates receive rationales (configurable limit) | Complete |
| Rationales cached in Redis with 24h TTL | Complete |
| Graceful fallback on LLM errors | Complete |
| TypeScript compilation passes in both services | Complete |

## Deviations from Plan

None - plan executed exactly as written.

## Testing Notes

To verify Redis caching is working:

```bash
# After running a search with includeMatchRationale=true
redis-cli KEYS "rationale:*" | head -10
# Should show keys like: rationale:{candidateId}:{jdHash}

# Verify TTL is set correctly (24h = 86400 seconds)
redis-cli TTL "rationale:{sample-key}"
# Should return value between 0 and 86400
```

## Next Steps

This plan provides the backend infrastructure for TRNS-03. The UI integration (09-06) will wire this through to the frontend to display rationales in candidate cards.
