---
phase: 01
plan: 01
subsystem: search-scoring
tags: [vector-search, score-propagation, legacy-engine, match-metadata]

dependency_graph:
  requires: []
  provides:
    - raw_vector_similarity field preserved through transformation chain
    - match_metadata.raw_vector_similarity exposed to frontend
    - match_metadata.gemini_score exposed for debugging
  affects:
    - 01-02-PLAN.md (frontend display of scores)
    - 01-03-PLAN.md (reranking integration)

tech_stack:
  added: []
  patterns:
    - Score preservation through object spread with field addition
    - Fallback chain for missing fields (|| 0)

key_files:
  created: []
  modified:
    - functions/src/engines/legacy-engine.ts
    - functions/src/engines/types.ts

decisions:
  - id: dec-01-01-01
    description: Use underscore prefix _raw_vector_similarity as internal field to avoid confusion with other score fields
    rationale: Clear distinction between internal tracking and public API fields
  - id: dec-01-01-02
    description: Add type definitions to match_metadata for raw_vector_similarity and gemini_score
    rationale: Required for TypeScript compilation; follows existing pattern

metrics:
  duration: 2 minutes
  completed: 2026-01-24
---

# Phase 01 Plan 01: Backend Score Propagation Fix Summary

**One-liner:** Preserved raw vector similarity through legacy-engine transformation chain, exposing both raw_vector_similarity and gemini_score in match_metadata for frontend score display.

## Objective Achieved

Fixed the score propagation bug where raw vector similarity was lost during candidate transformations in legacy-engine.ts. The vector search correctly computes vector_similarity_score, but it was being discarded. Now both scores (raw vector similarity AND LLM-influenced match score) are available in the API response.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Preserve raw vector similarity in vectorPool initialization | 72954b0 | legacy-engine.ts |
| 2 | Propagate raw similarity through candidate transformations | 05b5110 | legacy-engine.ts |
| 3 | Expose raw similarity in match_metadata and response | ed14f64 | legacy-engine.ts |
| 3b | Add type definitions for new fields | 2e7a888 | types.ts |

## Verification Results

### Build Verification
```
$ cd functions && npm run build
> headhunter-functions@1.0.0 build
> tsc
(no errors)
```

### Field Preservation Verification
```
$ grep -n "_raw_vector_similarity\|raw_vector_similarity" functions/src/engines/legacy-engine.ts
148:            _raw_vector_similarity: c.vector_similarity_score || c.similarity_score || 0
579:                        _raw_vector_similarity: c._raw_vector_similarity || 0,
587:                    _raw_vector_similarity: c._raw_vector_similarity || 0,
600:                _raw_vector_similarity: c._raw_vector_similarity || 0,
650:                    _raw_vector_similarity: c._raw_vector_similarity || c.vector_similarity_score || 0,
675:                vector_score: c._raw_vector_similarity || 0,
676:                raw_vector_similarity: c._raw_vector_similarity || 0,
686:            console.log(`[LegacyEngine] Score sample: ...raw_vector=${matches[0]?.match_metadata?.raw_vector_similarity || 0}...`);
```

### Occurrence Count
```
$ grep -c "_raw_vector_similarity" functions/src/engines/legacy-engine.ts
7
```

Meets requirement: >= 6 occurrences (1 initialization + 4 transformations + 2 in match_metadata)

## Technical Implementation

### Score Preservation Chain

1. **vectorPool initialization** (line 148):
   ```typescript
   let vectorPool: any[] = (vectorSearchResults || []).map((c: any) => ({
       ...c,
       _raw_vector_similarity: c.vector_similarity_score || c.similarity_score || 0
   }));
   ```

2. **rerankedTop mapping** (line 579): Preserves `_raw_vector_similarity` through Gemini reranking

3. **remainingCandidates mapping** (line 587): Preserves for candidates beyond top 50

4. **Error fallback mapping** (line 600): Preserves when Gemini reranking fails

5. **Fallback candidates mapping** (line 650): Re-captures from original vectorSearchResults for sparse results

6. **match_metadata exposure** (lines 675-676):
   ```typescript
   vector_score: c._raw_vector_similarity || 0,
   raw_vector_similarity: c._raw_vector_similarity || 0,
   gemini_score: c.gemini_score || 0,
   ```

### Logging Added

Score sample logging at line 686 allows verification that scores differ:
```
[LegacyEngine] Score sample: overall=X, raw_vector=Y, gemini=Z
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added type definitions for new match_metadata fields**
- **Found during:** Task 3 (build verification)
- **Issue:** TypeScript compilation failed because `raw_vector_similarity` and `gemini_score` were not in the `CandidateMatch.match_metadata` type definition
- **Fix:** Added both fields to `functions/src/engines/types.ts`
- **Files modified:** functions/src/engines/types.ts
- **Commit:** 2e7a888

## Success Criteria Met

- [x] TypeScript compiles without errors
- [x] `_raw_vector_similarity` field is preserved through all candidate transformations
- [x] `match_metadata.raw_vector_similarity` is set to the preserved raw vector similarity
- [x] `match_metadata.gemini_score` is set for debugging
- [x] Logging shows both scores for verification

## Next Phase Readiness

The backend now correctly preserves and exposes both score types. Next plan (01-02) should:
1. Update frontend to display both scores (Similarity Score vs Match Score)
2. Update SearchResults component to read from `match_metadata.raw_vector_similarity`

**Blockers:** None
**Concerns:** None
