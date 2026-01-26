---
phase: 14
plan: 01
subsystem: search
tags: [bias-reduction, anonymization, blind-hiring, privacy]
dependency-graph:
  requires: [phase-12, phase-13]
  provides: [BIAS-01, anonymization-middleware]
  affects: [phase-14-plans-02-05]
tech-stack:
  added: []
  patterns: [type-guard, data-transformation, middleware]
key-files:
  created:
    - services/hh-search-svc/src/bias/types.ts
    - services/hh-search-svc/src/bias/anonymization.ts
    - services/hh-search-svc/src/bias/anonymization.test.ts
    - services/hh-search-svc/src/bias/index.ts
  modified:
    - services/hh-search-svc/src/types.ts
    - services/hh-search-svc/src/routes.ts
    - services/hh-search-svc/src/schemas.ts
decisions:
  - id: BIAS-01-types
    choice: Dedicated AnonymizedCandidate type
    rationale: Type safety for anonymized data, prevent accidental PII leakage
  - id: BIAS-01-proxy-exclusion
    choice: Exclude companyPedigree and companyRelevance from anonymized scores
    rationale: Company tier signals correlate with demographics per research
  - id: BIAS-01-reason-filtering
    choice: Filter match reasons by pattern matching
    rationale: Company/school/location mentions filtered, generic reasons preserved
metrics:
  duration: 5m 25s
  completed: 2026-01-26
---

# Phase 14 Plan 01: Resume Anonymization Toggle Summary

**One-liner:** Blind hiring anonymization middleware stripping PII while preserving candidateId, skills, and scores for bias-free evaluation.

## What Was Built

### 1. Anonymization Types (`src/bias/types.ts`)

Created type-safe interfaces for anonymization:

- **AnonymizationConfig**: Configurable field lists for PII, proxy, and preserved fields
- **AnonymizedCandidate**: Strongly-typed anonymized result with only job-relevant data
- **AnonymizedSearchResponse**: Full response type for anonymized search results
- **DEFAULT_ANONYMIZATION_CONFIG**: Production defaults based on proxy variable audit

```typescript
// PII fields stripped: fullName, title, headline, location, country, metadata
// Proxy fields excluded: companyPedigree, companyRelevance, graduationYear
// Preserved: candidateId, skills, yearsExperience, industries, signalScores, mlTrajectory
```

### 2. Anonymization Functions (`src/bias/anonymization.ts`)

Core transformation logic:

- **anonymizeCandidate()**: Transforms single candidate, strips PII, filters match reasons
- **anonymizeSearchResponse()**: Applies to full response, adds anonymization metadata
- **anonymizeMatchReasons()**: Pattern-based filtering of reasons mentioning companies/schools/locations
- **isAnonymizedResponse()**: Type guard for checking response anonymization status

Key features:
- Signal scores preserved except company-related ones (proxy risk)
- Match reasons filtered for company/school/location mentions
- Years in match reasons replaced with `[year]` placeholder
- ML trajectory predictions preserved (predictive, not identifying)

### 3. Comprehensive Test Suite (`src/bias/anonymization.test.ts`)

514 lines, 30 test cases covering:

- PII stripping (name, title, location, headline, metadata)
- Proxy exclusion (companyPedigree, companyRelevance)
- Preservation (candidateId, scores, skills, industries, mlTrajectory)
- Match reason filtering (company, school, location patterns)
- Edge cases (empty arrays, minimal candidates, Phase 7 signals)
- Response-level anonymization with metadata marking

### 4. API Integration (`src/routes.ts`)

Wired anonymization to search endpoint:

- Added `anonymizedView` parameter to `HybridSearchRequest`
- Added schema validation in `hybridSearchSchema`
- Applied anonymization to both cached and fresh responses
- Header `X-Cache-Status` preserved for observability

Usage:
```typescript
POST /v1/search/hybrid
{
  "query": "senior engineer",
  "anonymizedView": true
}
```

## Commits

| Hash | Type | Description |
|------|------|-------------|
| b93dcc5 | feat | Create anonymization types and configuration |
| 344ba5b | test | Add comprehensive anonymization unit tests (30 tests) |
| ecd2b4d | feat | Wire anonymization to search API endpoint |

## Verification Results

| Check | Status |
|-------|--------|
| TypeScript compiles | PASS |
| Tests pass (30/30) | PASS |
| Barrel export exists | PASS |
| API integration pattern | PASS |
| HybridSearchRequest has anonymizedView | PASS |
| Schema validation includes anonymizedView | PASS |

## Key Technical Decisions

### 1. Separate AnonymizedCandidate Type

Instead of marking fields optional on HybridSearchResultItem, created a dedicated type. This provides:
- Compile-time enforcement that PII fields don't exist
- Clear documentation of what's preserved vs stripped
- Type guard for checking response state

### 2. Proxy Field Exclusion

Based on 14-RESEARCH.md proxy variable audit:
- `companyPedigree` and `companyRelevance` excluded from scores
- These signals correlate with demographics (company tier → socioeconomic background)
- Other signals (skills, trajectory, level) deemed job-relevant

### 3. Pattern-Based Match Reason Filtering

Using regex patterns rather than entity recognition:
- Fast execution (no ML inference needed)
- Catches common patterns: "at [Company]", "graduated from", "based in"
- Preserves generic reasons: "Strong skill match", "Senior level alignment"
- Year values replaced with `[year]` placeholder for remaining reasons

## Deviations from Plan

None - plan executed exactly as written.

## Next Phase Readiness

Plan 14-02 can proceed. This plan provides:
- Anonymization infrastructure for blind hiring workflows
- Type-safe anonymized response format
- API endpoint parameter for toggling anonymization

Dependencies for subsequent plans:
- Signal weight calibration (14-02) can use anonymized data
- Fairness metrics (14-03) can measure disparate impact on anonymized results
- Audit logging (14-04) can track anonymization usage
