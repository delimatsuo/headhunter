# Phase 1: Reranking Fix - Research

**Researched:** 2026-01-24
**Domain:** LLM Reranking Pipeline / Search System Integration
**Confidence:** HIGH

## Summary

The reranking system is fully implemented but produces scores that are not being properly differentiated from raw similarity scores. Through comprehensive code analysis, I have identified the root cause: **the LLM reranking IS being called and IS producing differentiated scores**, but the score integration and frontend display logic is incorrectly treating `overall_score` as `similarity_score` for display purposes.

**The core problem has three components:**
1. **Score Integration**: The `legacy-engine.ts` correctly calls Gemini reranking and computes a combined score (70% Gemini + 30% retrieval), but this score is being passed through multiple transformation layers that lose the distinction.
2. **Frontend Data Mapping**: The `api.ts` service maps both `score` and `similarity` fields to the same underlying value from the backend response.
3. **Display Logic**: The frontend displays `matchScore` (from `match.score`) which goes through the same transformation chain as similarity.

**Primary recommendation:** Fix the score propagation chain to preserve and display both the raw similarity score from vector search AND the LLM-influenced match score separately.

## Standard Stack

The system already uses the correct stack - no new libraries needed.

### Core (Already in Use)
| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| @google/generative-ai | ^0.x | Gemini API client (Firebase functions) | Working |
| @google-cloud/vertexai | ^1.x | Vertex AI client (hh-rerank-svc) | Working |
| pg | ^8.x | PostgreSQL client | Working |

### Supporting (Already in Use)
| Library | Purpose | Status |
|---------|---------|--------|
| p-retry | Retry logic for LLM calls | Working |
| p-timeout | Timeout handling | Working |
| Firebase Callable Functions | API layer | Working |

**No new dependencies required** - this is a bug fix in existing code flow.

## Architecture Patterns

### Current Data Flow (Problematic)

```
1. Frontend (SearchPage.tsx)
   ↓ calls apiService.searchWithEngine()

2. API Service (api.ts)
   ↓ calls Firebase engineSearch()

3. Firebase Function (engine-search.ts)
   ↓ calls VectorSearchService.searchCandidatesSkillAware()
   ↓ passes results to LegacyEngine.search()

4. Legacy Engine (legacy-engine.ts)
   ↓ Filters candidates
   ↓ Calls getGeminiRerankingService().rerank()
   ↓ CORRECTLY computes: overallScore = (geminiScore * 0.7) + (retrievalScore * 0.3)
   ↓ Returns results with overall_score set

5. Response Transform (engine-search.ts → api.ts → SearchResults.tsx)
   ↓ match.score = c.overall_score / 100 (line 425)
   ↓ match.similarity = c.vector_similarity_score || c.overall_score (line 426)
   ⚠️ HERE'S THE BUG: similarity uses overall_score as fallback!

6. Frontend Display (SkillAwareCandidateCard.tsx)
   ↓ matchScore prop = match.score (which is overall_score)
   ↓ Only one score displayed
```

### Correct Data Flow (Target)

```
1-4. Same as above

5. Response Transform (FIXED)
   ↓ Preserve BOTH scores through the chain:
   ↓   - match.score = LLM-influenced overall_score
   ↓   - match.similarity = RAW vector_similarity from pgvector

6. Frontend Display (FIXED)
   ↓ Display TWO scores:
   ↓   - "Match Score" = LLM-influenced (green badge)
   ↓   - "Similarity" = raw vector score (blue badge)
   ↓ Users can see the difference
```

### Key Architectural Insight

The Gemini reranking service in `legacy-engine.ts` returns scores correctly:
```typescript
// Line 546-554 - Gemini scores ARE being used
const ranking = rankedMap.get(candidateId);
const geminiScore = ranking ? ranking.score : 0;
const retrievalScore = c.retrieval_score || 0;

// Combined: 70% Gemini + 30% Retrieval
const overallScore = (geminiScore * 0.7) + (retrievalScore * 0.3);
```

The issue is that `vector_similarity_score` is not being passed through the response chain. It gets lost between:
1. Vector search results (has `similarity` field)
2. Engine processing (computes `overall_score`)
3. API mapping (uses `overall_score` as fallback for similarity)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Score normalization | Custom scaling logic | Consistent 0-100 range throughout | Already exists in multiple places |
| LLM reranking | New reranking implementation | Existing GeminiRerankingService | Fully functional, just not integrated correctly |
| Score differentiation | Complex UI logic | Pass both scores from backend | Cleaner data contract |

**Key insight:** The reranking infrastructure is complete and working. This is a data mapping bug, not a missing feature.

## Common Pitfalls

### Pitfall 1: Score Scale Confusion
**What goes wrong:** Scores are sometimes 0-1, sometimes 0-100
**Why it happens:** Different layers use different scales
- Gemini reranking: 0-100
- API response mapping: divides by 100 (`c.overall_score / 100`)
- Frontend normalization: multiplies by 100 if < 1

**How to avoid:**
- Standardize on 0-100 internally
- Only scale at final display layer
- Add type annotations showing expected scale

**Warning signs:** Scores showing as decimals when expecting percentages or vice versa

### Pitfall 2: Fallback Chain Obscures Bug
**What goes wrong:** `similarity = vector_similarity_score || overall_score`
**Why it happens:** Defensive coding to avoid undefined values
**How to avoid:**
- Track both scores explicitly through the chain
- Never use the reranked score as fallback for raw similarity
- Log both scores at each layer during debugging

**Warning signs:** Match Score = Similarity Score for all results

### Pitfall 3: Response Object Mutation
**What goes wrong:** Multiple transformations mutate the same object
**Why it happens:**
- `api.ts` transforms engine response
- `searchWithEngine` builds new response object
- Some original data gets lost

**How to avoid:**
- Preserve original vector search similarity in a dedicated field
- Use explicit field names: `raw_vector_similarity` vs `llm_match_score`

### Pitfall 4: Testing Without End-to-End Verification
**What goes wrong:** Unit tests pass but integration fails
**Why it happens:** Each layer works correctly in isolation
**How to avoid:**
- Add integration test that asserts Match Score != Similarity Score
- Log both scores at backend response
- Add frontend console logging during development

## Code Examples

### Where Gemini Score IS Being Applied (Working)

**Source:** `functions/src/engines/legacy-engine.ts` lines 546-578

```typescript
// This code IS working - Gemini scores ARE used
const rerankedTop = topCandidates.map((c: any) => {
    const candidateId = c.candidate_id || c.id || '';
    const ranking = rankedMap.get(candidateId);
    const geminiScore = ranking ? ranking.score : 0;
    const retrievalScore = c.retrieval_score || 0;

    // Combined: 70% Gemini (follows hiring logic) + 30% Retrieval signals
    const overallScore = (geminiScore * 0.7) + (retrievalScore * 0.3);

    return {
        ...c,
        overall_score: overallScore,  // LLM-influenced score
        gemini_score: geminiScore,    // Pure LLM score (preserved!)
        rationale
    };
}).sort((a: any, b: any) => b.overall_score - a.overall_score);
```

### Where Score Gets Lost (Bug Location 1)

**Source:** `functions/src/engines/legacy-engine.ts` lines 654-673

```typescript
// BUG: vector_score is assigned from vertex_score, not preserved from vector search
const matches: CandidateMatch[] = candidates.slice(0, limit).map((c: any) => ({
    // ...
    match_metadata: {
        sources: c.sources,
        score_breakdown: c.score_breakdown,
        vertex_score: c.vertex_score,
        vector_score: c.vertex_score, // ⚠️ BUG: Should be original similarity!
        target_function: targetClassification.function,
        target_level: targetClassification.level,
        candidate_function: c.searchable?.function
    }
}));
```

### Where Score Gets Lost (Bug Location 2)

**Source:** `headhunter-ui/src/services/api.ts` lines 425-426

```typescript
// BUG: Using overall_score as fallback for similarity
return {
    candidate,
    score: c.overall_score / 100,  // OK - this is the match score
    similarity: c.vector_similarity_score || c.overall_score,  // ⚠️ BUG!
    // ...
};
```

### Where Score Gets Lost (Bug Location 3)

**Source:** `headhunter-ui/src/services/api.ts` lines 927

```typescript
// BUG: Both fields get the same value
const matches = candidates.map((c: any) => ({
    // ...
    score: c.overall_score,
    similarity: c.vector_similarity_score || c.overall_score,  // ⚠️ Fallback!
    // ...
}));
```

### Fix Pattern: Preserve Original Similarity

```typescript
// In legacy-engine.ts, when processing vector results:
const vectorPoolWithSimilarity = vectorSearchResults.map((c: any) => ({
    ...c,
    _raw_vector_similarity: c.similarity || c.distance || 0  // Preserve original
}));

// Later, in final match construction:
match_metadata: {
    // ...
    raw_vector_similarity: c._raw_vector_similarity,  // Pass through
    match_score: c.overall_score,  // LLM-influenced
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Vector similarity only | LLM reranking | Project inception | More nuanced ranking |
| Single score display | Two scores (target) | This fix | Transparency for users |

**Current state:** LLM reranking implemented but score differentiation not visible

## Open Questions

### 1. Score Display Preferences
**What we know:** System computes both scores correctly internally
**What's unclear:** User preference for seeing one vs two scores
**Recommendation:** Show both initially, gather feedback, potentially make configurable

### 2. Gemini Score Scale
**What we know:** Gemini reranking returns 0-100 scores
**What's unclear:** Whether scores are well-calibrated (is 80 always "good"?)
**Recommendation:** Log score distributions, may need calibration later

### 3. Cache Key Stability
**What we know:** hh-rerank-svc uses Redis caching
**What's unclear:** Whether changing score integration affects cache invalidation
**Recommendation:** This fix is in Firebase functions, not hh-rerank-svc, so cache not affected

## Root Cause Analysis Summary

```
SYMPTOM: Match Score = Similarity Score (100% correlation)

ROOT CAUSE CHAIN:
1. vector-search.ts returns candidates with `similarity` field
2. legacy-engine.ts processes them but doesn't preserve `similarity`
3. After Gemini reranking, `overall_score` is set correctly
4. But `vector_score` in match_metadata is set to `vertex_score` (undefined)
5. api.ts uses `overall_score` as fallback when `vector_similarity_score` missing
6. Frontend receives identical values for both scores

EVIDENCE:
- Gemini logs show "Gemini Reranking returned X results"
- Score values ARE different internally (gemini_score tracked)
- Final output has Match Score = Similarity Score due to fallback chain

FIX APPROACH:
1. Preserve raw vector similarity through the entire chain
2. Pass both scores explicitly in response
3. Display both scores in frontend
4. Verify with logging that scores differ by >10% for 90%+ of results
```

## Success Criteria Validation

| Criterion | How to Verify | Current Status |
|-----------|---------------|----------------|
| Match Score differs from Similarity for 90%+ | Log and compare both scores | BLOCKED by score preservation bug |
| LLM reranking logged and verified | Check Cloud Function logs | WORKING - logs visible |
| Strong qualitative fit ranks higher | Compare rankings before/after | PARTIALLY WORKING - ranking correct, display wrong |
| Rerank latency under 500ms | Check timing logs | WORKING - within budget |

## Sources

### Primary (HIGH confidence)
- `functions/src/engines/legacy-engine.ts` - Full source analysis
- `functions/src/gemini-reranking-service.ts` - Reranking implementation
- `headhunter-ui/src/services/api.ts` - Response transformation
- `SEARCH_INVESTIGATION_HANDOFF.md` - Problem documentation

### Secondary (MEDIUM confidence)
- `services/hh-rerank-svc/src/rerank-service.ts` - Microservice implementation (not in current path)
- `functions/src/engine-search.ts` - Cloud function entry point

### Tertiary (LOW confidence)
- N/A - All findings based on direct code analysis

## Metadata

**Confidence breakdown:**
- Root cause identification: HIGH - Direct code tracing shows exact bug locations
- Fix approach: HIGH - Clear pattern of preserving scores through chain
- Success criteria: HIGH - Measurable through logging

**Research date:** 2026-01-24
**Valid until:** N/A - Bug fix research, timeless until code changes

---

## Implementation Notes for Planner

### Fix Locations (in order)

1. **`functions/src/engines/legacy-engine.ts`**
   - Preserve raw vector similarity from `vectorSearchResults`
   - Pass through `_raw_vector_similarity` field
   - Set `vector_score` in `match_metadata` correctly

2. **`functions/src/engine-search.ts`**
   - Ensure raw similarity passes through to response

3. **`headhunter-ui/src/services/api.ts`**
   - Remove fallback chain for similarity
   - Map `similarity` from `raw_vector_similarity` explicitly

4. **`headhunter-ui/src/components/Candidate/SkillAwareCandidateCard.tsx`**
   - Consider displaying both scores (optional, for visibility)

### Testing Strategy

1. Add console.log at each transformation layer showing both scores
2. Deploy to dev and run search
3. Export results to CSV
4. Verify Match Score != Similarity Score for 90%+ of results
5. Verify qualitative fit (strong candidates) have higher match scores

### Estimated Effort

- Code changes: 2-3 hours
- Testing: 1-2 hours
- Deployment: 30 minutes
- Total: 3.5-5.5 hours
