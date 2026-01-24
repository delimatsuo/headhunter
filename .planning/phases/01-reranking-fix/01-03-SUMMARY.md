---
phase: 01
plan: 03
subsystem: ui-display
tags: [react, candidate-card, score-display, user-experience]

dependency_graph:
  requires:
    - 01-01 (backend score propagation)
    - 01-02 (API service score mapping)
  provides:
    - Dual score display in candidate cards (Match + Similarity)
    - Visual confirmation that reranking is working (scores differ)
    - Distinct badge styling for match vs similarity scores
  affects:
    - 01-04-PLAN.md (verification plan)

tech_stack:
  added: []
  patterns:
    - Conditional rendering based on score difference threshold
    - Score normalization for 0-1 and 0-100 scale compatibility

key_files:
  created: []
  modified:
    - headhunter-ui/src/components/Candidate/SkillAwareCandidateCard.tsx
    - headhunter-ui/src/components/Search/SearchResults.tsx

decisions:
  - id: dec-01-03-01
    description: Show similarity badge only when scores differ by more than 1%
    rationale: Avoids confusion when scores are identical (reranking bypass); cleaner UI
  - id: dec-01-03-02
    description: Use "Sim" label instead of "Similarity" for badge
    rationale: Compact label fits badge design; tooltip provides full explanation

metrics:
  duration: 2 minutes
  completed: 2026-01-24
---

# Phase 01 Plan 03: UI Dual Score Display Summary

**One-liner:** Updated candidate cards to display both Match Score (LLM-influenced) and Similarity Score (raw vector) as separate badges with tooltips, enabling visual confirmation of reranking behavior.

## Objective Achieved

With Plans 01 and 02 fixing the backend and API service score propagation, this plan updates the UI to display both scores. Users can now visually confirm when LLM reranking is influencing results (scores differ) versus when it's bypassed (scores identical).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add similarityScore prop to SkillAwareCandidateCard | d6fb69a | SkillAwareCandidateCard.tsx |
| 2 | Display both scores as distinct badges | 9b00515 | SkillAwareCandidateCard.tsx |
| 3 | Pass similarityScore from SearchResults | b4c0178 | SearchResults.tsx |

## Implementation Details

### Task 1: Interface and Prop Addition
- Added `similarityScore?: number` to `SkillAwareCandidateCardProps` interface
- Destructured `similarityScore` in component function signature
- Comment indicates this is the raw vector similarity score

### Task 2: Dual Badge Display
Added helper function and conditional rendering:

```typescript
// Check if Match Score and Similarity Score are meaningfully different
const scoresAreDifferent = () => {
  if (matchScore === undefined || similarityScore === undefined) return false;
  const normalizedMatch = matchScore <= 1 ? matchScore * 100 : matchScore;
  const normalizedSim = similarityScore <= 1 ? similarityScore * 100 : similarityScore;
  return Math.abs(normalizedMatch - normalizedSim) > 1; // More than 1% difference
};
```

Display logic:
- Match badge: Always shown (primary score)
- Similarity badge: Only shown when `scoresAreDifferent()` returns true
- Distinct CSS classes: `score-badge match` and `score-badge similarity`
- Tooltips explain each score's meaning

### Task 3: Prop Passing
Updated SearchResults to pass `match.similarity` as `similarityScore` prop:

```tsx
<SkillAwareCandidateCard
  candidate={match.candidate}
  matchScore={match.score}
  similarityScore={match.similarity}  // NEW
  // ... other props
/>
```

## Verification Results

1. **TypeScript build:** Compiled successfully (warnings are pre-existing, unrelated)
2. **Interface check:** `similarityScore?: number;` present in props interface
3. **Prop passing:** `similarityScore={match.similarity}` in SearchResults.tsx:263
4. **Badge classes:** Both `score-badge match` and `score-badge similarity` present

## Deviations from Plan

None - plan executed exactly as written.

## UX Decisions

| Decision | Rationale |
|----------|-----------|
| Similarity shown only when different | Avoids confusion when reranking bypassed |
| 1% threshold for "different" | Filters out rounding noise; meaningful differences only |
| "Sim" label vs "Similarity" | Compact for badge; tooltip provides context |
| Match badge always visible | Primary score users expect; similarity is supplementary |

## Next Phase Readiness

Plan 01-03 complete. The full score propagation chain is now in place:
- Backend: raw_vector_similarity preserved in legacy-engine.ts
- API: similarity mapped to response in SearchResults
- UI: Both scores displayed with visual differentiation

Ready for Plan 01-04 (Verification) to validate end-to-end behavior.

## Commits

```
b4c0178 feat(01-03): pass similarityScore from SearchResults to SkillAwareCandidateCard
9b00515 feat(01-03): display both Match and Similarity scores as distinct badges
d6fb69a feat(01-03): add similarityScore prop to SkillAwareCandidateCard
```
