---
phase: 07-signal-scoring
plan: 04
subsystem: search-scoring
tags: [signals, integration, search-context, logging]
requires: [07-01-skill-calculators, 07-02-seniority-company, 07-03-type-extensions]
provides: [phase7-signal-integration, signal-computation-context, phase7-logging]
affects: [07-05-verification]
tech-stack:
  added: []
  patterns: [context-passing, signal-extraction, debug-logging]
key-files:
  created: []
  modified:
    - services/hh-search-svc/src/scoring.ts
    - services/hh-search-svc/src/search-service.ts
decisions:
  - id: signal-computation-context
    choice: Create SignalComputationContext interface for Phase 7 signal computation
    rationale: Avoids naming conflict with existing SearchContext (auth context)
  - id: conditional-phase7-computation
    choice: Only compute Phase 7 signals when signalContext provided
    rationale: Backward compatibility - signals optional, computed only when search context available
  - id: target-level-detection
    choice: Auto-detect target level from job description keywords
    rationale: Improves UX when seniorityLevels filter not explicitly provided
metrics:
  duration: 6 minutes
  completed: 2026-01-25
---

# Phase 7 Plan 04: Signal Integration Summary

**One-liner:** Integrated Phase 7 signal calculators into scoring.ts and search-service.ts with context passing and debug logging.

---

## What Was Built

Completed the integration of Phase 7 signal calculators into the search pipeline, enabling all 5 Phase 7 signals to contribute to candidate ranking.

### scoring.ts Updates

**SignalComputationContext Interface:**
- requiredSkills, preferredSkills
- targetLevel, targetCompanies, targetIndustries
- roleType for context-aware scoring

**extractSignalScores Enhancement:**
- Now accepts optional `signalContext` parameter
- Computes Phase 7 signals when context provided:
  - SCOR-02: skillsExactMatch
  - SCOR-03: skillsInferred
  - SCOR-04: seniorityAlignment
  - SCOR-05: recencyBoost
  - SCOR-06: companyRelevance
- Extracts candidate data from row metadata

**computeWeightedScore Enhancement:**
- Includes Phase 7 signals in weighted sum
- Only adds signal contribution when both signal and weight exist
- Maintains backward compatibility (Phase 7 signals optional)

**Helper Functions:**
- `extractCandidateSkills`: From skills array + metadata.intelligent_analysis
- `extractCandidateLevel`: From career_trajectory_analysis
- `extractCandidateCompanies`: From experience array
- `extractCandidateExperience`: For recency calculation

### search-service.ts Updates

**Search Context Building:**
- Builds `SignalComputationContext` in hydrateResult
- Extracts requiredSkills from filters.skills
- Auto-detects targetLevel from job description keywords
- Extracts targetIndustries from filters
- Passes roleType from resolved weights

**Helper Methods:**
- `detectTargetLevel`: Keyword-based level detection (director, manager, senior, etc.)
- `extractTargetCompanies`: From filters.metadata.targetCompanies

**Phase 7 Signal Logging:**
- Logs statistics for top 20 candidates after ranking
- Averages for all 5 Phase 7 signals
- Enables monitoring and debugging

**Debug Output Enhancement:**
- Added `phase7Breakdown` to debug response
- Shows Phase 7 signals for top 5 candidates
- Includes skillsExactMatch, skillsInferred, seniorityAlignment, recencyBoost, companyRelevance

---

## Deviations from Plan

None - plan executed exactly as written.

---

## Testing Evidence

### TypeScript Compilation
```bash
cd services/hh-search-svc && npx tsc --noEmit
# Result: ✅ No errors
```

### Signal Flow Verification
1. ✅ SignalComputationContext imported in search-service.ts
2. ✅ signalContext built in hydrateResult
3. ✅ extractSignalScores called with context
4. ✅ Phase 7 signals computed when context provided
5. ✅ computeWeightedScore includes Phase 7 signals
6. ✅ phase7Breakdown in debug output

---

## Decisions Made

### SignalComputationContext Naming
**Decision:** Create new `SignalComputationContext` interface instead of reusing `SearchContext`

**Options considered:**
1. Reuse existing `SearchContext` interface
2. Create new `SignalComputationContext` interface
3. Rename existing `SearchContext` to `AuthContext`

**Choice:** Option 2 (new interface)

**Rationale:**
- Existing `SearchContext` is for auth/tenant context (different purpose)
- Clear separation of concerns (auth vs signal computation)
- Avoids breaking changes to existing code
- Explicit naming clarifies intent

---

### Conditional Phase 7 Computation
**Decision:** Only compute Phase 7 signals when `signalContext` provided

**Options considered:**
1. Always compute Phase 7 signals (empty context if not provided)
2. Compute only when signalContext provided
3. Make signalContext required parameter

**Choice:** Option 2 (conditional computation)

**Rationale:**
- Backward compatibility - existing code doesn't break
- Performance optimization - skip computation when no context
- Semantic clarity - signals only meaningful with search context
- Aligns with "optional Phase 7 signals" design from 07-03

---

### Target Level Detection
**Decision:** Auto-detect target level from job description keywords

**Options considered:**
1. Require explicit seniorityLevels filter
2. Default to 'mid' if not provided
3. Auto-detect from job description text

**Choice:** Option 3 (auto-detection with 'mid' fallback)

**Rationale:**
- Improves UX - works even without explicit filter
- Common keywords covered (director, manager, senior, junior)
- Falls back to 'mid' (neutral) if no keywords match
- Non-breaking - explicit filter still takes precedence

---

## File Changes

### Modified Files
| File | Lines Changed | Purpose |
|------|---------------|---------|
| `services/hh-search-svc/src/scoring.ts` | +190 -3 | Phase 7 signal computation, helper functions |
| `services/hh-search-svc/src/search-service.ts` | +108 -4 | Context passing, logging, debug output |

### Key Functions Added
**scoring.ts:**
- `extractCandidateSkills(row)` → string[]
- `extractCandidateLevel(row)` → string | null
- `extractCandidateCompanies(row)` → string[]
- `extractCandidateExperience(row)` → CandidateExperience[]

**search-service.ts:**
- `detectTargetLevel(request)` → string
- `extractTargetCompanies(request)` → string[] | undefined

---

## Integration Points

### Used By
- Search API endpoints (via SearchService.hybridSearch)
- Skill-aware search paths
- Multi-tenant search scenarios

### Dependencies
- signal-calculators.ts (Phase 7 calculators)
- signal-weights.ts (weight configuration)
- types.ts (SignalScores, PgHybridSearchRow)

---

## Next Phase Readiness

### Blockers
None

### Concerns
None - integration successful, TypeScript compilation passing

### Required for Next Plan (07-05: Verification)
- ✅ Phase 7 signals computed in search results
- ✅ Debug output includes phase7Breakdown
- ✅ Logging shows Phase 7 signal statistics
- ✅ All code compiles without errors

---

## Requirements Satisfied

| Requirement | Status | Evidence |
|-------------|--------|----------|
| SCOR-02 Integration | ✅ Complete | skillsExactMatch computed in extractSignalScores |
| SCOR-03 Integration | ✅ Complete | skillsInferred computed in extractSignalScores |
| SCOR-04 Integration | ✅ Complete | seniorityAlignment computed in extractSignalScores |
| SCOR-05 Integration | ✅ Complete | recencyBoost computed in extractSignalScores |
| SCOR-06 Integration | ✅ Complete | companyRelevance computed in extractSignalScores |
| Weighted Scoring | ✅ Complete | computeWeightedScore includes all Phase 7 signals |
| Debug Output | ✅ Complete | phase7Breakdown shows signals for top 5 candidates |
| Logging | ✅ Complete | Phase 7 statistics logged for top 20 candidates |

---

## Performance Notes

- **Execution time:** 6 minutes (3 tasks, 3 commits)
- **Phase 7 signal computation:** Per-candidate overhead negligible
  - Helper functions: O(1) - data extraction from metadata
  - Calculator calls: O(n) where n = number of skills/experiences
  - Typical: 5-10 skills, 3-5 experiences → <1ms per candidate
- **Logging overhead:** Minimal (top 20 sample, aggregation only)
- **Debug output:** Only when includeDebug=true

---

## Phase 7 Progress

**Plans Complete:** 4/5 (80%)
- ✅ 07-01: Skill Signal Calculators
- ✅ 07-02: Seniority, Recency, Company Calculators
- ✅ 07-03: Type Extensions and Weight Configuration
- ✅ 07-04: Signal Integration (THIS PLAN)
- ⬜ 07-05: Verification and End-to-End Testing

**Requirements Complete:** 5/5 (100% - implementation complete, verification pending)
- ✅ SCOR-02: Exact skill matching (integrated)
- ✅ SCOR-03: Inferred skill matching (integrated)
- ✅ SCOR-04: Seniority alignment (integrated)
- ✅ SCOR-05: Recency boost (integrated)
- ✅ SCOR-06: Company relevance (integrated)

---

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | 4288775 | feat(07-04): add Phase 7 signal computation to scoring.ts |
| 2 | cb27eb0 | feat(07-04): pass search context to extractSignalScores |
| 3 | e8f64ec | feat(07-04): add Phase 7 signal logging and debug output |

---

**Summary created:** 2026-01-25
**Total duration:** 6 minutes
**Status:** ✅ Complete - Ready for 07-05
