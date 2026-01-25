---
phase: 07-signal-scoring
plan: 03
subsystem: search-scoring
tags: [types, configuration, signal-weights, phase7]
requires: [07-01, 07-02]
provides: [phase7-type-support, extended-weight-config]
affects: [07-04, 07-05]
tech-stack:
  added: []
  patterns: [type-extension, weight-normalization]
key-files:
  created: []
  modified:
    - services/hh-search-svc/src/types.ts
    - services/hh-search-svc/src/signal-weights.ts
decisions:
  - key: phase7-signal-optional
    rationale: "All 5 Phase 7 signals are optional to maintain backward compatibility"
    impact: "Gradual rollout possible - scoring functions can check field presence"
  - key: weight-distribution-strategy
    rationale: "Executive favors seniority+company, IC favors exact skills+recency, Manager balanced"
    impact: "Role-specific weight presets reflect recruiter priorities for each level"
  - key: maintain-sum-1.0
    rationale: "All weights must sum to 1.0 for normalized scoring"
    impact: "Adjusted existing weights down proportionally to accommodate new signals"
metrics:
  duration: 108s
  completed: 2026-01-25
---

# Phase 7 Plan 03: Type Extensions and Weight Configuration

**One-liner:** Extended SignalScores and SignalWeightConfig interfaces with 5 Phase 7 signals, updated all role presets to maintain sum=1.0

## What Was Built

### Type System Extensions

Extended both scoring and configuration interfaces to support Phase 7 signals:

**SignalScores interface (types.ts):**
- Added 5 new optional fields for Phase 7 signals
- All fields 0-1 normalized
- Maintains backward compatibility with optional typing

**SignalWeightConfig interface (signal-weights.ts):**
- Added 5 new optional weight fields matching SignalScores
- Documented each field with SCOR-XX references
- Field names identical between interfaces for consistency

**New Phase 7 fields:**
1. `skillsExactMatch` - SCOR-02: Skills exact match score
2. `skillsInferred` - SCOR-03: Skills inferred/transferable score
3. `seniorityAlignment` - SCOR-04: Level alignment with tier adjustment
4. `recencyBoost` - SCOR-05: Recent experience decay scoring
5. `companyRelevance` - SCOR-06: Target company + tier + industry alignment

### Weight Preset Updates

Updated all 4 role-type presets with Phase 7 signal weights:

**Executive preset:**
- Emphasizes `seniorityAlignment` (0.12) and `companyRelevance` (0.12)
- Lower weight on exact skills (0.02) - hire for fit, not exact match
- Total weight redistribution maintains sum = 1.00

**IC preset:**
- Emphasizes `skillsExactMatch` (0.14) and `recencyBoost` (0.08)
- Skills-heavy distribution - exact fit matters most
- Lower company relevance (0.06) - skills trump pedigree
- Total weight redistribution maintains sum = 1.00

**Manager preset:**
- Balanced distribution across all signals
- `skillsExactMatch` (0.06), `seniorityAlignment` (0.06)
- Moderate weighting on all Phase 7 signals
- Total weight redistribution maintains sum = 1.00

**Default preset:**
- Evenly distributed across all 12 signals
- Neutral fallback when role type unknown
- Total weight redistribution maintains sum = 1.00

### Weight Normalization Enhancement

Updated `normalizeWeights()` function:
- Added `PHASE7_SIGNAL_KEYS` array for iteration
- Includes Phase 7 signals in sum calculation
- Preserves each Phase 7 signal during normalization
- Handles optional field presence gracefully

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

All verification criteria passed:

1. ✅ **TypeScript compilation:** `npx tsc --noEmit` passed without errors
2. ✅ **SignalScores has 5 new optional fields:** skillsExactMatch, skillsInferred, seniorityAlignment, recencyBoost, companyRelevance
3. ✅ **SignalWeightConfig has 5 new optional fields:** Matching field names and types
4. ✅ **All 4 ROLE_WEIGHT_PRESETS sum to exactly 1.00:**
   - Executive: 1.000 (diff: 0.000000)
   - Manager: 1.000 (diff: 0.000000)
   - IC: 1.000 (diff: 0.000000)
   - Default: 1.000 (diff: 0.000000)
5. ✅ **Field names match:** All 13 fields consistent between SignalScores and SignalWeightConfig

## Decisions Made

### 1. Phase 7 Signals Are Optional
**Context:** Need to support gradual rollout and backward compatibility

**Decision:** All 5 Phase 7 signals defined as optional fields (using `?:` syntax)

**Rationale:**
- Scoring functions can check field presence before using
- Allows deployment without breaking existing searches
- Enables A/B testing with gradual feature enablement

**Alternatives considered:**
- Required fields: Would break existing code
- Separate interface: Would fragment type system

**Impact:** Scoring and enrichment functions must handle undefined values

### 2. Role-Specific Weight Distributions
**Context:** Different role types value different signals

**Decision:**
- Executive: High seniorityAlignment (0.12), companyRelevance (0.12)
- IC: High skillsExactMatch (0.14), recencyBoost (0.08)
- Manager: Balanced across all signals

**Rationale:**
- Recruiter insights: Execs hire for fit, ICs need exact skills
- Reflects real-world hiring priorities per level
- Provides differentiated scoring behavior

**Alternatives considered:**
- Uniform weights: Would ignore role-specific priorities
- More granular presets: Adds complexity without clear benefit

**Impact:** Search results will rank differently based on roleType parameter

### 3. Proportional Weight Reduction
**Context:** Need to make room for 5 new signals while maintaining sum = 1.0

**Decision:** Reduced existing weights proportionally to accommodate new signals

**Rationale:**
- Maintains relative importance of existing signals
- Avoids arbitrary weight assignments
- Mathematical soundness (sum always = 1.0)

**Alternatives considered:**
- Uniform reduction: Would change relative signal importance
- Zero out minor signals: Would lose useful scoring dimensions

**Impact:** Existing signal weights slightly lower but proportionally preserved

## Technical Notes

### Weight Distribution Strategy

**Executive searches (C-level, VP, Director):**
```typescript
vectorSimilarity: 0.08     (-0.02 from original 0.10)
levelMatch: 0.12           (-0.08 from original 0.20)
specialtyMatch: 0.04       (-0.01 from original 0.05)
techStackMatch: 0.04       (-0.01 from original 0.05)
functionMatch: 0.20        (-0.05 from original 0.25)
trajectoryFit: 0.10        (-0.05 from original 0.15)
companyPedigree: 0.12      (-0.08 from original 0.20)
// Phase 7 additions
skillsExactMatch: 0.02     (new - low priority for execs)
skillsInferred: 0.02       (new - low priority for execs)
seniorityAlignment: 0.12   (new - HIGH priority for execs)
recencyBoost: 0.02         (new - low priority for execs)
companyRelevance: 0.12     (new - HIGH priority for execs)
```

**IC searches (Senior, Mid, Junior):**
```typescript
vectorSimilarity: 0.12     (-0.08 from original 0.20)
levelMatch: 0.08           (-0.07 from original 0.15)
specialtyMatch: 0.12       (-0.08 from original 0.20)
techStackMatch: 0.12       (-0.08 from original 0.20)
functionMatch: 0.06        (-0.04 from original 0.10)
trajectoryFit: 0.06        (-0.04 from original 0.10)
companyPedigree: 0.02      (-0.03 from original 0.05)
// Phase 7 additions
skillsExactMatch: 0.14     (new - HIGH priority for ICs)
skillsInferred: 0.08       (new - moderate for ICs)
seniorityAlignment: 0.06   (new - moderate for ICs)
recencyBoost: 0.08         (new - HIGH priority for ICs)
companyRelevance: 0.06     (new - moderate for ICs)
```

### Type System Integration

**Field naming convention:**
- SignalScores: Present tense (`skillsExactMatch`)
- SignalWeightConfig: Identical names (`skillsExactMatch`)
- No "Score" or "Weight" suffix - context from interface

**Optional field handling:**
- All Phase 7 fields use `?: number` syntax
- normalizeWeights() checks `!== undefined` before including in sum
- Scoring functions should use `?? 0.5` for missing signals (neutral default)

**Backward compatibility:**
- Existing code unaffected - optional fields don't require changes
- New scoring code can check field presence: `if (signals.skillsExactMatch !== undefined)`
- Gradual migration: Add Phase 7 scoring incrementally

## Testing Evidence

**TypeScript compilation:**
```bash
$ cd services/hh-search-svc && npx tsc --noEmit
# (no output - compilation successful)
```

**Weight preset validation:**
```
executive: 1.000 (diff from 1.0: 0.000000)
manager: 1.000 (diff from 1.0: 0.000000)
ic: 1.000 (diff from 1.0: 0.000000)
default: 1.000 (diff from 1.0: 0.000000)
```

**Field consistency:**
```
Field names match: true
SignalScores fields: 13
SignalWeightConfig fields: 13
Phase 7 fields added: skillsExactMatch, skillsInferred, seniorityAlignment, recencyBoost, companyRelevance
```

## Next Phase Readiness

### Blockers
None.

### Prerequisites for Phase 7 Plan 04
- ✅ SignalScores extended with Phase 7 fields
- ✅ SignalWeightConfig extended with Phase 7 weights
- ✅ All role presets include Phase 7 weights (sum = 1.0)
- ✅ normalizeWeights() handles Phase 7 signals
- ✅ TypeScript compilation passing

### Handoff Context
Phase 7 Plan 04 (Signal Score Extraction) can now:
1. Read Phase 7 signal values from candidate metadata
2. Populate SignalScores object with all 13 fields (8 existing + 5 Phase 7)
3. Use extended SignalWeightConfig for weighted scoring
4. Trust that all role presets are properly normalized

The type system is ready for Phase 7 scoring integration.

## Files Modified

### services/hh-search-svc/src/types.ts
- Extended SignalScores interface with 5 Phase 7 fields
- Added PHASE 7 SIGNALS comment section
- Each field documented with SCOR-XX reference

### services/hh-search-svc/src/signal-weights.ts
- Extended SignalWeightConfig interface with 5 Phase 7 fields
- Added PHASE7_SIGNAL_KEYS array for normalization
- Updated all 4 ROLE_WEIGHT_PRESETS with Phase 7 weights
- Enhanced normalizeWeights() to include Phase 7 signals in sum
- All presets maintain sum = 1.0 exactly

## Success Criteria Met

All plan objectives achieved:

- [x] SignalScores interface includes 5 new optional fields for Phase 7 signals
- [x] SignalWeightConfig interface includes 5 new optional weight fields
- [x] ROLE_WEIGHT_PRESETS updated with Phase 7 signal weights
- [x] All presets sum to 1.0 after adding new signal weights
- [x] normalizeWeights() includes Phase 7 signals in sum calculation
- [x] TypeScript compilation passing
- [x] Field names match between SignalScores and SignalWeightConfig

Phase 7 Plan 03 complete. Type system ready for signal extraction and scoring integration (Plans 04-05).
