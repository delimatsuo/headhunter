---
phase: 14-bias-reduction
plan: 02
subsystem: scoring-documentation
tags: [bias, compliance, documentation, proxy-audit, BIAS-02]

dependency_graph:
  requires:
    - "Phase 4: Multi-Signal Scoring Framework"
    - "Phase 7: Signal Scoring Implementation"
  provides:
    - "Scoring algorithm documentation with proxy variable audit"
    - "BIAS-02 demographic-blind scoring compliance documentation"
  affects:
    - "14-03: Fairness metrics (uses documented signals)"
    - "14-04: Impact ratio monitoring (uses documented groups)"
    - "15-XX: NYC LL144 compliance (references scoring documentation)"

tech_stack:
  added: []
  patterns:
    - "JSDoc proxy risk annotations"
    - "Compliance documentation"

key_files:
  created:
    - "docs/SCORING_ALGORITHM.md"
  modified:
    - "services/hh-search-svc/src/signal-weights.ts"

decisions:
  - key: "No HIGH-risk proxies in scoring"
    choice: "Verified absence of location, graduationYear, educationInstitutions"
    reason: "Demographic-blind scoring compliance"
  - key: "companyPedigree documented as MEDIUM risk"
    choice: "Keep in scoring with 12% weight cap"
    reason: "Prior experience at scale is legitimate job requirement"
  - key: "yearsExperience as filter only"
    choice: "Document as legitimate job requirement"
    reason: "Used for filtering, not ranking - correlates with job seniority"

metrics:
  duration: "~15 minutes"
  completed: "2026-01-26"
  tests_added: 0
  tests_passing: "N/A (documentation task)"
---

# Phase 14 Plan 02: SCORING_ALGORITHM.md Documentation Summary

**One-liner:** Created comprehensive scoring algorithm documentation with proxy variable audit for BIAS-02 compliance.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Audit scoring code for proxy variables | N/A (read-only) | - |
| 2 | Create SCORING_ALGORITHM.md documentation | 59c2df7 | docs/SCORING_ALGORITHM.md |
| 3 | Add JSDoc proxy risk comments to signal-weights.ts | da9bd9b | signal-weights.ts |

## What Was Built

### 1. Proxy Variable Audit (Task 1)

Conducted code audit of scoring files:
- `services/hh-search-svc/src/scoring.ts`
- `services/hh-search-svc/src/signal-calculators.ts`
- `services/hh-search-svc/src/trajectory-calculators.ts`

**Audit Results:**

| Risk Level | Variables | Status |
|------------|-----------|--------|
| HIGH | graduationYear | NOT USED (0 matches) |
| HIGH | educationInstitutions, school, university | NOT USED (0 matches) |
| HIGH | zipCode, postalCode | NOT USED (0 matches) |
| MEDIUM | companyPedigree, companyRelevance | Used with justification |
| MEDIUM | yearsExperience | Filter only (not scoring signal) |

### 2. SCORING_ALGORITHM.md Documentation (Task 2)

Created comprehensive 297-line documentation:

**Sections:**
- Overview with compliance statement
- All 12 scoring signals with proxy risk levels
- Proxy Variable Analysis (HIGH/MEDIUM/LOW risk audit)
- Signal Weight Presets (executive, manager, IC)
- Scoring formula with example calculation
- Bias mitigation measures
- Configuration reference

**Key Content:**
```markdown
## Proxy Variable Analysis

### HIGH-Risk Proxy Variables (NOT USED)
- location / zipCode
- graduationYear
- educationInstitutions / school / university

### MEDIUM-Risk Variables (Used with Justification)
- companyPedigree: Weight capped at 12%, job-related justification
- companyRelevance: Industry experience is legitimate
- yearsExperience: Filter only, not scoring signal
```

### 3. JSDoc Proxy Risk Comments (Task 3)

Updated `signal-weights.ts` with:

1. **Module-level BIAS-02 compliance block** listing all risk levels
2. **13 PROXY RISK annotations** on interface properties:
   - 10 signals marked as `PROXY RISK: LOW`
   - 2 signals marked as `PROXY RISK: **MEDIUM**` with detailed justification
   - Links to SCORING_ALGORITHM.md for full audit

**Example:**
```typescript
/**
 * Company pedigree score (0-1) - PROXY RISK: **MEDIUM**
 *
 * This signal correlates with demographic factors (access to elite
 * institutions/companies). However, prior experience at scale is a
 * legitimate job requirement for certain roles.
 *
 * Mitigation: Weight capped at 12%, excluded from anonymized view,
 * documented in SCORING_ALGORITHM.md as job-related justification.
 */
companyPedigree: number;
```

## Verification Results

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| SCORING_ALGORITHM.md exists | File exists | Exists | PASS |
| Documentation lines | 150+ | 297 | PASS |
| Proxy Variable Analysis section | Present | Present | PASS |
| PROXY RISK comments | Multiple | 13 | PASS |
| TypeScript compiles | No errors | Clean | PASS |

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

### 1. No HIGH-risk proxies confirmed
The audit verified that location, graduation year, and education institution fields are never referenced in scoring code. They exist only for display purposes.

### 2. companyPedigree retained with documentation
While companyPedigree correlates with access to elite institutions (a potential proxy for race/socioeconomic status), prior experience at scale is a legitimate job requirement. Documented justification and mitigation (12% weight cap).

### 3. yearsExperience is filter-only
Confirmed that yearsExperience is used for filtering (minExperienceYears/maxExperienceYears) but not as a scoring signal. This is legitimate as job requirements often specify minimum experience.

## Success Criteria Verification

| Criterion | Status |
|-----------|--------|
| SCORING_ALGORITHM.md exists with 150+ lines | PASS (297 lines) |
| Proxy Variable Analysis documents HIGH/MEDIUM/LOW risk | PASS |
| HIGH-risk variables confirmed NOT in scoring | PASS |
| MEDIUM-risk variables have documented justification | PASS |
| signal-weights.ts has PROXY RISK comments | PASS (13 occurrences) |

## Next Phase Readiness

**Ready for Phase 14 Plan 03:** Fairness Metrics Implementation

Prerequisites provided:
- Documented scoring signals for metrics tracking
- Identified proxy variables for monitoring
- Established baseline for impact ratio analysis

---

*Executed: 2026-01-26*
*Duration: ~15 minutes*
