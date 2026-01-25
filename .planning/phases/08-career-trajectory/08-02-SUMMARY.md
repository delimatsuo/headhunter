---
phase: 08
plan: 02
subsystem: trajectory-analysis
tags: [trajectory, velocity, career-type, classification, Together-AI]

requires:
  - 08-01  # Direction classifier foundation

provides:
  - Velocity classifier (fast/normal/slow based on promotion timing)
  - Type classifier (technical_growth/leadership_track/career_pivot/lateral_move)
  - Together AI fallback for missing date data
  - Function change detection for career pivots

affects:
  - 08-03  # Trajectory scoring will use velocity and type

tech-stack:
  added: []
  patterns:
    - Date-based velocity calculation with year-per-level metrics
    - Function keyword detection for career pivot identification
    - Track-aware type classification (IC vs management)

key-files:
  created: []
  modified:
    - services/hh-search-svc/src/trajectory-calculators.ts
    - services/hh-search-svc/src/trajectory-calculators.test.ts

decisions:
  - title: "Velocity thresholds: <2yr fast, 2-4yr normal, >4yr slow"
    rationale: "Industry-standard promotion timelines for tech roles"
    alternatives: []
  - title: "Together AI fallback when dates unavailable"
    rationale: "Many profiles lack structured date data; use existing enrichment"
    alternatives: ["Default to 'normal'", "Skip velocity scoring"]
  - title: "Function change detection via title keywords"
    rationale: "Frontend/backend/data/devops keywords indicate functional pivots"
    alternatives: ["Ignore function changes", "Use skill overlap analysis"]
  - title: "Check function changes before level filtering"
    rationale: "Ensures pivots detected even when titles don't map to levels"
    alternatives: ["Only check for mapped titles"]

metrics:
  duration: "7 minutes"
  completed: "2026-01-24"
---

# Phase 8 Plan 02: Trajectory Velocity and Type Classifiers

**One-liner:** Velocity (fast/normal/slow) and type (technical/leadership/pivot/lateral) classifiers with date-based computation and Together AI fallback

## Summary

Added `calculateTrajectoryVelocity` and `classifyTrajectoryType` functions to analyze career progression speed and track patterns. Velocity computed from promotion timing (years per level) with Together AI fallback when dates unavailable. Type classification detects technical growth, leadership track, career pivots (track/function changes), and lateral moves.

## What Was Built

### Core Functions

**calculateTrajectoryVelocity:**
- Computes years-per-level from experience entries with dates
- Returns 'fast' (<2yr), 'normal' (2-4yr), or 'slow' (>4yr)
- Falls back to Together AI `promotion_velocity` field when dates missing
- Defaults to 'normal' when insufficient data

**classifyTrajectoryType:**
- Detects 'technical_growth' from IC progression without management
- Detects 'leadership_track' from management progression
- Detects 'career_pivot' from track changes (IC↔Manager) or function changes
- Detects 'lateral_move' for same-level moves
- Function detection uses keywords: frontend, backend, fullstack, data, devops, mobile, security

### Type Definitions

```typescript
export type TrajectoryVelocity = 'fast' | 'normal' | 'slow';
export type TrajectoryType = 'technical_growth' | 'leadership_track' | 'lateral_move' | 'career_pivot';

export interface ExperienceEntry {
  title: string;
  startDate?: string;
  endDate?: string;
}

export interface CareerTrajectoryData {
  promotion_velocity?: 'fast' | 'normal' | 'slow';
  current_level?: string;
  trajectory_type?: string;
}
```

### Test Coverage

**39 total tests across 4 describe blocks:**
- 4 tests for `mapTitleToLevel` (from 08-01)
- 16 tests for `calculateTrajectoryDirection` (from 08-01)
- 10 tests for `calculateTrajectoryVelocity`:
  - Date-based velocity detection (fast/normal/slow)
  - Together AI fallback when dates missing
  - Edge cases (single experience, empty array, unknown titles)
- 9 tests for `classifyTrajectoryType`:
  - Technical growth detection (IC progression)
  - Leadership track detection (management progression)
  - Career pivot detection (track changes, function changes)
  - Lateral move detection (same-level moves)

All tests passing.

## Key Implementation Details

### Velocity Calculation Logic

```typescript
// Calculate level increases and time spans
let totalLevelIncrease = 0;
let totalYears = 0;

for (let i = 1; i < levelsWithDates.length; i++) {
  const levelChange = levelsWithDates[i].level - levelsWithDates[i - 1].level;
  if (levelChange > 0) {
    const years = (levelsWithDates[i].startDate.getTime() - levelsWithDates[i - 1].startDate.getTime()) / (1000 * 60 * 60 * 24 * 365);
    totalLevelIncrease += levelChange;
    totalYears += years;
  }
}

const yearsPerLevel = totalYears / totalLevelIncrease;
if (yearsPerLevel < 2) return 'fast';
if (yearsPerLevel > 4) return 'slow';
return 'normal';
```

### Function Change Detection

```typescript
// Check for function changes FIRST (before filtering invalid levels)
const functionKeywords = titleSequence.map(title => {
  const lower = title.toLowerCase();
  if (/\b(front[-\s]?end|frontend|ui|ux)\b/i.test(lower)) return 'frontend';
  if (/\b(back[-\s]?end|backend|server)\b/i.test(lower)) return 'backend';
  // ... other patterns
  return 'general';
});

const uniqueFunctions = new Set(functionKeywords.filter(f => f !== 'general'));
const hasFunctionChange = uniqueFunctions.size > 1;
```

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

1. **Velocity thresholds align with industry standards**
   - <2 years per level: Fast (typical at FAANG, startups)
   - 2-4 years per level: Normal (standard corporate progression)
   - >4 years per level: Slow (traditional enterprise or plateaued)

2. **Together AI fallback ensures broad coverage**
   - Many profiles lack structured experience dates
   - Together AI enrichment already computed `promotion_velocity`
   - Fallback prevents null/unknown velocity scores

3. **Function change detection before level filtering**
   - "Frontend Engineer" and "Backend Engineer" may not map to levels
   - Function keywords detected regardless of level mapping
   - Ensures pivots aren't missed due to unknown titles

4. **Track change detection uses level-based logic**
   - Technical track: levels 0-6
   - Management track: levels 7-13
   - Any transition between tracks = career pivot

## Testing Approach

### Unit Tests

All 39 tests passing:
- Velocity: Date-based computation, Together AI fallback, edge cases
- Type: Technical/leadership/pivot/lateral detection, edge cases
- Direction: Upward/lateral/downward detection (from 08-01)
- Title mapping: Standard and variant title handling (from 08-01)

### Edge Cases Covered

- Empty/single experience arrays
- Missing dates (Together AI fallback)
- Unknown titles (filtered out gracefully)
- Function changes with unmapped titles
- Track changes with level normalization

## Integration Points

### Upstream Dependencies

- **08-01 (Direction Classifier):** Shares `mapTitleToLevel` function and level constants

### Downstream Consumers

- **08-03 (Trajectory Scoring):** Will use velocity and type to compute trajectory fit scores
- **Search Service:** Will provide velocity/type as part of candidate enrichment

## Verification Results

✅ `calculateTrajectoryVelocity` returns 'fast', 'normal', or 'slow'
✅ Together AI fallback works when dates are missing
✅ `classifyTrajectoryType` returns one of four trajectory types
✅ Career pivots (track changes, function changes) are detected
✅ All 39 unit tests pass
✅ TypeScript compilation passes with no errors

## Next Phase Readiness

**Ready for 08-03 (Trajectory Scoring):**
- Velocity classifier complete (TRAJ-02)
- Type classifier complete (TRAJ-04)
- Both export stable TypeScript types
- Test coverage validates edge cases
- Functions ready for integration into scoring logic

**Blockers:** None

**Concerns:** None

## Performance Notes

- Velocity calculation: O(n) where n = number of experience entries
- Type classification: O(n) for function keyword extraction + O(n) for level analysis
- No external dependencies (Together AI data is optional fallback)
- Pure functions with no side effects

## Known Limitations

1. **Date parsing relies on ISO date strings**
   - Dates must be in format compatible with `new Date()`
   - Invalid dates silently filtered out

2. **Function keywords may not cover all specializations**
   - Current set: frontend, backend, fullstack, data, devops, mobile, security
   - Edge cases (e.g., "embedded", "blockchain") fall through to 'general'

3. **Level mapping doesn't distinguish all career stages**
   - Some nuanced progressions (e.g., "Senior I" vs "Senior II") map to same level
   - Could cause velocity to appear slower than reality

## Future Enhancements (Post-v1)

- Add more function keyword patterns (embedded, blockchain, game dev, etc.)
- Support non-ISO date formats
- Consider company-specific level mappings (e.g., L3/L4/L5 at Google)
- Track industry changes (fintech → healthcare) as pivots

---

**Plan 08-02 Complete**
- TRAJ-02: Velocity computed as fast (<2yr), normal (2-4yr), slow (>4yr) ✅
- TRAJ-04: Type classified as technical_growth, leadership_track, lateral_move, or career_pivot ✅
- Together AI promotion_velocity used as fallback when date parsing fails ✅
- Edge cases (missing dates, single role) return sensible defaults ✅
