# Phase 8: Career Trajectory - Research

**Researched:** 2026-01-24
**Domain:** Career Progression Analysis / Trajectory Classification / Rule-Based Scoring
**Confidence:** HIGH

## Summary

Phase 8 implements career trajectory analysis as a scoring signal that considers career direction (upward/lateral/downward), velocity (fast/normal/slow), trajectory type (technical/leadership/lateral/pivot), and trajectory fit score for role alignment. The system **already has partial trajectory data** in enriched profiles (`career_trajectory_analysis.promotion_velocity` and `.career_progression` fields from Together AI), but this data is not currently parsed or used in scoring.

**Key Decision (from context):** Rule-based trajectory analysis is sufficient per research; ML-based approaches are deferred to v2. This aligns with the pragmatic approach used in Phase 7 signal scoring.

The primary implementation path is:
1. **Extract trajectory fields** from existing enriched profiles (Together AI already generates `promotion_velocity` and `career_progression`)
2. **Add rule-based classifiers** to compute trajectory_direction and trajectory_type from title sequences
3. **Implement trajectory fit scoring** that aligns candidate trajectory with role requirements
4. **Integrate into Phase 7 scoring framework** as a new weighted signal (already has `trajectoryFit` weight placeholder at 0.06-0.10)

## Industry Research Findings

### Career Trajectory Classification Algorithms

Recent research in career path prediction (CPP) has evaluated multiple algorithmic approaches:

#### Machine Learning Approaches
- **LSTM-based architectures** are widely adopted for sequence modeling of job titles ([Frontiers | Toward more realistic career path prediction](https://www.frontiersin.org/journals/big-data/articles/10.3389/fdata.2025.1564521/full))
- Models trained on 20 million companies detect role progression, skill development, and leadership transitions ([Career Mapping in 2026](https://www.talentguard.com/what-is-career-mapping))
- Large Language Model-based occupation classification (FewSOC) achieves higher accuracy than traditional methods ([Leveraging Large Language Models for Career Mobility Analysis](https://arxiv.org/html/2511.12010v1))

**Implication for Phase 8:** ML approaches are powerful but require training data and model maintenance. For MVP, rule-based classification is sufficient and explainable.

#### Rule-Based Classification
- **Job title parsing** with pattern matching (e.g., "Senior", "Lead", "Manager", "Director", "VP", "C-Level") provides reliable level detection
- **Title sequence analysis** comparing adjacent roles reveals promotion patterns
- **Dual career path frameworks** distinguish technical track (Staff, Principal, Fellow, Architect) from management track (Manager, Director, VP, CTO) ([Engineering Management vs. Technical Track](https://onlinedegrees.sandiego.edu/engineering-management-vs-technical-track/))

**Implication for Phase 8:** Title sequence analysis with level ordering + track detection is implementable without ML and provides transparent, debuggable scoring.

### Career Velocity Metrics

#### Career Path Ratio (CPR)
Standard HR metric measuring promotions vs lateral moves ([Career Path Ratio: Meaning & How To Calculate](https://www.aihr.com/hr-glossary/career-path-ratio/)):
- **Fast progression:** CPR > 0.6 (promotion every <2 years)
- **Normal progression:** CPR 0.2-0.6 (promotion every 2-4 years)
- **Slow progression:** CPR < 0.2 (promotion every >4 years or mostly lateral)

**Implication for Phase 8:** Time-between-promotions is a computable metric from title sequences with date ranges.

#### Progression Patterns
- **Vertical trajectory:** Upward slope with higher-level positions and pay ([What is career trajectory?](https://www.indeed.com/career-advice/career-development/what-is-career-trajectory))
- **Lateral trajectory:** Same-level moves across companies or functions
- **Downward trajectory:** Lower-level titles (can indicate skill pivots or career resets)

**Implication for Phase 8:** Level distance calculation (e.g., Mid → Senior = +1, Senior → Mid = -1) provides direction signal.

### Trajectory Type Detection

#### Technical vs Management Track
Title patterns reveal career track choices ([Technical Track versus Managerial Track](https://www.linkedin.com/pulse/technical-track-versus-managerial-realities-both-paul)):

**Technical Track Indicators:**
- "Staff Engineer", "Principal Engineer", "Distinguished Engineer"
- "Architect", "Fellow", "Chief Scientist"
- "Technical Lead" (individual contributor variant)

**Management Track Indicators:**
- "Engineering Manager", "Senior Manager", "Director"
- "VP of Engineering", "CTO", "Head of..."
- "Manager of Managers", "General Manager"

**Career Pivot Indicators:**
- Role function change (e.g., Engineer → Product Manager)
- Industry change with level reset
- Track switch (IC → Manager or Manager → IC)

**Implication for Phase 8:** String pattern matching on titles + level analysis detects track and identifies pivots.

## Existing Codebase Infrastructure

### Together AI Enrichment (Already Generates Trajectory Data)

**Schema:** `scripts/prompt_builder.py` (lines 76-77)
```python
"career_trajectory_analysis": {
  "current_level": "...",
  "years_experience": 0,
  "promotion_velocity": "...",
  "career_progression": "...",
  "performance_indicator": "..."
}
```

**Fields available in enriched profiles:**
- `current_level`: Already standardized to Junior/Mid/Senior/Staff/Principal/Executive
- `promotion_velocity`: Likely "Fast/Average/Slow" (string from Together AI)
- `career_progression`: Narrative description (e.g., "steady upward trajectory")
- `performance_indicator`: Quality signal (not directly used in trajectory scoring)

**Gap:** These fields exist but are not parsed or used in the scoring framework.

### Phase 7 Signal Scoring Infrastructure (Ready for Extension)

**Signal Weight Configuration:** `services/hh-search-svc/src/signal-weights.ts`
- `SignalWeightConfig` interface already has `trajectoryFit: number` field (line 33)
- `ROLE_WEIGHT_PRESETS` allocate 0.06-0.10 weight to trajectoryFit (lines 90, 108, 125, 143)
- Weight resolution and normalization already implemented

**Signal Calculators:** `services/hh-search-svc/src/signal-calculators.ts`
- Pure functions pattern established (5 existing calculators)
- Return 0-1 normalized scores
- Return 0.5 (neutral) when context data is missing
- No trajectory calculator exists yet

**Types:** `services/hh-search-svc/src/types.ts`
- `SignalScores` interface already has `trajectoryFit: number` field (line 68)
- Ready to accept computed trajectory scores

**Gap:** No trajectory calculator function exists; need to implement rule-based scoring logic.

### Level Ordering (Already Defined)

**Seniority Levels:** `services/hh-search-svc/src/signal-calculators.ts` (lines 51-62)
```typescript
const LEVEL_ORDER = [
  'intern', 'junior', 'mid', 'senior', 'staff',
  'principal', 'manager', 'director', 'vp', 'c-level'
];
```

**Gap:** This ordering mixes technical and management tracks. Need to define separate track orderings or use this as a baseline with track-specific adjustments.

## Recommended Architecture

### Rule-Based Trajectory Scoring Approach

Based on research and existing infrastructure, implement a **pure rule-based system** that:

1. **Parses trajectory data from enriched profiles**
   - Extract `career_trajectory_analysis` from profile JSON
   - Normalize `promotion_velocity` string to velocity enum
   - Parse `current_level` into level index

2. **Computes trajectory_direction from title sequence**
   - Use LEVEL_ORDER to map titles to numeric levels
   - Compare sequential positions: level[n] - level[n-1]
   - Aggregate into direction: upward (avg >0), lateral (avg ≈0), downward (avg <0)

3. **Computes trajectory_velocity from date ranges**
   - Calculate years between level changes
   - Map to velocity: fast (<2yr), normal (2-4yr), slow (>4yr)
   - Use Together AI `promotion_velocity` as fallback when date parsing fails

4. **Classifies trajectory_type from title patterns**
   - Technical: "Staff", "Principal", "Architect", "Fellow" in titles
   - Leadership: "Manager", "Director", "VP", "Head" in titles
   - Lateral: Same level, different function/company
   - Pivot: Function change or level reset

5. **Computes trajectory_fit score (0-1)**
   - Match candidate trajectory_type with role requirements
   - Reward upward trajectory for growth roles
   - Reward fast velocity for high-growth companies
   - Penalize downward trajectory unless role is pivot-friendly

### Data Model Extensions

**No new database fields needed.** Trajectory fields already exist in enriched profiles:
```typescript
interface EnrichedProfile {
  // ... existing fields
  career_trajectory_analysis?: {
    current_level: string;
    years_experience: number;
    promotion_velocity: string; // "Fast" | "Average" | "Slow"
    career_progression: string; // narrative
    performance_indicator?: string;
  };
}
```

**Computed at scoring time** (no persistence needed):
```typescript
interface TrajectoryMetrics {
  direction: 'upward' | 'lateral' | 'downward';
  velocity: 'fast' | 'normal' | 'slow';
  type: 'technical_growth' | 'leadership_track' | 'lateral_move' | 'career_pivot';
  fit_score: number; // 0-1 normalized
}
```

### Integration with Phase 7 Framework

**Add trajectory calculator:** `services/hh-search-svc/src/signal-calculators.ts`
```typescript
export interface TrajectoryContext {
  targetLevel: string;
  targetTrack: 'technical' | 'management' | 'any';
  roleGrowthType: 'high_growth' | 'stable' | 'pivot_friendly';
}

export function calculateTrajectoryFit(
  candidateProfile: EnrichedProfile,
  context: TrajectoryContext
): number {
  // Extract trajectory data from profile
  // Compute direction, velocity, type
  // Score fit based on role requirements
  // Return 0-1 normalized score
}
```

**Invoke in scoring pipeline:** `services/hh-search-svc/src/scoring.ts`
```typescript
// Compute trajectory signal
const trajectoryFit = calculateTrajectoryFit(
  candidate.profile,
  {
    targetLevel: request.filters?.seniorityLevels?.[0] || 'senior',
    targetTrack: inferTrackFromJD(request.jobDescription),
    roleGrowthType: inferGrowthTypeFromJD(request.jobDescription)
  }
);

// Add to signal scores
signalScores.trajectoryFit = trajectoryFit;
```

**Weight in final score:** Already configured in `ROLE_WEIGHT_PRESETS`
- Executive searches: trajectoryFit weight = 0.10 (moderate importance)
- Manager searches: trajectoryFit weight = 0.10 (moderate importance)
- IC searches: trajectoryFit weight = 0.06 (lower importance, skills matter more)

## Implementation Considerations

### Trajectory Direction Calculation

**Rule-based approach:**
1. Extract title sequence from experience array
2. Map each title to level index using LEVEL_ORDER
3. Calculate deltas: `[level[i] - level[i-1] for i in 1..n]`
4. Classify:
   - **Upward:** Mean delta > 0.5 (mostly promotions)
   - **Lateral:** Mean delta ∈ [-0.5, 0.5] (mostly same-level moves)
   - **Downward:** Mean delta < -0.5 (mostly demotions/resets)

**Edge cases:**
- Missing dates → use Together AI `career_progression` narrative
- Title not in LEVEL_ORDER → use NLP similarity to closest known title
- Gaps in employment → ignore gap periods, only compare consecutive roles

### Trajectory Velocity Calculation

**Rule-based approach:**
1. Extract date ranges from experience array
2. Identify level changes (where level[i] != level[i-1])
3. Calculate years between changes: `(endDate[i] - startDate[i-1]) / 365.25`
4. Classify:
   - **Fast:** Mean time-to-promotion < 2 years
   - **Normal:** Mean time-to-promotion 2-4 years
   - **Slow:** Mean time-to-promotion > 4 years

**Fallback:** If date parsing fails or experience lacks dates, use Together AI `promotion_velocity` field directly.

### Trajectory Type Classification

**Rule-based pattern matching:**

**Technical Growth:**
- Title contains: "Staff", "Principal", "Distinguished", "Architect", "Fellow", "Chief Scientist"
- No management keywords
- Level increases without function change

**Leadership Track:**
- Title contains: "Manager", "Director", "VP", "Head of", "Chief", "CTO", "CEO"
- Progression through management hierarchy

**Lateral Move:**
- Same level, different company or function
- Frequency of lateral moves > promotions
- Breadth-building career pattern

**Career Pivot:**
- Function change (e.g., Engineering → Product)
- Industry change with level reset
- Track switch (IC → Manager or Manager → IC)

### Trajectory Fit Scoring Logic

**Scoring matrix (0-1 normalized):**

| Candidate Trajectory | Role Type | Fit Score |
|---------------------|-----------|-----------|
| Upward + Fast | High-growth startup | 1.0 |
| Upward + Normal | Standard growth role | 0.9 |
| Upward + Slow | Stable enterprise | 0.7 |
| Lateral + Fast | Cross-functional role | 0.8 |
| Lateral + Normal | Breadth-building role | 0.7 |
| Downward + Any | Career reset / pivot | 0.4 (unless pivot-friendly) |
| Leadership Track | Manager/Director role | 1.0 |
| Technical Growth | IC/Staff+ role | 1.0 |
| Career Pivot | Any (context-dependent) | 0.6 |

**Adjustments:**
- **Track mismatch penalty:** -0.2 if technical candidate for manager role (or vice versa)
- **Velocity mismatch penalty:** -0.1 if fast-paced candidate for slow-growth role
- **Direction bonus:** +0.1 for upward trajectory in any context

**Neutral score:** 0.5 when trajectory data is unavailable or ambiguous

## Testing Strategy

### Unit Tests (TDD Required)

**Test trajectory direction classifier:**
```typescript
describe('calculateTrajectoryDirection', () => {
  it('detects upward trajectory from Junior → Senior → Staff', () => {
    const sequence = ['Junior Engineer', 'Senior Engineer', 'Staff Engineer'];
    expect(calculateTrajectoryDirection(sequence)).toBe('upward');
  });

  it('detects lateral trajectory from same-level moves', () => {
    const sequence = ['Senior Engineer', 'Senior Data Scientist', 'Senior PM'];
    expect(calculateTrajectoryDirection(sequence)).toBe('lateral');
  });

  it('detects downward trajectory from role reset', () => {
    const sequence = ['Director', 'Senior Engineer'];
    expect(calculateTrajectoryDirection(sequence)).toBe('downward');
  });
});
```

**Test trajectory velocity classifier:**
```typescript
describe('calculateTrajectoryVelocity', () => {
  it('detects fast velocity (<2yr promotions)', () => {
    const experience = [
      { title: 'Junior', startDate: '2020-01', endDate: '2021-06' },
      { title: 'Senior', startDate: '2021-07', endDate: '2023-01' }
    ];
    expect(calculateTrajectoryVelocity(experience)).toBe('fast');
  });

  it('falls back to Together AI field when dates missing', () => {
    const profile = { career_trajectory_analysis: { promotion_velocity: 'Slow' } };
    expect(extractVelocity(profile)).toBe('slow');
  });
});
```

**Test trajectory type classifier:**
```typescript
describe('classifyTrajectoryType', () => {
  it('detects technical growth track', () => {
    const sequence = ['Senior Engineer', 'Staff Engineer', 'Principal Engineer'];
    expect(classifyTrajectoryType(sequence)).toBe('technical_growth');
  });

  it('detects leadership track', () => {
    const sequence = ['Senior Engineer', 'Engineering Manager', 'Director'];
    expect(classifyTrajectoryType(sequence)).toBe('leadership_track');
  });

  it('detects career pivot', () => {
    const sequence = ['Senior Engineer', 'Product Manager'];
    expect(classifyTrajectoryType(sequence)).toBe('career_pivot');
  });
});
```

**Test trajectory fit scorer:**
```typescript
describe('calculateTrajectoryFit', () => {
  it('scores 1.0 for upward+fast candidate in high-growth role', () => {
    const candidate = { direction: 'upward', velocity: 'fast', type: 'technical_growth' };
    const context = { targetTrack: 'technical', roleGrowthType: 'high_growth' };
    expect(calculateTrajectoryFit(candidate, context)).toBe(1.0);
  });

  it('penalizes track mismatch', () => {
    const candidate = { type: 'technical_growth' };
    const context = { targetTrack: 'management' };
    expect(calculateTrajectoryFit(candidate, context)).toBeLessThan(0.8);
  });

  it('returns 0.5 when trajectory data missing', () => {
    const candidate = {};
    const context = { targetTrack: 'any' };
    expect(calculateTrajectoryFit(candidate, context)).toBe(0.5);
  });
});
```

### Integration Tests

**Test end-to-end scoring:**
```typescript
describe('Phase 8 Integration', () => {
  it('includes trajectoryFit in signal scores', async () => {
    const request = {
      jobDescription: 'Senior Engineering Manager',
      roleType: 'manager'
    };
    const result = await hybridSearch(request);

    expect(result.results[0].signalScores).toHaveProperty('trajectoryFit');
    expect(result.results[0].signalScores.trajectoryFit).toBeGreaterThan(0);
  });

  it('ranks leadership track higher for manager search', async () => {
    const request = {
      jobDescription: 'Engineering Manager',
      roleType: 'manager'
    };
    const results = await hybridSearch(request);

    const topCandidate = results.results[0];
    expect(topCandidate.profile.career_trajectory_analysis.career_progression)
      .toContain('management');
  });
});
```

## Success Criteria Validation

### TRAJ-01: Career direction computed from title sequence analysis
**Implementation:** `calculateTrajectoryDirection()` function parses title sequence, maps to level indices, computes deltas, classifies as upward/lateral/downward.
**Validation:** Unit tests verify classification across 10+ title sequence patterns.

### TRAJ-02: Career velocity computed (fast/normal/slow progression)
**Implementation:** `calculateTrajectoryVelocity()` function analyzes time-between-promotions from experience dates, falls back to Together AI field.
**Validation:** Unit tests verify velocity classification with date ranges and fallback logic.

### TRAJ-03: Trajectory fit score for role alignment
**Implementation:** `calculateTrajectoryFit()` function scores 0-1 based on direction/velocity/type alignment with role requirements.
**Validation:** Unit tests verify scoring matrix across 15+ candidate/role combinations.

### TRAJ-04: Trajectory type classification (technical, leadership, lateral, pivot)
**Implementation:** `classifyTrajectoryType()` function uses pattern matching on title keywords and level changes.
**Validation:** Unit tests verify classification across 8+ career path patterns.

### Success Criterion 1: Each candidate has computed trajectory_direction
**Evidence:** `calculateTrajectoryDirection()` returns 'upward'|'lateral'|'downward' for all candidates with experience data.
**Fallback:** Returns 'lateral' (neutral) when data insufficient.

### Success Criterion 2: Each candidate has computed trajectory_velocity
**Evidence:** `calculateTrajectoryVelocity()` returns 'fast'|'normal'|'slow' from date analysis or Together AI field.
**Fallback:** Returns 'normal' (neutral) when data insufficient.

### Success Criterion 3: Manager role search ranks candidates with leadership trajectory higher
**Evidence:** Integration test with "Engineering Manager" JD shows top-5 results have `type: 'leadership_track'` and `trajectoryFit > 0.8`.
**Metric:** Average trajectoryFit score for leadership-track candidates > 0.15 higher than technical-track candidates.

### Success Criterion 4: Trajectory type classification appears in candidate data
**Evidence:** All candidates with sufficient experience data have `type` field populated with one of: 'technical_growth', 'leadership_track', 'lateral_move', 'career_pivot'.
**Coverage:** >90% of candidates with 2+ roles have trajectory type classified.

### Success Criterion 5: Trajectory fit score (0-1) reflects alignment between candidate trajectory and role direction
**Evidence:** Scatter plot of trajectoryFit scores shows correlation with manual recruiter assessments (r > 0.7).
**Distribution:** Fit scores span full range [0.0, 1.0] with mean ≈ 0.6 and no clustering at 0.5 (neutral).

## Dependencies & Blockers

### Prerequisites
- ✅ Phase 7 signal scoring framework (complete)
- ✅ Together AI enrichment with `career_trajectory_analysis` fields (complete)
- ✅ LEVEL_ORDER definition in signal-calculators.ts (complete)
- ✅ Signal weight configuration in signal-weights.ts (complete)

### No New Dependencies Required
All implementation can use existing TypeScript standard library and Node.js utilities.

### Potential Blockers
1. **Inconsistent title formatting** in enriched profiles
   - **Mitigation:** NLP normalization + fuzzy matching to LEVEL_ORDER
   - **Fallback:** Use Together AI `current_level` when title parsing fails

2. **Missing date ranges** in experience arrays
   - **Mitigation:** Use Together AI `promotion_velocity` field as fallback
   - **Fallback:** Return neutral velocity score (0.5)

3. **Ambiguous trajectory patterns** (e.g., IC → Manager → IC)
   - **Mitigation:** Detect as 'career_pivot' type
   - **Scoring:** Apply pivot-specific fit logic

## Future Enhancements (v2.0)

### Machine Learning Trajectory Prediction
- Train LSTM model on historical candidate outcomes
- Predict next likely role based on trajectory pattern
- Learn optimal velocity benchmarks per industry/company tier

### Trajectory-Based Recommendations
- "Similar career paths" feature for recruiters
- Trajectory cluster analysis (e.g., "fast-track FAANG engineers")
- Personalized role suggestions based on trajectory type

### Advanced Trajectory Metrics
- Skill evolution velocity (rate of new skill acquisition)
- Stability pattern (average tenure per role)
- Promotion pattern (consistent vs erratic progression)

## References

### Research Sources
- [Frontiers | Toward more realistic career path prediction](https://www.frontiersin.org/journals/big-data/articles/10.3389/fdata.2025.1564521/full) - Career path prediction algorithms and evaluation
- [Career Path Ratio: Meaning & How To Calculate](https://www.aihr.com/hr-glossary/career-path-ratio/) - Standard HR velocity metrics
- [What is career trajectory?](https://www.indeed.com/career-advice/career-development/what-is-career-trajectory) - Direction classification framework
- [Engineering Management vs. Technical Track](https://onlinedegrees.sandiego.edu/engineering-management-vs-technical-track/) - Dual career path frameworks
- [Technical Track versus Managerial Track](https://www.linkedin.com/pulse/technical-track-versus-managerial-realities-both-paul) - Track detection patterns
- [Career Mapping in 2026](https://www.talentguard.com/what-is-career-mapping) - Industry trends and AI-enabled analysis
- [Leveraging Large Language Models for Career Mobility Analysis](https://arxiv.org/html/2511.12010v1) - LLM-based occupation classification
- [CMap: a database for mapping job titles](https://www.nature.com/articles/s41597-025-05526-3) - Job title standardization and promotion pathways

### Codebase References
- `services/hh-search-svc/src/signal-weights.ts` - Signal weight configuration
- `services/hh-search-svc/src/signal-calculators.ts` - Signal scoring functions
- `services/hh-search-svc/src/types.ts` - Type definitions
- `scripts/prompt_builder.py` - Together AI prompt with career_trajectory_analysis schema
- `functions/src/analysis-service.ts` - Legacy enrichment service with trajectory fields

## Summary: What You Need to Know to PLAN This Phase Well

### Core Implementation Pattern
**This is a pure TypeScript scoring extension** following the exact pattern from Phase 7:
1. Add trajectory calculator function to `signal-calculators.ts`
2. Parse existing `career_trajectory_analysis` fields from enriched profiles
3. Apply rule-based classification logic (direction, velocity, type)
4. Return 0-1 normalized fit score
5. Signal weights already configured in `ROLE_WEIGHT_PRESETS`

### Key Technical Decisions
- **Rule-based, not ML:** Explainable, sufficient for MVP, deferring ML to v2
- **Reuse existing data:** Together AI already generates trajectory fields
- **No database changes:** All computation at scoring time
- **Pure functions:** Testable, cacheable, deterministic

### Critical Success Factors
1. **Accurate level mapping:** Title → LEVEL_ORDER index must be robust
2. **Graceful degradation:** Missing data → neutral score (0.5), not error
3. **Track detection:** Technical vs leadership patterns must be reliable
4. **Fit scoring logic:** Matrix must align with recruiter intuition

### Primary Risk
**Inconsistent title formatting** in enriched profiles could break level mapping.
**Mitigation:** Build robust normalization + fuzzy matching + fallback to Together AI `current_level` field.

### Estimated Complexity
**Medium (similar to Phase 7 individual signals)**
- Trajectory direction: ~100 LOC
- Trajectory velocity: ~80 LOC
- Trajectory type: ~120 LOC
- Trajectory fit scorer: ~150 LOC
- Tests: ~300 LOC
- Total: ~750 LOC (3-4 day effort)

**Confidence:** HIGH - Pattern is established, data exists, integration points are clear.
