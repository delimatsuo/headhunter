# Phase 7: Signal Scoring Implementation - Research

**Researched:** 2026-01-24
**Domain:** Multi-Signal Scoring / Skills Matching / Seniority Alignment / Recency / Company Relevance
**Confidence:** HIGH

## Summary

Phase 7 implements 5 remaining scoring signals to complete the multi-signal scoring framework established in Phase 4. The codebase already has strong infrastructure:

1. **Existing Framework (Phase 4):** `SignalWeightConfig` with 7 core signals, `ROLE_WEIGHT_PRESETS`, `computeWeightedScore()`, and `extractSignalScores()` reading from metadata `_*_score` fields
2. **Skill Intelligence (Phase 6):** `skills-graph.ts` with `expandSkills()`, `getCachedSkillExpansion()`, and `skills-inference.ts` with `inferSkillsFromTitle()`, `findTransferableSkills()`
3. **Legacy Scoring (legacy-engine.ts):** Already implements Phase 2 signals (`_level_score`, `_specialty_score`, `_tech_stack_score`, `_function_title_score`, `_trajectory_score`) as 0-1 normalized values

The 5 signals to implement are discrete scoring functions that compute 0-1 normalized values based on available data, with neutral fallbacks (0.5) when data is missing.

**Primary recommendation:** Implement each signal as a pure function in a new `signal-calculators.ts` module, integrate via `extractSignalScores()`, and extend `SignalWeightConfig`/`SignalScores` types to include the new signals.

## Standard Stack

### Core (Already Available)
| Component | Purpose | Status |
|-----------|---------|--------|
| `signal-weights.ts` | SignalWeightConfig, ROLE_WEIGHT_PRESETS, normalizeWeights() | Extend with 5 new signals |
| `scoring.ts` | computeWeightedScore(), extractSignalScores() | Modify to include new signals |
| `types.ts` | SignalScores interface | Extend with new signal types |
| `skills-service.ts` | normalizeSkillName(), skillsMatch(), expandSkills() | Use for skill scoring |
| `skills-inference.ts` | findTransferableSkills() | Use for inferred skills |

### Supporting
| Component | Purpose | When to Use |
|-----------|---------|-------------|
| PostgreSQL `sourcing.candidates` | `intelligent_analysis` JSONB with skills, experience, company data | Source for all candidate data |
| PostgreSQL `sourcing.experience` | `start_date`, `end_date`, `is_current`, `company_name` | Recency boost calculation |
| PostgreSQL `sourcing.candidate_skills` | `skill_id`, `confidence_score`, `is_inferred` | Skills matching |
| `TOP_COMPANIES` list in `legacy-engine.ts` | Company pedigree reference | Company relevance scoring |

### No New Dependencies Required
All scoring logic uses existing infrastructure. No external libraries needed.

## Architecture Patterns

### Recommended Project Structure
```
services/hh-search-svc/src/
├── signal-weights.ts      # SignalWeightConfig with 5 new signals
├── scoring.ts             # computeWeightedScore (modify)
├── signal-calculators.ts  # NEW: Pure functions for each signal
└── types.ts               # SignalScores with 5 new fields
```

### Pattern 1: Signal Calculator as Pure Function
**What:** Each signal is a pure function that takes candidate data and query context, returns 0-1 score
**When to use:** All 5 new signals
**Why:** Testable, composable, no side effects

```typescript
// services/hh-search-svc/src/signal-calculators.ts

interface SkillMatchContext {
  requiredSkills: string[];
  preferredSkills: string[];
}

interface SeniorityContext {
  targetLevel: string;  // 'junior' | 'mid' | 'senior' | 'manager' | 'director' | 'vp' | 'c-level'
  roleType: RoleType;
}

interface CompanyContext {
  targetCompanies?: string[];
  targetIndustries?: string[];
}

/**
 * SCOR-02: Skills Exact Match Score (0-1)
 *
 * Measures how many required skills the candidate has.
 * Uses skill normalization and alias matching from skills-service.
 */
export function calculateSkillsExactMatch(
  candidateSkills: string[],
  context: SkillMatchContext
): number {
  if (!context.requiredSkills || context.requiredSkills.length === 0) {
    return 0.5; // Neutral when no skills required
  }

  let matchCount = 0;

  for (const required of context.requiredSkills) {
    const hasSkill = candidateSkills.some(cs =>
      skillsMatch(cs, required)
    );
    if (hasSkill) matchCount++;
  }

  // Score = ratio of matched to required
  return matchCount / context.requiredSkills.length;
}

/**
 * SCOR-03: Skills Inferred Score (0-1)
 *
 * Measures match through related/transferable skills.
 * Uses skill graph expansion from skills-graph.ts.
 */
export function calculateSkillsInferred(
  candidateSkills: string[],
  context: SkillMatchContext
): number {
  if (!context.requiredSkills || context.requiredSkills.length === 0) {
    return 0.5; // Neutral when no skills required
  }

  let totalConfidence = 0;
  let expandedMatches = 0;

  for (const required of context.requiredSkills) {
    // Skip if already exact match
    const isExact = candidateSkills.some(cs => skillsMatch(cs, required));
    if (isExact) continue;

    // Expand required skill to find related matches
    const expansion = getCachedSkillExpansion(required, 2);

    for (const related of expansion.relatedSkills) {
      const hasRelated = candidateSkills.some(cs =>
        skillsMatch(cs, related.skillName)
      );
      if (hasRelated) {
        totalConfidence += related.confidence; // 0.6-0.9 based on distance
        expandedMatches++;
        break; // Only count first match per required skill
      }
    }
  }

  if (expandedMatches === 0) return 0.0; // No inferred matches

  // Average confidence of inferred matches, scaled by coverage
  const avgConfidence = totalConfidence / expandedMatches;
  const coverage = expandedMatches / context.requiredSkills.length;

  return avgConfidence * coverage;
}

/**
 * SCOR-04: Seniority Alignment Score (0-1)
 *
 * Measures how well candidate level aligns with target.
 * Accounts for company tier adjustments (FAANG Senior = Startup Staff).
 */
export function calculateSeniorityAlignment(
  candidateLevel: string | null,
  companyTier: number, // 0=startup, 1=mid, 2=FAANG
  context: SeniorityContext
): number {
  if (!candidateLevel || candidateLevel === 'unknown') {
    return 0.5; // Neutral for unknown level
  }

  const levelOrder = ['intern', 'junior', 'mid', 'senior', 'staff', 'principal',
                      'manager', 'director', 'vp', 'c-level'];

  const candidateIndex = levelOrder.indexOf(candidateLevel.toLowerCase());
  const targetIndex = levelOrder.indexOf(context.targetLevel.toLowerCase());

  if (candidateIndex === -1 || targetIndex === -1) {
    return 0.5; // Unknown level mapping
  }

  // Apply company tier adjustment (FAANG +1, Startup -1)
  const effectiveIndex = Math.min(
    Math.max(0, candidateIndex + (companyTier - 1)),
    levelOrder.length - 1
  );

  const distance = Math.abs(effectiveIndex - targetIndex);

  // Score based on distance
  if (distance === 0) return 1.0;   // Exact match
  if (distance === 1) return 0.8;   // One level off
  if (distance === 2) return 0.6;   // Two levels off
  if (distance === 3) return 0.4;   // Three levels off
  return 0.2;                        // More than three levels
}

/**
 * SCOR-05: Recency Boost Score (0-1)
 *
 * Boosts candidates with recent skill usage.
 * Uses experience dates to determine recency.
 */
export function calculateRecencyBoost(
  candidateExperience: Array<{
    title: string;
    skills?: string[];
    startDate?: Date | string;
    endDate?: Date | string | null;
    isCurrent?: boolean;
  }>,
  requiredSkills: string[]
): number {
  if (!requiredSkills || requiredSkills.length === 0) {
    return 0.5; // Neutral when no skills specified
  }

  if (!candidateExperience || candidateExperience.length === 0) {
    return 0.5; // Neutral when no experience data
  }

  const now = new Date();
  let totalRecencyScore = 0;
  let skillsWithRecency = 0;

  for (const skill of requiredSkills) {
    // Find most recent experience using this skill
    let bestRecency = 0;

    for (const exp of candidateExperience) {
      const expSkills = exp.skills || [];
      const hasSkill = expSkills.some(es => skillsMatch(es, skill));

      if (!hasSkill) continue;

      // Calculate recency (years since end, 0 for current)
      if (exp.isCurrent) {
        bestRecency = Math.max(bestRecency, 1.0); // Current = full recency
      } else if (exp.endDate) {
        const endDate = new Date(exp.endDate);
        const yearsSince = (now.getTime() - endDate.getTime()) / (365.25 * 24 * 60 * 60 * 1000);

        // Decay: 1.0 at 0 years, 0.5 at 2 years, 0.2 at 5 years
        const recency = Math.max(0.1, 1.0 - (yearsSince * 0.16));
        bestRecency = Math.max(bestRecency, recency);
      }
    }

    if (bestRecency > 0) {
      totalRecencyScore += bestRecency;
      skillsWithRecency++;
    }
  }

  if (skillsWithRecency === 0) return 0.3; // Skills not found in experience

  return totalRecencyScore / requiredSkills.length;
}

/**
 * SCOR-06: Company Relevance Score (0-1)
 *
 * Scores based on company tier, target company match, and industry fit.
 */
export function calculateCompanyRelevance(
  candidateCompanies: string[],
  candidateIndustries: string[],
  companyTier: number,
  context: CompanyContext
): number {
  let score = 0.0;
  let signals = 0;

  // Signal 1: Target company match (highest value)
  if (context.targetCompanies && context.targetCompanies.length > 0) {
    const hasTargetCompany = context.targetCompanies.some(tc =>
      candidateCompanies.some(cc =>
        cc.toLowerCase().includes(tc.toLowerCase()) ||
        tc.toLowerCase().includes(cc.toLowerCase())
      )
    );
    score += hasTargetCompany ? 1.0 : 0.0;
    signals++;
  }

  // Signal 2: Company tier (FAANG=1.0, Unicorn=0.7, Startup=0.3)
  const tierScore = companyTier >= 2 ? 1.0 : companyTier >= 1 ? 0.7 : 0.3;
  score += tierScore;
  signals++;

  // Signal 3: Industry alignment
  if (context.targetIndustries && context.targetIndustries.length > 0) {
    const hasMatchingIndustry = context.targetIndustries.some(ti =>
      candidateIndustries.some(ci =>
        ci.toLowerCase().includes(ti.toLowerCase()) ||
        ti.toLowerCase().includes(ci.toLowerCase())
      )
    );
    score += hasMatchingIndustry ? 1.0 : 0.3;
    signals++;
  }

  return signals > 0 ? score / signals : 0.5;
}
```

### Pattern 2: Extend SignalScores Interface
**What:** Add 5 new optional signal fields to SignalScores
**Why:** Backward compatible - new signals are optional

```typescript
// services/hh-search-svc/src/types.ts (extend)

export interface SignalScores {
  // Existing signals (Phase 4)
  vectorSimilarity: number;
  levelMatch: number;
  specialtyMatch: number;
  techStackMatch: number;
  functionMatch: number;
  trajectoryFit: number;
  companyPedigree: number;
  skillsMatch?: number;

  // NEW: Phase 7 signals (all 0-1 normalized)
  skillsExactMatch?: number;   // SCOR-02
  skillsInferred?: number;     // SCOR-03
  seniorityAlignment?: number; // SCOR-04
  recencyBoost?: number;       // SCOR-05
  companyRelevance?: number;   // SCOR-06
}
```

### Pattern 3: Extend SignalWeightConfig
**What:** Add weights for 5 new signals with role-type presets
**Why:** Different roles weight signals differently (IC cares about skills, exec cares about company)

```typescript
// services/hh-search-svc/src/signal-weights.ts (extend)

export interface SignalWeightConfig {
  // Existing weights
  vectorSimilarity: number;
  levelMatch: number;
  specialtyMatch: number;
  techStackMatch: number;
  functionMatch: number;
  trajectoryFit: number;
  companyPedigree: number;
  skillsMatch?: number;

  // NEW: Phase 7 weights
  skillsExactMatch?: number;
  skillsInferred?: number;
  seniorityAlignment?: number;
  recencyBoost?: number;
  companyRelevance?: number;
}

// Updated ROLE_WEIGHT_PRESETS with new signals
export const ROLE_WEIGHT_PRESETS: Record<RoleType, SignalWeightConfig> = {
  executive: {
    // Core signals (sum to ~0.80)
    vectorSimilarity: 0.08,
    levelMatch: 0.12,
    specialtyMatch: 0.03,
    techStackMatch: 0.03,
    functionMatch: 0.18,
    trajectoryFit: 0.12,
    companyPedigree: 0.14,
    // Phase 7 signals (sum to ~0.20)
    skillsExactMatch: 0.02,
    skillsInferred: 0.02,
    seniorityAlignment: 0.08,
    recencyBoost: 0.02,
    companyRelevance: 0.08
  },

  manager: {
    vectorSimilarity: 0.12,
    levelMatch: 0.10,
    specialtyMatch: 0.10,
    techStackMatch: 0.08,
    functionMatch: 0.12,
    trajectoryFit: 0.10,
    companyPedigree: 0.10,
    // Phase 7 signals
    skillsExactMatch: 0.06,
    skillsInferred: 0.04,
    seniorityAlignment: 0.08,
    recencyBoost: 0.04,
    companyRelevance: 0.06
  },

  ic: {
    vectorSimilarity: 0.15,
    levelMatch: 0.08,
    specialtyMatch: 0.12,
    techStackMatch: 0.12,
    functionMatch: 0.08,
    trajectoryFit: 0.06,
    companyPedigree: 0.04,
    // Phase 7 signals - skills matter most for IC
    skillsExactMatch: 0.12,
    skillsInferred: 0.08,
    seniorityAlignment: 0.06,
    recencyBoost: 0.06,
    companyRelevance: 0.03
  },

  default: {
    vectorSimilarity: 0.12,
    levelMatch: 0.10,
    specialtyMatch: 0.10,
    techStackMatch: 0.10,
    functionMatch: 0.10,
    trajectoryFit: 0.08,
    companyPedigree: 0.10,
    skillsExactMatch: 0.08,
    skillsInferred: 0.06,
    seniorityAlignment: 0.06,
    recencyBoost: 0.04,
    companyRelevance: 0.06
  }
};
```

### Pattern 4: Integrate into extractSignalScores()
**What:** Calculate new signals from row metadata
**When to use:** In search-service.ts hydrateResult()

```typescript
// services/hh-search-svc/src/scoring.ts (modify)

export function extractSignalScores(
  row: PgHybridSearchRow,
  searchContext?: {
    requiredSkills?: string[];
    preferredSkills?: string[];
    targetLevel?: string;
    targetCompanies?: string[];
    targetIndustries?: string[];
    roleType?: RoleType;
  }
): SignalScores {
  const metadata = row.metadata as Record<string, unknown> | null;

  // Existing signal extraction
  const scores: SignalScores = {
    vectorSimilarity: normalizeVectorScore(row.vector_score),
    levelMatch: extractScore(metadata, '_level_score'),
    specialtyMatch: extractScore(metadata, '_specialty_score'),
    techStackMatch: extractScore(metadata, '_tech_stack_score'),
    functionMatch: extractScore(metadata, '_function_title_score'),
    trajectoryFit: extractScore(metadata, '_trajectory_score'),
    companyPedigree: extractScore(metadata, '_company_score')
  };

  // Phase 7 signals (only compute if context provided)
  if (searchContext) {
    const candidateSkills = extractCandidateSkills(row);
    const candidateExperience = extractCandidateExperience(row);
    const candidateCompanies = extractCandidateCompanies(row);
    const candidateIndustries = (row.industries || []) as string[];
    const candidateLevel = extractCandidateLevel(row);
    const companyTier = extractCompanyTier(row);

    // SCOR-02: Skills exact match
    scores.skillsExactMatch = calculateSkillsExactMatch(candidateSkills, {
      requiredSkills: searchContext.requiredSkills || [],
      preferredSkills: searchContext.preferredSkills || []
    });

    // SCOR-03: Skills inferred
    scores.skillsInferred = calculateSkillsInferred(candidateSkills, {
      requiredSkills: searchContext.requiredSkills || [],
      preferredSkills: searchContext.preferredSkills || []
    });

    // SCOR-04: Seniority alignment
    scores.seniorityAlignment = calculateSeniorityAlignment(
      candidateLevel,
      companyTier,
      {
        targetLevel: searchContext.targetLevel || 'mid',
        roleType: searchContext.roleType || 'default'
      }
    );

    // SCOR-05: Recency boost
    scores.recencyBoost = calculateRecencyBoost(
      candidateExperience,
      searchContext.requiredSkills || []
    );

    // SCOR-06: Company relevance
    scores.companyRelevance = calculateCompanyRelevance(
      candidateCompanies,
      candidateIndustries,
      companyTier,
      {
        targetCompanies: searchContext.targetCompanies,
        targetIndustries: searchContext.targetIndustries
      }
    );
  }

  return scores;
}
```

### Anti-Patterns to Avoid

- **Hardcoding skill lists:** Use `skills-service.ts` for normalization, not inline skill arrays
- **Ignoring missing data:** Always return 0.5 (neutral) when data is unavailable, never 0 or 1
- **Blocking on missing signals:** Signals are optional; scoring should work with any subset
- **Coupling to database schema:** Extract data via helper functions, not direct field access
- **Expensive recomputation:** Use cached skill expansion (`getCachedSkillExpansion`)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Skill normalization | Custom alias matching | `skillsMatch()` from skills-service | Already handles 468 skills with aliases |
| Skill expansion | New graph traversal | `getCachedSkillExpansion()` | Already has BFS + LRU cache |
| Company tier detection | New company database | Existing `getCompanyTier()` in legacy-engine | Already has TOP_COMPANIES list |
| Level hierarchy | Custom level mapping | Existing `levelOrder` arrays | Already defined in legacy-engine |

## Common Pitfalls

### Pitfall 1: Division by Zero in Coverage Calculations
**What goes wrong:** `matchCount / requiredSkills.length` throws when `requiredSkills` is empty
**Why it happens:** Search request doesn't include skills filter
**How to avoid:**
- Guard clause: `if (!requiredSkills?.length) return 0.5`
- Return neutral (0.5) for missing context
**Warning signs:** NaN in signal scores

### Pitfall 2: Date Parsing Errors for Recency
**What goes wrong:** `new Date(endDate)` returns Invalid Date
**Why it happens:** PostgreSQL dates may be strings in various formats
**How to avoid:**
- Use date-fns `parseISO()` or check `isNaN(date.getTime())`
- Default to current date for `isCurrent` positions
- Return 0.5 for unparseable dates
**Warning signs:** Recency scores are always 0 or 0.5

### Pitfall 3: Case Sensitivity in String Matching
**What goes wrong:** "React" doesn't match "react" or "REACT"
**Why it happens:** Direct string comparison without normalization
**How to avoid:**
- Always use `skillsMatch()` for skill comparison (handles normalization)
- Use `.toLowerCase()` for company/industry matching
**Warning signs:** Low match rates despite obvious overlaps

### Pitfall 4: Stale Cached Skill Expansions
**What goes wrong:** New skill relationships not reflected in searches
**Why it happens:** LRU cache has 1-hour TTL
**How to avoid:**
- Accept TTL as acceptable tradeoff for performance
- Cache is automatically invalidated on service restart
- For testing, use `clearSkillExpansionCache()`
**Warning signs:** Skill graph updates not reflected in searches

### Pitfall 5: Weight Sum Drift After Adding Signals
**What goes wrong:** Weights sum to 1.15 after adding new signals, inflating scores
**Why it happens:** Added new signal weights without adjusting existing
**How to avoid:**
- Use `normalizeWeights()` which auto-adjusts if sum != 1.0
- Test that presets sum to 1.0 (+/- 0.001)
**Warning signs:** Warning log "Normalizing weights"

## Code Examples

### Example 1: Helper Functions for Data Extraction

```typescript
// services/hh-search-svc/src/signal-calculators.ts

import { normalizeSkillName } from '@/shared/skills-service';

/**
 * Extract candidate skills from various metadata sources
 */
function extractCandidateSkills(row: PgHybridSearchRow): string[] {
  const skills: string[] = [];

  // From skills array
  if (row.skills) {
    skills.push(...row.skills);
  }

  // From intelligent_analysis
  const metadata = row.metadata as Record<string, unknown> | null;
  if (metadata?.intelligent_analysis) {
    const analysis = metadata.intelligent_analysis as Record<string, unknown>;

    // Explicit skills
    if (analysis.explicit_skills) {
      const explicit = analysis.explicit_skills as Record<string, unknown>;
      if (Array.isArray(explicit.technical_skills)) {
        explicit.technical_skills.forEach((s: any) => {
          skills.push(typeof s === 'string' ? s : s.skill);
        });
      }
    }

    // Inferred skills
    if (analysis.inferred_skills) {
      const inferred = analysis.inferred_skills as Record<string, unknown>;
      ['highly_probable_skills', 'probable_skills', 'likely_skills'].forEach(key => {
        if (Array.isArray(inferred[key])) {
          (inferred[key] as any[]).forEach(s => skills.push(s.skill));
        }
      });
    }
  }

  // Normalize all skills
  return [...new Set(skills.map(s => normalizeSkillName(s)))];
}

/**
 * Extract candidate level from metadata
 */
function extractCandidateLevel(row: PgHybridSearchRow): string | null {
  const metadata = row.metadata as Record<string, unknown> | null;

  // Try intelligent_analysis first
  if (metadata?.intelligent_analysis) {
    const analysis = metadata.intelligent_analysis as Record<string, unknown>;
    if (analysis.career_trajectory_analysis) {
      const trajectory = analysis.career_trajectory_analysis as Record<string, unknown>;
      if (trajectory.current_level) return trajectory.current_level as string;
    }
  }

  // Fallback to direct metadata
  if (metadata?.current_level) return metadata.current_level as string;

  return null;
}

/**
 * Extract company tier (0=startup, 1=mid, 2=FAANG)
 */
function extractCompanyTier(row: PgHybridSearchRow): number {
  const metadata = row.metadata as Record<string, unknown> | null;

  if (metadata?.company_pedigree) {
    const pedigree = metadata.company_pedigree as Record<string, unknown>;
    if (pedigree.company_tier === 'faang') return 2;
    if (pedigree.company_tier === 'unicorn') return 1;
  }

  // Check companies against TOP_COMPANIES
  const companies = extractCandidateCompanies(row);
  for (const company of companies) {
    const lower = company.toLowerCase();
    if (['google', 'meta', 'facebook', 'amazon', 'microsoft', 'apple', 'netflix'].includes(lower)) {
      return 2;
    }
    if (['nubank', 'ifood', 'mercado libre', 'stripe', 'uber'].some(tc => lower.includes(tc))) {
      return 1;
    }
  }

  return 0;
}

/**
 * Extract experience records for recency calculation
 */
function extractCandidateExperience(row: PgHybridSearchRow): Array<{
  title: string;
  skills: string[];
  startDate?: string;
  endDate?: string | null;
  isCurrent: boolean;
}> {
  const metadata = row.metadata as Record<string, unknown> | null;
  const experience: Array<any> = [];

  if (metadata?.intelligent_analysis) {
    const analysis = metadata.intelligent_analysis as Record<string, unknown>;
    if (Array.isArray(analysis.experience)) {
      (analysis.experience as any[]).forEach(exp => {
        experience.push({
          title: exp.title || '',
          skills: exp.skills || [],
          startDate: exp.start_date,
          endDate: exp.end_date,
          isCurrent: exp.is_current || false
        });
      });
    }
  }

  return experience;
}
```

### Example 2: Integration in Search Service

```typescript
// services/hh-search-svc/src/search-service.ts (modify hydrateResult)

private hydrateResult(
  row: PgHybridSearchRow,
  request: HybridSearchRequest,
  resolvedWeights: SignalWeightConfig,
  roleType: RoleType
): HybridSearchResultItem {
  // ... existing code ...

  // Build search context for Phase 7 signals
  const searchContext = {
    requiredSkills: request.filters?.skills || [],
    preferredSkills: [],
    targetLevel: this.detectTargetLevel(request),
    targetCompanies: this.extractTargetCompanies(request),
    targetIndustries: request.filters?.industries,
    roleType
  };

  // Extract signal scores INCLUDING Phase 7 signals
  const signalScores = extractSignalScores(row, searchContext);

  // Compute weighted score with all signals
  const weightedScore = computeWeightedScore(signalScores, resolvedWeights);

  // ... rest of existing code ...
}
```

### Example 3: Unit Tests for Signal Calculators

```typescript
// services/hh-search-svc/src/__tests__/signal-calculators.test.ts

import {
  calculateSkillsExactMatch,
  calculateSkillsInferred,
  calculateSeniorityAlignment,
  calculateRecencyBoost,
  calculateCompanyRelevance
} from '../signal-calculators';

describe('calculateSkillsExactMatch', () => {
  it('returns 1.0 when all required skills match', () => {
    const result = calculateSkillsExactMatch(
      ['JavaScript', 'TypeScript', 'React'],
      { requiredSkills: ['JavaScript', 'React'], preferredSkills: [] }
    );
    expect(result).toBe(1.0);
  });

  it('returns 0.5 for partial match', () => {
    const result = calculateSkillsExactMatch(
      ['JavaScript', 'Python'],
      { requiredSkills: ['JavaScript', 'React'], preferredSkills: [] }
    );
    expect(result).toBe(0.5);
  });

  it('returns 0.5 when no required skills specified', () => {
    const result = calculateSkillsExactMatch(
      ['JavaScript'],
      { requiredSkills: [], preferredSkills: [] }
    );
    expect(result).toBe(0.5);
  });

  it('handles alias matching (JS = JavaScript)', () => {
    const result = calculateSkillsExactMatch(
      ['JS', 'TS'],
      { requiredSkills: ['JavaScript', 'TypeScript'], preferredSkills: [] }
    );
    expect(result).toBe(1.0);
  });
});

describe('calculateSeniorityAlignment', () => {
  it('returns 1.0 for exact level match', () => {
    const result = calculateSeniorityAlignment('senior', 1, {
      targetLevel: 'senior',
      roleType: 'ic'
    });
    expect(result).toBe(1.0);
  });

  it('boosts FAANG candidate level', () => {
    // FAANG mid = effective senior
    const result = calculateSeniorityAlignment('mid', 2, {
      targetLevel: 'senior',
      roleType: 'ic'
    });
    expect(result).toBe(1.0); // mid + tier 2 = senior level
  });

  it('returns 0.5 for unknown level', () => {
    const result = calculateSeniorityAlignment(null, 0, {
      targetLevel: 'senior',
      roleType: 'ic'
    });
    expect(result).toBe(0.5);
  });
});

describe('calculateRecencyBoost', () => {
  it('returns 1.0 for current position using skill', () => {
    const result = calculateRecencyBoost(
      [{ title: 'Engineer', skills: ['Python'], isCurrent: true }],
      ['Python']
    );
    expect(result).toBe(1.0);
  });

  it('decays score for older experience', () => {
    const twoYearsAgo = new Date();
    twoYearsAgo.setFullYear(twoYearsAgo.getFullYear() - 2);

    const result = calculateRecencyBoost(
      [{
        title: 'Engineer',
        skills: ['Python'],
        endDate: twoYearsAgo.toISOString(),
        isCurrent: false
      }],
      ['Python']
    );
    expect(result).toBeGreaterThan(0.5);
    expect(result).toBeLessThan(1.0);
  });
});
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Binary skill match | Alias-aware + graph expansion | Phase 6 | 40% better recall for skill searches |
| Hardcoded level comparison | Company-tier adjusted seniority | Phase 7 | More accurate executive vs IC matching |
| No recency consideration | Experience date decay | Phase 7 | Favor candidates with recent relevant work |
| Single company score | Multi-signal (tier + target + industry) | Phase 7 | Better company fit assessment |

## Open Questions

### 1. Skill Weight Distribution: Exact vs Inferred
**What we know:** Both signals measure skill fit, but exact is more reliable
**What's unclear:** Optimal weight ratio between skillsExactMatch and skillsInferred
**Recommendation:** Start with 2:1 ratio (exact twice the weight of inferred), tune based on user feedback

### 2. Recency Decay Curve
**What we know:** More recent experience is more valuable
**What's unclear:** Optimal decay function (linear, exponential, step)
**Recommendation:** Start with linear decay (1.0 - 0.16*years), evaluate if exponential needed

### 3. Industry Matching Granularity
**What we know:** "Fintech" should match "Financial Services"
**What's unclear:** Need for industry taxonomy or simple substring match
**Recommendation:** Use substring match for MVP, consider industry taxonomy if precision issues arise

## Sources

### Primary (HIGH confidence)
- `services/hh-search-svc/src/signal-weights.ts` - Existing weight config pattern
- `services/hh-search-svc/src/scoring.ts` - Existing score computation
- `services/hh-search-svc/src/types.ts` - SignalScores interface
- `functions/src/shared/skills-service.ts` - Skill normalization (468 skills)
- `functions/src/shared/skills-graph.ts` - BFS expansion with caching
- `functions/src/engines/legacy-engine.ts` - Phase 2 signals, company scoring

### Secondary (MEDIUM confidence)
- `scripts/migrations/002_sourcing_schema.sql` - PostgreSQL schema for experience/skills
- `.planning/phases/04-multi-signal-scoring-framework/04-RESEARCH.md` - Phase 4 framework
- `.planning/phases/06-skills-intelligence/06-RESEARCH.md` - Skills expansion patterns

## Metadata

**Confidence breakdown:**
- Signal formulas: HIGH - Derived from existing legacy-engine patterns
- Integration points: HIGH - Clear extension of existing types/functions
- Weight distribution: MEDIUM - Initial values need tuning
- Edge case handling: HIGH - Neutral defaults for all missing data

**Research date:** 2026-01-24
**Valid until:** 2026-02-24 (30 days - formulas stable, weights may need tuning)

---

## Implementation Notes for Planner

### Dependency Chain

1. **signal-calculators.ts (NEW)** - Pure functions for 5 signals
   - No dependencies on other new files
   - Uses: skills-service.ts, skills-graph.ts

2. **types.ts (EXTEND)** - Add 5 new SignalScores fields
   - Depends on: nothing
   - All new fields are optional for backward compatibility

3. **signal-weights.ts (EXTEND)** - Add 5 new weights + update presets
   - Depends on: types.ts extension
   - Presets must sum to 1.0

4. **scoring.ts (MODIFY)** - Integrate new signals into extractSignalScores()
   - Depends on: signal-calculators.ts, types.ts extension

5. **search-service.ts (MODIFY)** - Pass search context to extractSignalScores()
   - Depends on: scoring.ts modification

### Testing Strategy

1. **Unit tests for each calculator function** (5 test files)
2. **Integration test for full signal extraction**
3. **Regression test for existing signal behavior**
4. **Weight normalization test for all presets**

### Estimated Effort

- signal-calculators.ts: 3-4 hours
- Type extensions: 1 hour
- Weight preset tuning: 1 hour
- Scoring integration: 2 hours
- Search service integration: 1 hour
- Testing: 3-4 hours
- **Total: 11-14 hours**

### Risk Mitigation

- **Feature flag:** `ENABLE_PHASE7_SIGNALS=true/false` to toggle new signals
- **Logging:** Log all 5 new signal scores for debugging
- **Monitoring:** Track distribution of new signal values in production
- **Rollback:** Weights default to 0 for new signals if flag disabled
