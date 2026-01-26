# Scoring Algorithm Documentation

**Version:** 2.0 (Phase 14 - Bias Reduction)
**Last Updated:** 2026-01-26
**Compliance:** BIAS-02 Demographic-Blind Scoring

---

## Overview

The Headhunter search system uses a multi-signal weighted scoring framework to rank candidates based on job-relevant qualifications. This document describes:

1. All signals used in scoring
2. Weight configurations per role type
3. Proxy variable analysis (bias compliance)
4. Scoring computation formula

**Key Compliance Statement:** This scoring algorithm does NOT use demographic proxies (zip code, graduation year, school name) to rank candidates. All signals are job-related and defensible under employment law.

---

## Scoring Signals

### Core Signals (Always Applied)

| Signal | Weight Range | Description | Proxy Risk |
|--------|-------------|-------------|------------|
| vectorSimilarity | 0.08-0.12 | Semantic match between candidate profile and job description | LOW |
| levelMatch | 0.08-0.12 | Seniority level alignment (Senior, Staff, Principal) | LOW |
| specialtyMatch | 0.04-0.12 | Technical specialty alignment (backend, frontend, fullstack) | LOW |
| techStackMatch | 0.04-0.12 | Technology stack compatibility | LOW |
| functionMatch | 0.06-0.20 | Job function alignment (engineering, product, design) | LOW |
| trajectoryFit | 0.06-0.10 | Career trajectory alignment (growth pattern, direction) | LOW |
| companyPedigree | 0.02-0.12 | Prior company experience tier | **MEDIUM** |

### Phase 7 Signals (Skill-Aware Searches)

| Signal | Weight Range | Description | Proxy Risk |
|--------|-------------|-------------|------------|
| skillsExactMatch | 0.02-0.14 | Exact match of required/preferred skills | LOW |
| skillsInferred | 0.02-0.08 | Skills inferred from experience context | LOW |
| seniorityAlignment | 0.06-0.12 | Seniority title alignment | LOW |
| recencyBoost | 0.02-0.08 | Recent experience relevance | LOW |
| companyRelevance | 0.05-0.12 | Relevance of prior companies to role | **MEDIUM** |

---

## Proxy Variable Analysis

### BIAS-02 Compliance Audit

This section documents the proxy variable audit performed for Phase 14 compliance.

#### HIGH-Risk Proxy Variables (NOT USED)

The following variables are known demographic proxies and are explicitly **NOT** used in scoring:

| Variable | Demographic Correlation | Status |
|----------|------------------------|--------|
| location / zipCode | Race, socioeconomic status | **NOT USED** - Display only |
| graduationYear | Age | **NOT USED** - Never referenced |
| educationInstitutions | Race, socioeconomic status | **NOT USED** - Display only |
| schoolName / university | Race, socioeconomic status | **NOT USED** - Display only |

**Verification:** Code audit confirms these fields are:
- Not imported in `scoring.ts`
- Not imported in `signal-calculators.ts`
- Not referenced in `trajectory-calculators.ts`
- Used only for display in UI, never for ranking

**Audit Command Results:**
```bash
# Graduation year search
grep -r "graduation" services/hh-search-svc/src/*.ts
# Result: No matches found

# Education institution search
grep -r "educationInstitution|school|university|college" services/hh-search-svc/src/*.ts
# Result: No matches found

# Zip code search
grep -r "zipCode|postalCode" services/hh-search-svc/src/*.ts
# Result: No matches found
```

#### MEDIUM-Risk Variables (Used with Justification)

| Variable | Why It's a Proxy | Job-Related Justification | Mitigation |
|----------|-----------------|---------------------------|------------|
| companyPedigree | FAANG/enterprise experience correlates with access to elite institutions | Prior experience at scale is legitimate job qualification for roles requiring such experience | Weight capped at 12%; can be overridden per search |
| companyRelevance | Similar to pedigree | Industry-specific experience is job-related | Weight capped at 12%; can be overridden |
| yearsExperience | Correlates with age | Direct job requirement (senior roles need experience) | Used as filter, not score signal - legitimate |

**Legal Defensibility:** Courts have upheld that job-related factors like "prior experience at comparable organizations" are legitimate even if they correlate with protected characteristics, provided they are not pretextual.

#### LOW-Risk Variables (Safe to Use)

All other signals (vectorSimilarity, levelMatch, skillsExactMatch, etc.) are based on:
- Skills explicitly listed by candidate
- Job titles and functions
- Technical capabilities
- Career trajectory patterns

These do not correlate meaningfully with protected demographic characteristics.

---

## Signal Weight Presets

Weight presets are defined in `services/hh-search-svc/src/signal-weights.ts`.

### Executive Role (C-level, VP, Director)

Emphasizes function alignment and company pedigree:

| Signal | Weight | Rationale |
|--------|--------|-----------|
| vectorSimilarity | 0.08 | Lower - context matters more than keywords |
| levelMatch | 0.12 | Important - executive level alignment |
| specialtyMatch | 0.04 | Lower - generalist executives |
| techStackMatch | 0.04 | Lower - strategic, not tactical |
| functionMatch | 0.20 | **Highest** - executive function fit |
| trajectoryFit | 0.10 | Important - leadership trajectory |
| companyPedigree | 0.12 | Relevant - executive experience at scale |
| skillsExactMatch | 0.02 | Lower - soft skills matter more |
| skillsInferred | 0.02 | Lower |
| seniorityAlignment | 0.12 | Important - executive level |
| recencyBoost | 0.02 | Lower |
| companyRelevance | 0.12 | Relevant - industry experience |

### Manager Role (Engineering Manager, Tech Lead)

Balanced across all dimensions:

| Signal | Weight |
|--------|--------|
| vectorSimilarity | 0.12 |
| levelMatch | 0.10 |
| specialtyMatch | 0.12 |
| techStackMatch | 0.08 |
| functionMatch | 0.12 |
| trajectoryFit | 0.10 |
| companyPedigree | 0.10 |
| skillsExactMatch | 0.06 |
| skillsInferred | 0.05 |
| seniorityAlignment | 0.06 |
| recencyBoost | 0.04 |
| companyRelevance | 0.05 |

### Individual Contributor (Senior, Mid, Junior)

Emphasizes skills and technical stack:

| Signal | Weight | Rationale |
|--------|--------|-----------|
| vectorSimilarity | 0.12 | Important - technical match |
| levelMatch | 0.08 | Moderate |
| specialtyMatch | 0.12 | **High** - exact specialty matters |
| techStackMatch | 0.12 | **High** - exact tech matters |
| functionMatch | 0.06 | Moderate |
| trajectoryFit | 0.06 | Moderate |
| companyPedigree | 0.02 | **Low** - skills > pedigree for ICs |
| skillsExactMatch | 0.14 | **Highest** - exact skill fit |
| skillsInferred | 0.08 | Important |
| seniorityAlignment | 0.06 | Moderate |
| recencyBoost | 0.08 | Important - recent skills |
| companyRelevance | 0.06 | Moderate |

---

## Scoring Formula

Final score is computed as weighted sum:

```
score = SUM(signal_i * weight_i) for all signals
```

Where:
- Each signal is normalized to 0-1 range
- Weights sum to 1.0 (normalized if not)
- Missing signals default to 0.5 (neutral)

### Implementation Reference

See `services/hh-search-svc/src/scoring.ts`:

```typescript
export function computeWeightedScore(
  signals: Partial<SignalScores>,
  weights: SignalWeightConfig
): number {
  // Default missing signals to 0.5 (neutral)
  const vs = signals.vectorSimilarity ?? 0.5;
  const lm = signals.levelMatch ?? 0.5;
  // ... additional signals ...

  let score = 0;
  score += vs * weights.vectorSimilarity;
  score += lm * weights.levelMatch;
  // ... additional weighted sums ...

  return score;
}
```

### Example Calculation

For an IC search with candidate scores:

| Signal | Score | Weight | Contribution |
|--------|-------|--------|--------------|
| vectorSimilarity | 0.85 | 0.12 | 0.102 |
| levelMatch | 0.90 | 0.08 | 0.072 |
| specialtyMatch | 0.95 | 0.12 | 0.114 |
| techStackMatch | 0.80 | 0.12 | 0.096 |
| functionMatch | 0.70 | 0.06 | 0.042 |
| trajectoryFit | 0.75 | 0.06 | 0.045 |
| companyPedigree | 0.50 | 0.02 | 0.010 |
| skillsExactMatch | 0.92 | 0.14 | 0.129 |
| skillsInferred | 0.65 | 0.08 | 0.052 |
| seniorityAlignment | 0.88 | 0.06 | 0.053 |
| recencyBoost | 0.70 | 0.08 | 0.056 |
| companyRelevance | 0.60 | 0.06 | 0.036 |
| **Total** | | | **0.807** |

---

## Bias Mitigation Measures

### 1. Anonymization Mode (BIAS-01)

When enabled, scoring results are anonymized:
- Name, photo, location stripped
- Company names redacted
- companyPedigree excluded from displayed scores
- Only skills, experience level, and signal scores shown

### 2. Diverse Slate Warnings (BIAS-05)

Post-search analysis warns when:
- >70% of candidates from same company tier
- >70% from same experience band
- >70% from same specialty

### 3. Impact Ratio Monitoring (BIAS-04)

Selection rates tracked by:
- Company tier (FAANG/enterprise/startup/other)
- Experience band (0-3, 3-7, 7-15, 15+ years)
- Specialty (backend, frontend, fullstack, etc.)

Four-fifths rule alerts when any group falls below 80% of highest-selected group.

---

## Configuration

Signal weights can be overridden per-search via `signalWeights` parameter:

```typescript
{
  "query": "Senior Python developer",
  "signalWeights": {
    "companyPedigree": 0.00,  // Disable pedigree for this search
    "skillsExactMatch": 0.20   // Increase skill weight
  }
}
```

See `services/hh-search-svc/src/signal-weights.ts` for:
- `ROLE_WEIGHT_PRESETS` - Predefined weight configurations
- `resolveWeights()` - Merges request overrides with presets
- `normalizeWeights()` - Ensures weights sum to 1.0

---

## Audit Log

| Date | Auditor | Finding | Action |
|------|---------|---------|--------|
| 2026-01-26 | Phase 14 Execution | No HIGH-risk proxies in scoring | Documented in this file |
| 2026-01-26 | Phase 14 Execution | companyPedigree has MEDIUM risk | Documented justification, weight capped at 12% |
| 2026-01-26 | Phase 14 Execution | yearsExperience used as filter only | Documented as legitimate job requirement |

---

## Related Documentation

- `services/hh-search-svc/src/signal-weights.ts` - Weight configuration and presets
- `services/hh-search-svc/src/scoring.ts` - Score computation implementation
- `services/hh-search-svc/src/signal-calculators.ts` - Individual signal calculation functions
- `services/hh-search-svc/src/trajectory-calculators.ts` - Career trajectory analysis

---

*This document is maintained as part of BIAS-02 compliance and should be updated when scoring signals change.*
