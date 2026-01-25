---
phase: 04-multi-signal-scoring-framework
plan: 01
subsystem: scoring
tags: [signal-weights, role-presets, multi-signal-scoring, configuration, typescript]

# Dependency graph
requires:
  - phase: 03-04
    provides: Hybrid Search Verification complete, RRF operational
provides:
  - SignalWeightConfig type with all 7 core signals (0-1 normalized)
  - Role-type presets (executive, manager, ic, default) with appropriate weight distributions
  - Environment variables for signal weight customization
  - Utility functions for weight resolution and normalization
affects: [phase-04-02-scoring-implementation, phase-04-03-response-enrichment]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SignalWeightConfig interface for configurable signal weights"
    - "Role-type presets pattern for executive/manager/ic/default searches"
    - "Weight normalization to ensure sum = 1.0"
    - "Request override pattern for per-search weight customization"

key-files:
  created:
    - services/hh-search-svc/src/signal-weights.ts
  modified:
    - services/hh-search-svc/src/config.ts

key-decisions:
  - "7 core signals: vectorSimilarity, levelMatch, specialtyMatch, techStackMatch, functionMatch, trajectoryFit, companyPedigree"
  - "Optional 8th signal: skillsMatch for skill-aware searches"
  - "Executive: function (0.25) and companyPedigree (0.20) weighted highest"
  - "IC: specialty (0.20) and techStack (0.20) weighted highest"
  - "Default weights sum to 1.0 - normalization applied only when needed"
  - "GEMINI_BLEND_WEIGHT default 0.7 for rerank score blending"

patterns-established:
  - "Pattern: resolveWeights(requestOverrides, roleType) for weight resolution"
  - "Pattern: normalizeWeights() for weight sum validation"
  - "Pattern: SIGNAL_WEIGHT_* environment variables for default customization"
  - "Pattern: parseRoleType() for string-to-RoleType with aliases"

# Metrics
duration: 8min
completed: 2026-01-24
---

# Phase 4 Plan 1: SignalWeightConfig Types and Role-Type Presets Summary

**Created signal weight configuration foundation with TypeScript types, role-type presets (executive/manager/ic/default), and environment variable support**

## Performance

- **Duration:** 8 min
- **Started:** 2026-01-24
- **Completed:** 2026-01-24
- **Tasks:** 2 (all auto tasks completed)
- **Files created:** 1
- **Files modified:** 1

## Accomplishments

- SignalWeightConfig interface with all 7 core signals (0-1 normalized)
- Optional skillsMatch signal for skill-aware searches
- RoleType union: `'executive' | 'manager' | 'ic' | 'default'`
- ROLE_WEIGHT_PRESETS with role-specific weight distributions
- normalizeWeights() ensures weights sum to 1.0
- resolveWeights() merges request overrides with role presets
- parseRoleType() converts strings to RoleType with common aliases
- SignalWeightEnvConfig interface with all 8 env config fields
- All SIGNAL_WEIGHT_* environment variables parsed with defaults
- GEMINI_BLEND_WEIGHT for rerank blending (default 0.7)
- getSignalWeightDefaults() export for integration

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create SignalWeightConfig types and role-type presets | a6d048a | signal-weights.ts |
| 2 | Add signal weight environment variables to config | 724c3d6 | config.ts |

## Files Created

- `services/hh-search-svc/src/signal-weights.ts` - Signal weight types, presets, and utility functions (273 lines)

## Files Modified

- `services/hh-search-svc/src/config.ts` - Added SignalWeightEnvConfig interface and env var parsing

## Verification Results

All verification criteria passed:

1. **TypeScript compiles without errors:**
   - `npm run typecheck --prefix services/hh-search-svc` - SUCCESS

2. **SignalWeightConfig interface defines all 7 signals:**
   - vectorSimilarity, levelMatch, specialtyMatch, techStackMatch, functionMatch, trajectoryFit, companyPedigree
   - Plus optional skillsMatch

3. **ROLE_WEIGHT_PRESETS has all 4 role types:**
   - executive: function (0.25), companyPedigree (0.20), levelMatch (0.20) weighted highest
   - manager: balanced weights (0.15 each with slight emphasis on trajectory)
   - ic: specialty (0.20), techStack (0.20), vectorSimilarity (0.20) weighted highest
   - default: balanced across all signals (0.15 each, 0.10 for trajectory)

4. **Environment variables parsed:**
   - SIGNAL_WEIGHT_VECTOR (default 0.15)
   - SIGNAL_WEIGHT_LEVEL (default 0.15)
   - SIGNAL_WEIGHT_SPECIALTY (default 0.15)
   - SIGNAL_WEIGHT_TECH_STACK (default 0.15)
   - SIGNAL_WEIGHT_FUNCTION (default 0.15)
   - SIGNAL_WEIGHT_TRAJECTORY (default 0.10)
   - SIGNAL_WEIGHT_COMPANY (default 0.15)
   - GEMINI_BLEND_WEIGHT (default 0.7)

## Technical Details

### SignalWeightConfig Interface

```typescript
export interface SignalWeightConfig {
  vectorSimilarity: number;  // Vector similarity from hybrid search
  levelMatch: number;        // Level/seniority match score
  specialtyMatch: number;    // Specialty match (backend, frontend, etc)
  techStackMatch: number;    // Tech stack compatibility
  functionMatch: number;     // Function alignment (engineering, product, etc)
  trajectoryFit: number;     // Career trajectory fit
  companyPedigree: number;   // Company pedigree score
  skillsMatch?: number;      // Skills match (optional, for skill-aware searches)
}
```

### Role-Type Weight Presets

| Signal | Executive | Manager | IC | Default |
|--------|-----------|---------|-----|---------|
| vectorSimilarity | 0.10 | 0.15 | 0.20 | 0.15 |
| levelMatch | 0.20 | 0.15 | 0.15 | 0.15 |
| specialtyMatch | 0.05 | 0.15 | 0.20 | 0.15 |
| techStackMatch | 0.05 | 0.10 | 0.20 | 0.15 |
| functionMatch | 0.25 | 0.15 | 0.10 | 0.15 |
| trajectoryFit | 0.15 | 0.15 | 0.10 | 0.10 |
| companyPedigree | 0.20 | 0.15 | 0.05 | 0.15 |
| **Sum** | 1.00 | 1.00 | 1.00 | 1.00 |

### Weight Resolution Flow

```typescript
// 1. Get base weights from role preset
const baseWeights = ROLE_WEIGHT_PRESETS[roleType];

// 2. Merge request overrides (if any)
const merged = { ...baseWeights, ...requestWeights };

// 3. Normalize if sum != 1.0
return normalizeWeights(merged);
```

### parseRoleType() Aliases

- executive: 'c-level', 'vp', 'director', 'exec'
- manager: 'engineering-manager', 'tech-lead', 'team-lead', 'mgr'
- ic: 'senior', 'mid', 'junior', 'individual-contributor', 'engineer'

## Deviations from Plan

None - plan executed exactly as written.

## Success Criteria Met

- [x] SignalWeightConfig type is defined with all 7 core signals
- [x] ROLE_WEIGHT_PRESETS has 4 role types with appropriate weight distributions
- [x] Environment variables allow customization of default weights
- [x] resolveWeights correctly merges and normalizes weight configurations
- [x] All TypeScript types compile without errors

## Next Phase Readiness

Ready for Plan 04-02 (Scoring Implementation):
- SignalWeightConfig type available for use in search-service.ts
- resolveWeights() can be called to get final weight configuration
- Environment variables allow A/B testing of different weight values
- Role presets enable automatic weight selection based on job type

---
*Phase: 04-multi-signal-scoring-framework*
*Plan: 01*
*Completed: 2026-01-24*
