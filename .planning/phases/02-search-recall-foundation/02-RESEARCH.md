# Phase 2: Search Recall Foundation - Research

**Researched:** 2026-01-24
**Domain:** Search Recall / Candidate Retrieval / Filter Strategy
**Confidence:** HIGH

## Summary

Phase 2 addresses a critical search recall problem: the system returns only ~10 candidates instead of the expected 50+ from a database of 23,000+ candidates. Through comprehensive code analysis, I have identified **7 distinct exclusionary filter layers** that progressively eliminate candidates before they reach the scoring/reranking stage.

**The core problem is architectural:** The system applies hard filters (level, specialty, tech stack, function, score threshold) at the retrieval stage when these should be soft signals at the scoring stage. This is the classic "precision vs recall" tradeoff, and the current design over-optimizes for precision at the expense of recall.

**Primary recommendation:** Convert hard exclusionary filters to soft scoring signals. Missing data should contribute a neutral 0.5 score rather than cause exclusion. The retrieval stage should fetch 500+ candidates using only vector similarity and basic consent checks, leaving all filtering logic to the scoring/reranking stages.

## Standard Stack

The system already has the correct infrastructure - no new libraries needed. The fix is architectural, not technological.

### Core (Already in Use)
| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| pg + pgvector | ^8.x | PostgreSQL vector similarity search | Working - needs query changes |
| @google/generative-ai | ^0.x | Gemini reranking | Working |
| firebase-admin | ^12.x | Firestore for profiles | Working |

### Supporting (Already in Use)
| Library | Purpose | Status |
|---------|---------|--------|
| p-retry | Retry logic | Working |
| Redis | Caching | Working |

**No new dependencies required** - this is an architectural change in existing code flow.

## Architecture Patterns

### Current Data Flow (Problematic)

```
23,000+ Candidates
     |
     v
[1] Vector Search (similarityThreshold=0.5)     ───> ~500 candidates
     |
     v
[2] Level Filter (levelRange)                   ───> ~200 candidates (HARD EXCLUSION)
     |
     v
[3] Specialty Filter (backend/frontend/etc)     ───> ~100 candidates (HARD EXCLUSION)
     |
     v
[4] Tech Stack Filter (Java devs excluded)      ───> ~70 candidates (HARD EXCLUSION)
     |
     v
[5] Function Exclusion (PM, QA, etc)            ───> ~60 candidates (HARD EXCLUSION)
     |
     v
[6] Career Trajectory Filter (overqualified)    ───> ~30 candidates (HARD EXCLUSION)
     |
     v
[7] Score Threshold (MIN_SCORE_THRESHOLD=30)    ───> ~15 candidates (HARD EXCLUSION)
     |
     v
[8] Gemini Reranking                            ───> ~10-15 candidates
     |
     v
Final Results: ~10 candidates (TARGET: 50+)
```

### Root Cause: Cascading Hard Filters

Each filter reduces the candidate pool by 20-50%. With 7 filters in series:
- Starting pool: 500 candidates
- After filters: 500 * 0.6^7 = ~14 candidates

This explains why search returns ~10 candidates instead of 50+.

### Target Data Flow (Solution)

```
23,000+ Candidates
     |
     v
[1] Vector Search (threshold=0.3, limit=800)    ───> 800 candidates (BROAD RECALL)
     |
     v
[2] Basic Consent Check Only                    ───> 795 candidates (REQUIRED FILTER)
     |
     v
[3] Multi-Signal Scoring (NOT filtering):       ───> 795 candidates with scores
    - Level match: 0-1 score (missing=0.5)
    - Specialty match: 0-1 score (missing=0.5)
    - Tech stack: 0-1 score (missing=0.5)
    - Function match: 0-1 score (missing=0.5)
    - Vector similarity: 0-1 score
    - Company pedigree: 0-1 score
     |
     v
[4] Sort by composite score                     ───> 795 candidates ranked
     |
     v
[5] Take top 100 for Gemini Reranking           ───> 100 candidates
     |
     v
[6] Gemini intelligent reranking                ───> 100 candidates reranked
     |
     v
[7] Return top 50                               ───> 50 candidates (TARGET MET)
```

### Key Architectural Principle

**Retrieval Stage:** BROAD - Maximize recall
- Only filter by vector similarity (low threshold)
- Only filter by legal requirements (consent, deleted)
- Goal: Get 500-800 candidates to score

**Scoring Stage:** NUANCED - Add soft signals
- Convert all "filters" to scoring factors
- Missing data = 0.5 (neutral), not exclusion
- All candidates remain, just with different scores

**Reranking Stage:** INTELLIGENT - Let AI decide
- Send 100 candidates to Gemini
- Gemini applies domain knowledge
- Final ranking based on fit, not hard rules

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Broad retrieval | Multiple filtered queries | Single pgvector query with low threshold | Already works, just increase limit |
| Missing data handling | Custom null checks | Default to 0.5 in scoring | Simple, consistent pattern |
| Smart filtering | Complex conditional exclusion | Gemini reranking | Already implemented, use it |

**Key insight:** The infrastructure to score instead of filter already exists. The `calculateLevelScore`, `calculateCompanyScore`, `calculateSpecialtyScore` functions return 0-1 scores. We just need to stop calling `.filter()` before using these scores.

## Common Pitfalls

### Pitfall 1: Premature Filtering
**What goes wrong:** Candidates excluded before scoring stage
**Why it happens:** Defensive coding - "Why score someone who doesn't match?"
**How to avoid:**
- Never call `.filter()` on candidate pool before scoring
- All matching logic expressed as scoring functions (0-1 range)
- Missing data = 0.5, not exclusion
**Warning signs:** Candidate pool drops by >30% at any single step

### Pitfall 2: Threshold Creep
**What goes wrong:** Thresholds set too high, eliminating good candidates
**Current thresholds causing issues:**
- `similarityThreshold=0.5` (vector-search.ts line 463)
- `similarityThreshold=0.7` (pgvector-client.ts line 331 default)
- `minSimilarity=0.45` (hh-search-svc config.ts line 236)
- `MIN_SCORE_THRESHOLD=30` (legacy-engine.ts line 619)
**How to avoid:**
- Start with very low thresholds (0.2-0.3)
- Let scoring and reranking handle quality
- Monitor recall metrics, not just precision

### Pitfall 3: Missing Data = Exclusion
**What goes wrong:** Candidates without specialty/level/skills data get filtered out
**Why it happens:** `.filter()` returns false when data is undefined
**Code locations:**
```typescript
// legacy-engine.ts line 184 - Specialty filter
const candidateSpecialties = this.getCandidateSpecialty(c, pgSpecialties);
if (candidateSpecialties.length === 0) return true; // GOOD - passes through
// BUT later, strict exclusions still apply to those with data

// legacy-engine.ts line 469-484 - Level filter
const nominalLevel = c.searchable?.level || '';
if (!nominalLevel || nominalLevel === 'unknown') return true; // GOOD
// BUT candidates WITH data still get hard filtered
```
**How to avoid:**
- Score missing data as 0.5 (neutral)
- Never exclude based on undefined values
- Document assumption: "Unknown is not disqualifying"

### Pitfall 4: Specialty Over-Filtering
**What goes wrong:** Backend search excludes fullstack developers
**Current code (legacy-engine.ts lines 200-238):**
```typescript
// STRICT EXCLUSIONS: Now with good specialty data, exclude clear mismatches
if (targetSpecialties.includes('backend')) {
    const isPureFrontend = candidateSpecialties.includes('frontend') &&
        !candidateSpecialties.includes('backend') &&
        !candidateSpecialties.includes('fullstack');
    if (isPureFrontend) return false; // HARD EXCLUSION
}
```
**How to avoid:**
- Convert to scoring: `isPureFrontend ? 0.2 : 1.0`
- Let Gemini evaluate edge cases
- Fullstack developers are often the BEST backend candidates

### Pitfall 5: Level Exclusion Logic
**What goes wrong:** Startup CTOs excluded from Senior Engineer searches
**Current logic (legacy-engine.ts lines 1103-1125):**
```typescript
// Get levels ABOVE the target level (candidates who would be stepping DOWN)
private getLevelsAbove(targetLevel: string): string[] {
    const icLevelOrder = ['intern', 'junior', 'mid', 'senior', 'staff', 'principal'];
    const managementLevels = ['manager', 'director', 'vp', 'c-level'];
    // Returns levels that would be "stepping down"
}
```
**How to avoid:**
- Don't assume career trajectory
- Some CTOs WANT to return to IC roles
- Score as "potential overqualification" (0.7) not exclusion (0.0)

## Code Examples

### Filter Location 1: Vector Similarity Threshold
**Source:** `functions/src/vector-search.ts` lines 463-470

```typescript
// CURRENT (too restrictive):
const similarityThreshold = 0.5; // Lowered from 0.7

// FIX: Lower threshold, increase limit
const similarityThreshold = 0.25; // Much broader recall
const limit = query.limit || 100;
const fetchLimit = Math.max(limit * 5, 500); // Fetch 5x more for scoring
```

### Filter Location 2: Level Range Filter
**Source:** `functions/src/engines/legacy-engine.ts` lines 167-173

```typescript
// CURRENT (hard filter):
vectorPool = vectorPool.filter((c: any) => {
    const effectiveLevel = this.getEffectiveLevel(c);
    if (effectiveLevel === 'unknown') return true;
    return levelRange.includes(effectiveLevel);
});

// FIX: Convert to scoring signal
vectorPool = vectorPool.map((c: any) => {
    const effectiveLevel = this.getEffectiveLevel(c);
    const levelScore = effectiveLevel === 'unknown'
        ? 0.5 // Neutral for unknown
        : levelRange.includes(effectiveLevel) ? 1.0 : 0.3; // Still include, lower score
    return { ...c, _level_score: levelScore };
});
```

### Filter Location 3: Specialty Exclusion
**Source:** `functions/src/engines/legacy-engine.ts` lines 184-242

```typescript
// CURRENT (hard filter):
vectorPool = vectorPool.filter((c: any) => {
    // ... specialty matching logic
    if (hasWrongSpecialty) return false; // EXCLUSION
    return true;
});

// FIX: Convert to scoring
vectorPool = vectorPool.map((c: any) => {
    const specialtyScore = this.calculateSpecialtyScore(c, targetSpecialties, pgSpecialties);
    // specialtyScore returns 0-1, already handles missing data as 0.5
    return { ...c, _specialty_score: specialtyScore };
});
```

### Filter Location 4: Score Threshold
**Source:** `functions/src/engines/legacy-engine.ts` lines 619-626

```typescript
// CURRENT (hard filter):
const MIN_SCORE_THRESHOLD = 30;
candidates = candidates.filter((c: any) => {
    return score >= MIN_SCORE_THRESHOLD;
});

// FIX: Remove threshold, let ranking handle it
// Sort by score and take top N - no arbitrary cutoff
candidates.sort((a, b) => b.overall_score - a.overall_score);
candidates = candidates.slice(0, targetLimit);
```

### Pattern: Scoring Instead of Filtering

```typescript
// Generic pattern for converting filter to score
function calculateSignalScore(
    candidate: any,
    targetValue: string | string[],
    candidateValue: string | undefined
): number {
    // Missing data = neutral
    if (!candidateValue) return 0.5;

    // Exact match = high score
    const targets = Array.isArray(targetValue) ? targetValue : [targetValue];
    if (targets.includes(candidateValue)) return 1.0;

    // Partial match = medium score
    if (targets.some(t => candidateValue.includes(t) || t.includes(candidateValue))) {
        return 0.7;
    }

    // No match = low score (not zero - still included)
    return 0.3;
}
```

## Identified Exclusionary Filters

### Summary Table

| # | Filter Name | Location | Current Behavior | Target Behavior |
|---|-------------|----------|------------------|-----------------|
| 1 | Vector Similarity | pgvector-client.ts:331 | threshold=0.7 | threshold=0.25 |
| 2 | Level Range | legacy-engine.ts:167 | EXCLUDE if not in range | SCORE 0.3-1.0 |
| 3 | Specialty Match | legacy-engine.ts:184 | EXCLUDE mismatches | SCORE 0.2-1.0 |
| 4 | Tech Stack | legacy-engine.ts:267 | EXCLUDE wrong stack | SCORE 0.2-1.0 |
| 5 | Function Title | legacy-engine.ts:310 | EXCLUDE PM/QA/etc | SCORE 0.1-1.0 |
| 6 | Career Trajectory | legacy-engine.ts:469 | EXCLUDE overqualified | SCORE 0.5-1.0 |
| 7 | Score Threshold | legacy-engine.ts:619 | EXCLUDE if <30 | REMOVE threshold |

### Missing Data Handling

| Data Field | Current | Target |
|------------|---------|--------|
| Level | Pass through as unknown | Score as 0.5 |
| Specialty | Pass through | Score as 0.5 |
| Skills | Exclude if missing required | Score as 0.5 |
| Function | Pass if no data | Score as 0.5 |
| Country | Include NULL | Score as 0.5 |

## Database Query Changes

### Current pgvector Query Pattern
**Source:** `functions/src/pgvector-client.ts` searchSimilar method

```sql
-- Current: Hard similarity threshold
WHERE 1 - (e.embedding <=> $1) > $3  -- threshold filter

-- Proposed: Softer threshold, higher limit
WHERE 1 - (e.embedding <=> $1) > 0.25  -- lower threshold
LIMIT 800  -- fetch more for scoring
```

### hh-search-svc Query Pattern
**Source:** `services/hh-search-svc/src/pgvector-client.ts` lines 175-279

```sql
-- Current: minSimilarity=0.45 (line 236 in config.ts)
WHERE COALESCE(vector_score, 0) >= $7 OR COALESCE(text_score, 0) > 0

-- Proposed: Much lower threshold
WHERE COALESCE(vector_score, 0) >= 0.15 OR COALESCE(text_score, 0) > 0
```

## State of the Art

| Old Approach | Current Approach | Why Better |
|--------------|------------------|------------|
| Filter then rank | Rank then filter | Higher recall, smarter filtering |
| Hard thresholds | Soft signals | Graceful degradation |
| Exclude unknown | Include with 0.5 score | Reduces false negatives |
| Precision focus | Recall focus | Users can filter, can't unfilter |

**Industry standard:** Two-stage retrieval-reranking pipelines (like this system) should:
1. Recall stage: Maximize candidates returned (high recall)
2. Rerank stage: Apply intelligence to sort (high precision)

The current implementation over-filters at stage 1, leaving too few candidates for intelligent stage 2.

## Open Questions

### 1. Performance Impact
**What we know:** More candidates to score = more computation
**What's unclear:** How much latency will increase
**Recommendation:**
- Current: ~100 candidates to Gemini
- Proposed: Still 100 to Gemini (just from larger pool)
- Scoring 800 vs 300 candidates adds ~50-100ms
- Acceptable for 5x improvement in recall

### 2. Specialty Data Quality
**What we know:** PostgreSQL `specialties` column recently backfilled
**What's unclear:** Coverage percentage across 23,000 candidates
**Recommendation:**
- Audit: `SELECT COUNT(*) FROM sourcing.candidates WHERE specialties IS NULL OR specialties = '{}'`
- If >50% missing, specialty filtering is harmful

### 3. Reranking Capacity
**What we know:** Gemini reranking handles 100 candidates
**What's unclear:** Whether 100 is optimal or can be increased
**Recommendation:**
- Test with 150-200 candidates
- Monitor reranking latency
- Current budget: <500ms, currently ~200ms

## Success Criteria

| Metric | Current | Target | How to Measure |
|--------|---------|--------|----------------|
| Candidates returned | ~10 | 50+ | Count results array |
| Pre-filter pool | ~300 | 500+ | Log at retrieval stage |
| Missing data handled | Excluded | Scored 0.5 | Audit code paths |
| Specialty filters | Hard exclusion | Soft scoring | Code review |

## Sources

### Primary (HIGH confidence)
- `functions/src/engines/legacy-engine.ts` - Full analysis of filter chain
- `functions/src/pgvector-client.ts` - Vector search thresholds
- `functions/src/vector-search.ts` - VectorSearchService filters
- `services/hh-search-svc/src/pgvector-client.ts` - HybridSearch query
- `services/hh-search-svc/src/config.ts` - Threshold configurations

### Secondary (MEDIUM confidence)
- `.planning/phases/01-reranking-fix/01-RESEARCH.md` - Prior phase context
- `docs/HANDOVER.md` - System documentation

### Tertiary (LOW confidence)
- N/A - All findings based on direct code analysis

## Metadata

**Confidence breakdown:**
- Filter identification: HIGH - Direct code tracing shows all 7 filter locations
- Solution approach: HIGH - Standard retrieval/rerank pattern
- Performance impact: MEDIUM - Needs validation with actual data
- Success criteria: HIGH - Measurable through logging

**Research date:** 2026-01-24
**Valid until:** Until architectural changes to search pipeline

---

## Implementation Notes for Planner

### Priority Order (Dependencies)

1. **Lower similarity thresholds** - Unblocks everything else
   - Files: `functions/src/vector-search.ts`, `functions/src/pgvector-client.ts`
   - Config: `services/hh-search-svc/src/config.ts`

2. **Remove hard level/specialty filters** - Biggest impact on recall
   - File: `functions/src/engines/legacy-engine.ts`
   - Convert `.filter()` calls to `.map()` with scores

3. **Remove score threshold** - Final blocker to recall
   - File: `functions/src/engines/legacy-engine.ts` line 619
   - Remove `MIN_SCORE_THRESHOLD` check

4. **Increase retrieval limits** - Ensures enough candidates
   - Multiple files, update `limit` parameters

### Testing Strategy

1. Add logging at each stage showing candidate count:
   ```
   [VectorSearch] Retrieved: 600 candidates
   [LegacyEngine] After level scoring: 600 candidates
   [LegacyEngine] After specialty scoring: 600 candidates
   [LegacyEngine] Sent to Gemini: 100 candidates
   [LegacyEngine] Final results: 50 candidates
   ```

2. Compare before/after with same search queries
3. Verify no candidates lost to filters (all reach scoring)
4. Validate results still have good quality (Gemini handles this)

### Estimated Effort

- Code changes: 4-6 hours
- Testing: 2-3 hours
- Documentation: 1 hour
- Total: 7-10 hours

### Risk Mitigation

- **Feature flag**: `ENABLE_BROAD_RECALL=true/false` to toggle behavior
- **A/B testing**: Run old and new paths in parallel, compare results
- **Gradual rollout**: Lower thresholds incrementally (0.5 -> 0.4 -> 0.3 -> 0.25)
