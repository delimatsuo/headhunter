---
phase: 01
plan: 02
subsystem: search-frontend
tags: [api-service, score-extraction, frontend, match-metadata]

dependency_graph:
  requires:
    - 01-01 (backend score propagation)
  provides:
    - Frontend API service correctly extracts raw_vector_similarity from match_metadata
    - Both score types (match score and similarity) available for display
    - Debug logging for score differentiation verification
  affects:
    - 01-03-PLAN.md (component score display)
    - 01-04-PLAN.md (end-to-end verification)

tech_stack:
  added: []
  patterns:
    - Optional chaining for match_metadata access (match_metadata?.raw_vector_similarity)
    - Fallback chain with explicit 0 default (never falls back to overall_score)
    - Score normalization from 0-100 to 0-1 scale

key_files:
  created: []
  modified:
    - headhunter-ui/src/services/api.ts

decisions:
  - id: dec-01-02-01
    description: Normalize all scores to 0-1 scale in API service layer
    rationale: Frontend components expect 0-1 scale for percentage display
  - id: dec-01-02-02
    description: Fallback chain is match_metadata.raw_vector_similarity -> vector_similarity_score -> 0
    rationale: Never fall back to overall_score which was the core bug masking reranking bypass

metrics:
  duration: 3 minutes
  completed: 2026-01-24
---

# Phase 01 Plan 02: Frontend Score Display Summary

**One-liner:** Fixed API service to extract raw_vector_similarity from match_metadata, providing distinct Match Score and Similarity Score to frontend components.

## Objective Achieved

Fixed the frontend API service (`headhunter-ui/src/services/api.ts`) to correctly extract both scores from the backend response:
- **Match Score:** LLM-influenced overall_score (the reranked score)
- **Similarity Score:** Raw vector similarity from match_metadata.raw_vector_similarity

The previous code had a fallback chain `similarity: c.vector_similarity_score || c.overall_score` which caused Match Score to equal Similarity Score when vector_similarity_score was missing, masking the reranking bypass bug.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix similarity extraction in searchWithEngine response mapping | 1016c18 | api.ts |
| 2 | Fix similarity extraction in searchCandidates response mapping | 7a7c6be | api.ts |
| 3 | Add debug logging to verify score differentiation | 7a7c6be | api.ts |

## Verification Results

### Build Verification
```
$ cd headhunter-ui && npm run build
The build folder is ready to be deployed.
```
TypeScript compiles without errors.

### No overall_score Fallback
```
$ grep -c "similarity:.*overall_score" headhunter-ui/src/services/api.ts
0
```
No fallback to overall_score exists.

### raw_vector_similarity Extraction
```
$ grep -n "raw_vector_similarity" headhunter-ui/src/services/api.ts
426:            similarity: (c.match_metadata?.raw_vector_similarity || c.vector_similarity_score || 0) / 100
887:          // Pass through match_metadata for raw_vector_similarity access
936:        similarity: (c.match_metadata?.raw_vector_similarity || c.vector_similarity_score || 0) / 100
```
3 occurrences (2 extraction points + 1 comment).

### Debug Logging
```
$ grep -n "API Debug" headhunter-ui/src/services/api.ts
442:          console.log(`[API Debug] searchCandidates first result - Match: ...`)
949:        console.log(`[API Debug] searchWithEngine first result - Match: ...`)
```
2 debug logging points (one for each search method).

## Technical Implementation

### Score Extraction Changes

**Before (buggy):**
```typescript
// searchWithEngine
similarity: c.vector_similarity_score || c.overall_score,  // BUG: falls back to overall_score

// searchCandidates
similarity: c.vector_similarity_score,  // Missing normalization
```

**After (fixed):**
```typescript
// searchWithEngine
similarity: (c.match_metadata?.raw_vector_similarity || c.vector_similarity_score || 0) / 100,

// searchCandidates
similarity: (c.match_metadata?.raw_vector_similarity || c.vector_similarity_score || 0) / 100,
```

### Key Changes

1. **Pass through match_metadata** (line 887):
   Added `match_metadata: match.match_metadata || {}` to the intermediate candidates mapping in searchWithEngine so the raw_vector_similarity is accessible.

2. **Fallback chain** (lines 426, 936):
   - First tries `match_metadata.raw_vector_similarity` (from legacy-engine)
   - Falls back to `vector_similarity_score` (from skill-aware-search)
   - Falls back to `0` (never overall_score)

3. **Score normalization** (division by 100):
   Backend returns scores on 0-100 scale; frontend expects 0-1 for percentage display.

4. **Debug logging** (lines 442, 949):
   Logs first result's Match vs Similarity scores and whether they differ by >1%.

## Deviations from Plan

None - plan executed exactly as written.

## Success Criteria Met

- [x] TypeScript compiles without errors
- [x] `similarity` field is extracted from `match_metadata.raw_vector_similarity` in both response mappings
- [x] No fallback chain uses `overall_score` as similarity
- [x] Debug logging is in place to verify score differentiation
- [x] Scores are correctly normalized (0-1 scale for frontend display)

## Next Phase Readiness

The API service now correctly extracts and normalizes both scores. Next plan (01-03) should:
1. Update SearchResults component to pass both scores to candidate cards
2. Update SkillAwareCandidateCard to display distinct Match Score and Similarity Score badges

**Blockers:** None
**Concerns:** None
