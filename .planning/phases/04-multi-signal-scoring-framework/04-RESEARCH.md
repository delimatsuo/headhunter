# Phase 4: Multi-Signal Scoring Framework - Research

**Researched:** 2026-01-24
**Domain:** Scoring Infrastructure / Weighted Signal Combination / Role-Based Configuration
**Confidence:** HIGH

## Summary

Phase 4 focuses on building a configurable multi-signal scoring framework that computes weighted combinations of signals for candidate ranking. The existing codebase already has substantial scoring infrastructure implemented during Phase 2, including 5 scoring signals (`_level_score`, `_specialty_score`, `_tech_stack_score`, `_function_title_score`, `_trajectory_score`) and a `phase2Multiplier` aggregation mechanism in `legacy-engine.ts`.

The primary gap is that the current implementation:
1. Uses hardcoded weight values (not configurable per search or role type)
2. Has different weight profiles (executive vs IC) but they're embedded in code
3. Does not expose signal breakdown in a standardized format to the frontend
4. Has multiple scoring paths (legacy-engine, vector-search, skill-aware-search, hh-search-svc) with inconsistent weight handling

**Primary recommendation:** Unify the scoring configuration into a single `SignalWeightConfig` structure that can be passed through the search request, stored as role-type defaults, and exposed in the response for transparency. This builds on existing Phase 2 infrastructure without replacing it.

## Standard Stack

The system already has all required infrastructure. No new libraries needed.

### Core (Already in Use)
| Component | Version | Purpose | Status |
|-----------|---------|---------|--------|
| TypeScript interfaces | N/A | Type-safe weight configuration | Extend existing types |
| Environment variables | N/A | Default weight configuration | Add new env vars |
| JSON configuration | N/A | Role-type weight presets | New file needed |

### Supporting (Already in Use)
| Component | Purpose | Status |
|-----------|---------|--------|
| `SearchRuntimeConfig` | Runtime search configuration | Extend with signal weights |
| `HybridSearchRequest` | Request with weight overrides | Add weights field |
| `score_breakdown` object | Signal breakdown in response | Already implemented |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| JSON config file | Database table | More complex but supports tenant-level config |
| Static role presets | ML-learned weights | Requires training data, deferred to future |
| Single weight object | Hierarchical weights | Simpler, sufficient for current needs |

**No new dependencies required** - this is a configuration and interface refactoring exercise.

## Architecture Patterns

### Current Scoring Data Flow

```
Phase 2 Signals (legacy-engine.ts)
     |
     v
[1] Pre-computed scores on candidate objects:
    - _level_score (0-1)
    - _specialty_score (0-1)
    - _tech_stack_score (0-1)
    - _function_title_score (0-1)
    - _trajectory_score (0-1)
     |
     v
[2] Phase 2 Multiplier (average of all 5 signals):
    phase2Multiplier = (level + specialty + tech + function + trajectory) / 5
     |
     v
[3] Base Score (mode-specific weights):
    Executive: { function: 50, vector: 15, company: 25, level: 35, specialty: 0 }
    IC:        { function: 25, vector: 25, company: 10, level: 15, specialty: 25 }
     |
     v
[4] Retrieval Score:
    retrievalScore = baseScore * Math.max(0.3, phase2Multiplier)
     |
     v
[5] Final Score (Gemini blend):
    overallScore = (geminiScore * 0.7) + (retrievalScore * 0.3)
```

**Key observation:** The current system has TWO weight systems that interact:
1. **Mode-specific base weights** (lines 385-387) - different for executive vs IC
2. **Phase 2 multiplier** (lines 519-525) - uniform averaging of all signals

### Target Scoring Data Flow

```
Search Request (with optional weights)
     |
     v
[1] Resolve Weight Configuration:
    - Check request.signalWeights (override)
    - Else: Load role-type preset (executive/manager/ic)
    - Else: Use default weights from config
     |
     v
[2] Compute Signal Scores (existing logic):
    - vectorSimilarity (0-1) from hybrid search
    - levelScore (0-1) from Phase 2
    - specialtyScore (0-1) from Phase 2
    - techStackScore (0-1) from Phase 2
    - functionScore (0-1) from Phase 2
    - trajectoryScore (0-1) from Phase 2
    - companyScore (0-1) normalized
     |
     v
[3] Weighted Combination:
    finalScore = sum(signal * weight) / sum(weights)
    OR
    finalScore = sum(signal * weight)  // if weights sum to 1.0
     |
     v
[4] Score Breakdown in Response:
    {
      finalScore: 0.82,
      signalScores: {
        vectorSimilarity: 0.75,
        levelMatch: 0.90,
        specialtyMatch: 1.0,
        techStackMatch: 0.60,
        functionMatch: 0.85,
        trajectoryFit: 0.80,
        companyPedigree: 0.50
      },
      weightsApplied: { ... },
      roleTypeUsed: 'ic'
    }
```

### Key Architectural Principle

**Single Source of Truth for Weights**

All scoring paths should read from a unified weight configuration:
- `hh-search-svc` for the new hybrid search path
- `legacy-engine.ts` for the functions-based path
- `skill-aware-search.ts` for the skill-focused path

The configuration should be:
1. **Environment-configurable** (defaults)
2. **Request-overridable** (per-search customization)
3. **Role-type aware** (presets for executive/manager/ic)

## Recommended Configuration Structure

### Signal Weight Types

```typescript
// services/hh-search-svc/src/types.ts (extend)

/**
 * Signal weight configuration for multi-signal scoring.
 * All weights should sum to 1.0 for normalized scoring.
 */
export interface SignalWeightConfig {
  /** Vector similarity from hybrid search (0-1) */
  vectorSimilarity: number;

  /** Level/seniority match score (0-1) */
  levelMatch: number;

  /** Specialty match score (0-1) - backend, frontend, etc */
  specialtyMatch: number;

  /** Tech stack compatibility score (0-1) */
  techStackMatch: number;

  /** Function alignment score (0-1) - engineering, product, etc */
  functionMatch: number;

  /** Career trajectory fit score (0-1) */
  trajectoryFit: number;

  /** Company pedigree score (0-1) */
  companyPedigree: number;

  /** Skills match score (0-1) - for skill-aware searches */
  skillsMatch?: number;

  /** Recency boost (0-1) - recent skill usage */
  recencyBoost?: number;
}

export type RoleType = 'executive' | 'manager' | 'ic' | 'default';

export interface SignalWeightPresets {
  executive: SignalWeightConfig;
  manager: SignalWeightConfig;
  ic: SignalWeightConfig;
  default: SignalWeightConfig;
}
```

### Default Weight Presets

Based on analysis of existing code (legacy-engine.ts lines 385-387):

```typescript
// Configuration (config.ts or separate weights.config.ts)

export const DEFAULT_SIGNAL_WEIGHTS: SignalWeightPresets = {
  // Executive searches (C-level, VP, Director)
  // Function and company matter most - they hire for fit and pedigree
  executive: {
    vectorSimilarity: 0.10,
    levelMatch: 0.20,
    specialtyMatch: 0.05,
    techStackMatch: 0.05,
    functionMatch: 0.25,
    trajectoryFit: 0.15,
    companyPedigree: 0.20
  },

  // Manager searches
  // Balance of skills, trajectory, and function
  manager: {
    vectorSimilarity: 0.15,
    levelMatch: 0.15,
    specialtyMatch: 0.15,
    techStackMatch: 0.10,
    functionMatch: 0.15,
    trajectoryFit: 0.15,
    companyPedigree: 0.15
  },

  // IC searches (Senior, Mid, Junior)
  // Specialty and tech stack matter most - exact skill fit
  ic: {
    vectorSimilarity: 0.20,
    levelMatch: 0.15,
    specialtyMatch: 0.20,
    techStackMatch: 0.20,
    functionMatch: 0.10,
    trajectoryFit: 0.10,
    companyPedigree: 0.05
  },

  // Default fallback (balanced)
  default: {
    vectorSimilarity: 0.15,
    levelMatch: 0.15,
    specialtyMatch: 0.15,
    techStackMatch: 0.15,
    functionMatch: 0.15,
    trajectoryFit: 0.10,
    companyPedigree: 0.15
  }
};
```

### Request Extension

```typescript
// Extend HybridSearchRequest
export interface HybridSearchRequest {
  // ... existing fields ...

  /**
   * Override signal weights for this search.
   * If not provided, role-type defaults are used.
   * Weights should sum to 1.0.
   */
  signalWeights?: Partial<SignalWeightConfig>;

  /**
   * Role type for weight preset selection.
   * Inferred from job classification if not provided.
   */
  roleType?: RoleType;
}
```

### Response Extension

```typescript
// Extend HybridSearchResultItem
export interface HybridSearchResultItem {
  // ... existing fields ...

  /**
   * Individual signal scores (0-1 normalized)
   */
  signalScores?: {
    vectorSimilarity: number;
    levelMatch: number;
    specialtyMatch: number;
    techStackMatch: number;
    functionMatch: number;
    trajectoryFit: number;
    companyPedigree: number;
    skillsMatch?: number;
  };

  /**
   * Weights that were applied to compute finalScore
   */
  weightsApplied?: SignalWeightConfig;

  /**
   * Which role type preset was used
   */
  roleTypeUsed?: RoleType;
}
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Weight normalization | Custom normalization logic | Require weights sum to 1.0 | Simpler, explicit contract |
| Role detection | New classification service | Use existing job-classification-service | Already works |
| Score aggregation | Complex formula engine | Simple weighted sum | Explainable, debuggable |
| Per-tenant config | Custom database schema | Environment variables + request overrides | Phase 1 simplicity |

**Key insight:** The existing Phase 2 scoring signals are well-designed (0-1 normalized). The framework just needs to make weights configurable and expose scores in responses.

## Common Pitfalls

### Pitfall 1: Weights Don't Sum to 1.0
**What goes wrong:** If weights sum to 0.5, final scores are half expected; if 1.5, scores are inflated
**Why it happens:** User provides partial weight override
**How to avoid:**
- Validate weights sum to 1.0 (with tolerance 0.001)
- Or: Normalize provided weights: `weight / sum(weights)`
- Log warning if normalization applied
**Warning signs:** Final scores consistently above 100 or below 50

### Pitfall 2: Missing Signals Crash Scoring
**What goes wrong:** `finalScore = undefined * 0.2` produces NaN
**Why it happens:** Some signals not computed for all candidates
**How to avoid:**
- Default missing signals to 0.5 (neutral)
- Use nullish coalescing: `(signal ?? 0.5) * weight`
- Log when signals are missing
**Warning signs:** NaN or undefined in score outputs

### Pitfall 3: Weight Config Inconsistency Across Paths
**What goes wrong:** Legacy engine uses one weight set, hh-search-svc uses another
**Why it happens:** Multiple scoring paths evolved independently
**Current state:**
- `legacy-engine.ts`: Hardcoded executive/IC weights
- `hh-search-svc`: Uses config.search.vectorWeight/textWeight
- `skill-aware-search.ts`: Uses ranking_weights from request
**How to avoid:**
- Create shared weight configuration module
- All paths import from same source
- Request overrides flow through consistently

### Pitfall 4: Role Type Detection Inconsistency
**What goes wrong:** Same job gets different role type in different code paths
**Current implementation:**
- `legacy-engine.ts` line 126: `isExecutiveSearch = ['c-level', 'vp', 'director'].includes(targetClassification.level)`
- `api.ts` line 186-197: Custom `parseLevel()` function
**How to avoid:**
- Use single role type detection (job-classification-service)
- Pass role type through request context
- Log detected role type for debugging

### Pitfall 5: Gemini Score Overwrites Everything
**What goes wrong:** Careful signal weighting is discarded by final Gemini blend
**Current code (legacy-engine.ts line 679):**
```typescript
const overallScore = (geminiScore * 0.7) + (retrievalScore * 0.3);
```
**How to avoid:**
- Make Gemini blend weight configurable
- Consider: Gemini rerank ORDER, not score replacement
- Or: Gemini provides one signal among many

## Code Examples

### Example 1: Unified Weight Configuration Module

```typescript
// services/common/src/signal-weights.ts

export interface SignalWeightConfig {
  vectorSimilarity: number;
  levelMatch: number;
  specialtyMatch: number;
  techStackMatch: number;
  functionMatch: number;
  trajectoryFit: number;
  companyPedigree: number;
  skillsMatch?: number;
}

export type RoleType = 'executive' | 'manager' | 'ic' | 'default';

export const ROLE_WEIGHT_PRESETS: Record<RoleType, SignalWeightConfig> = {
  executive: {
    vectorSimilarity: 0.10,
    levelMatch: 0.20,
    specialtyMatch: 0.05,
    techStackMatch: 0.05,
    functionMatch: 0.25,
    trajectoryFit: 0.15,
    companyPedigree: 0.20
  },
  manager: {
    vectorSimilarity: 0.15,
    levelMatch: 0.15,
    specialtyMatch: 0.15,
    techStackMatch: 0.10,
    functionMatch: 0.15,
    trajectoryFit: 0.15,
    companyPedigree: 0.15
  },
  ic: {
    vectorSimilarity: 0.20,
    levelMatch: 0.15,
    specialtyMatch: 0.20,
    techStackMatch: 0.20,
    functionMatch: 0.10,
    trajectoryFit: 0.10,
    companyPedigree: 0.05
  },
  default: {
    vectorSimilarity: 0.15,
    levelMatch: 0.15,
    specialtyMatch: 0.15,
    techStackMatch: 0.15,
    functionMatch: 0.15,
    trajectoryFit: 0.10,
    companyPedigree: 0.15
  }
};

export function resolveWeights(
  requestWeights: Partial<SignalWeightConfig> | undefined,
  roleType: RoleType = 'default'
): SignalWeightConfig {
  const baseWeights = ROLE_WEIGHT_PRESETS[roleType];

  if (!requestWeights) {
    return baseWeights;
  }

  // Merge request overrides with base weights
  const merged = { ...baseWeights, ...requestWeights };

  // Normalize if sum != 1.0
  const sum = Object.values(merged).reduce((a, b) => a + (b ?? 0), 0);
  if (Math.abs(sum - 1.0) > 0.001) {
    console.warn(`[SignalWeights] Normalizing weights (sum was ${sum.toFixed(3)})`);
    return Object.fromEntries(
      Object.entries(merged).map(([k, v]) => [k, (v ?? 0) / sum])
    ) as SignalWeightConfig;
  }

  return merged;
}
```

### Example 2: Compute Weighted Score

```typescript
// services/common/src/scoring.ts

export interface SignalScores {
  vectorSimilarity: number;
  levelMatch: number;
  specialtyMatch: number;
  techStackMatch: number;
  functionMatch: number;
  trajectoryFit: number;
  companyPedigree: number;
  skillsMatch?: number;
}

export function computeWeightedScore(
  signals: Partial<SignalScores>,
  weights: SignalWeightConfig
): number {
  let score = 0;
  let appliedWeight = 0;

  // Vector similarity
  const vs = signals.vectorSimilarity ?? 0.5;
  score += vs * weights.vectorSimilarity;
  appliedWeight += weights.vectorSimilarity;

  // Level match
  const lm = signals.levelMatch ?? 0.5;
  score += lm * weights.levelMatch;
  appliedWeight += weights.levelMatch;

  // Specialty match
  const sm = signals.specialtyMatch ?? 0.5;
  score += sm * weights.specialtyMatch;
  appliedWeight += weights.specialtyMatch;

  // Tech stack match
  const ts = signals.techStackMatch ?? 0.5;
  score += ts * weights.techStackMatch;
  appliedWeight += weights.techStackMatch;

  // Function match
  const fm = signals.functionMatch ?? 0.5;
  score += fm * weights.functionMatch;
  appliedWeight += weights.functionMatch;

  // Trajectory fit
  const tf = signals.trajectoryFit ?? 0.5;
  score += tf * weights.trajectoryFit;
  appliedWeight += weights.trajectoryFit;

  // Company pedigree
  const cp = signals.companyPedigree ?? 0.5;
  score += cp * weights.companyPedigree;
  appliedWeight += weights.companyPedigree;

  // Skills match (optional)
  if (signals.skillsMatch !== undefined && weights.skillsMatch) {
    score += signals.skillsMatch * weights.skillsMatch;
    appliedWeight += weights.skillsMatch;
  }

  // Normalize if not all weights were applied
  return appliedWeight > 0 ? score / appliedWeight * appliedWeight : score;
}
```

### Example 3: Environment Configuration

```typescript
// services/hh-search-svc/src/config.ts (additions)

export interface SignalWeightEnvConfig {
  defaultVectorWeight: number;
  defaultLevelWeight: number;
  defaultSpecialtyWeight: number;
  defaultTechStackWeight: number;
  defaultFunctionWeight: number;
  defaultTrajectoryWeight: number;
  defaultCompanyWeight: number;
  geminiBlendWeight: number;
}

// In getSearchServiceConfig():
const signalWeights: SignalWeightEnvConfig = {
  defaultVectorWeight: parseNumber(process.env.SIGNAL_WEIGHT_VECTOR, 0.15),
  defaultLevelWeight: parseNumber(process.env.SIGNAL_WEIGHT_LEVEL, 0.15),
  defaultSpecialtyWeight: parseNumber(process.env.SIGNAL_WEIGHT_SPECIALTY, 0.15),
  defaultTechStackWeight: parseNumber(process.env.SIGNAL_WEIGHT_TECH_STACK, 0.15),
  defaultFunctionWeight: parseNumber(process.env.SIGNAL_WEIGHT_FUNCTION, 0.15),
  defaultTrajectoryWeight: parseNumber(process.env.SIGNAL_WEIGHT_TRAJECTORY, 0.10),
  defaultCompanyWeight: parseNumber(process.env.SIGNAL_WEIGHT_COMPANY, 0.15),
  geminiBlendWeight: parseNumber(process.env.GEMINI_BLEND_WEIGHT, 0.7)
};
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded weights | Configurable weights | Phase 4 | A/B testing, role-specific tuning |
| Single weight set | Role-type presets | Phase 4 | Better fit for executive vs IC |
| Implicit signals | Explicit signal breakdown | Phase 4 | Transparency, debugging |
| Phase 2 multiplier (average) | Weighted combination | Phase 4 | More control over signal importance |

**Deprecated/outdated:**
- Phase 2 simple averaging (`phase2Multiplier = signals / 5`) - Replace with configurable weights

**Current best practice:**
- Configurable signal weights per search or role type
- Weights sum to 1.0 for predictable scoring
- All signals exposed in response for transparency
- Role type inferred from job classification but overridable

## Mapping to Existing Code

### SCOR-01: Vector similarity score (0-1) as baseline signal

**Already implemented:**
- `hh-search-svc/src/types.ts` line 35: `vectorScore: number;`
- `legacy-engine.ts` line 148: `_raw_vector_similarity: c.vector_similarity_score`
- `vector-search.ts` line 840: `vector_similarity_score: vectorResult.similarity_score * 100`

**Action:** Normalize to 0-1 consistently (some places use 0-100)

### SCOR-07: Configurable signal weights per search or role type

**Partially implemented:**
- `api.ts` lines 138-151: `ranking_weights` in request
- `skill-aware-search.ts` lines 397-402: Default weights with override
- `legacy-engine.ts` lines 385-387: Hardcoded executive/IC weights

**Action:**
1. Create unified SignalWeightConfig type
2. Add role-type presets (executive/manager/ic)
3. Flow weights through all scoring paths
4. Add environment variable defaults

### SCOR-08: Final score as weighted combination of all signals

**Already implemented (partially):**
- `legacy-engine.ts` lines 506-531: Phase 2 multiplier aggregation
- `skill-aware-search.ts` lines 418-422: Weighted sum
- `search-service.ts` lines 443-464: Skill boost ranking

**Action:**
1. Unify aggregation formula across paths
2. Use SignalWeightConfig consistently
3. Add signal breakdown to response

## Open Questions

### 1. Gemini Blend Weight
**What we know:** Currently hardcoded at 70% Gemini, 30% retrieval (line 679)
**What's unclear:** Should this be a configurable signal or a post-scoring adjustment?
**Recommendation:**
- Make it configurable via `GEMINI_BLEND_WEIGHT` env var
- Consider: Gemini provides ORDER, multi-signal provides SCORE
- Document the two-stage model clearly

### 2. Skills Match Integration
**What we know:** `skill-aware-search.ts` has separate skill matching logic
**What's unclear:** How to unify with Phase 2 signals
**Recommendation:**
- Add `skillsMatch` as optional 8th signal
- Compute when `required_skills` are provided in request
- Default to 0.5 (neutral) when not available

### 3. Tenant-Level Configuration
**What we know:** Current system doesn't support per-tenant weights
**What's unclear:** Is this needed for v1?
**Recommendation:**
- Defer to post-Phase 10
- Request-level overrides are sufficient for now
- Document as future enhancement

## Success Criteria

| Metric | Current | Target | How to Measure |
|--------|---------|--------|----------------|
| Weight configurability | Hardcoded | Per-search + role presets | Code review |
| Signal score exposure | Partial | All 7+ signals in response | API response check |
| Role-type presets | 2 (exec/IC) | 4 (exec/manager/ic/default) | Config review |
| Normalized scoring | Inconsistent (0-100, 0-1) | All 0-1 | Type enforcement |

## Sources

### Primary (HIGH confidence)
- `functions/src/engines/legacy-engine.ts` - Current scoring implementation
- `services/hh-search-svc/src/search-service.ts` - Hybrid search scoring
- `services/hh-search-svc/src/config.ts` - Current configuration patterns
- `functions/src/skill-aware-search.ts` - Skill-aware scoring patterns

### Secondary (MEDIUM confidence)
- `headhunter-ui/src/services/api.ts` - Frontend weight expectations
- `.planning/phases/02-search-recall-foundation/02-RESEARCH.md` - Phase 2 signal design

### Tertiary (LOW confidence)
- N/A - All findings based on direct code analysis

## Metadata

**Confidence breakdown:**
- Signal identification: HIGH - Traced all 7+ signals in code
- Weight configuration design: HIGH - Standard pattern, well-documented
- Integration approach: HIGH - Builds on existing Phase 2 infrastructure
- Performance impact: HIGH - No additional computation, just configuration

**Research date:** 2026-01-24
**Valid until:** Until major changes to scoring architecture

---

## Implementation Notes for Planner

### Dependency Chain

1. **Create SignalWeightConfig types** - Foundation for all other work
   - Files: `services/common/src/signal-weights.ts` (new)
   - Or: `services/hh-search-svc/src/types.ts` (extend)

2. **Add role-type weight presets** - Configuration layer
   - Files: `services/hh-search-svc/src/config.ts`
   - Environment variables: `SIGNAL_WEIGHT_*`

3. **Update HybridSearchRequest** - Request-level override support
   - Files: `services/hh-search-svc/src/types.ts`

4. **Update HybridSearchResponse** - Expose signal breakdown
   - Files: `services/hh-search-svc/src/types.ts`

5. **Implement weighted scoring in search-service.ts** - Core logic
   - File: `services/hh-search-svc/src/search-service.ts`

6. **Backport to legacy-engine.ts** - Consistency (optional)
   - File: `functions/src/engines/legacy-engine.ts`

### Testing Strategy

1. **Unit tests for weight resolution:**
   ```typescript
   expect(resolveWeights(undefined, 'executive')).toEqual(ROLE_WEIGHT_PRESETS.executive);
   expect(resolveWeights({ vectorSimilarity: 0.5 }, 'ic').vectorSimilarity).toBe(0.5);
   ```

2. **Unit tests for weighted scoring:**
   ```typescript
   const signals = { vectorSimilarity: 1.0, levelMatch: 0.5, ... };
   const weights = ROLE_WEIGHT_PRESETS.ic;
   expect(computeWeightedScore(signals, weights)).toBeCloseTo(0.75, 2);
   ```

3. **Integration tests:**
   - Search with no weight override uses role-type default
   - Search with weight override uses provided weights
   - Response includes signal breakdown

### Estimated Effort

- Type definitions: 1-2 hours
- Configuration: 1-2 hours
- Scoring implementation: 2-3 hours
- Response enrichment: 1-2 hours
- Testing: 2-3 hours
- Documentation: 1 hour
- Total: 8-13 hours

### Risk Mitigation

- **Feature flag:** `ENABLE_CONFIGURABLE_WEIGHTS=true/false` to toggle new behavior
- **Gradual rollout:** Start with hh-search-svc, then backport to legacy-engine
- **Logging:** Log weight configuration and resulting scores for debugging
