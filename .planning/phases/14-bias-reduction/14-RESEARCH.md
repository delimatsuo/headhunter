# Phase 14: Bias Reduction - Research

**Researched:** 2026-01-26
**Domain:** ML Fairness, Resume Anonymization, Bias Metrics
**Confidence:** MEDIUM-HIGH

## Summary

Phase 14 focuses on three distinct but interconnected capabilities: (1) resume anonymization to enable blind hiring workflows, (2) demographic-blind scoring to eliminate proxy discrimination, and (3) a bias metrics dashboard for administrators. The technology decision for Fairlearn 0.13.0 is locked, providing `MetricFrame`, `demographic_parity_difference`, and `selection_rate` as the core APIs for bias measurement.

The standard approach is:
1. **Anonymization middleware** - Response transformer in hh-search-svc that strips PII fields (name, photo, school names) when `anonymizedView` toggle is enabled
2. **Proxy variable audit** - Document which scoring signals could serve as demographic proxies, then remove or neutralize them
3. **Fairlearn-based metrics service** - Python service exposing bias metrics via REST API, consumed by React admin dashboard
4. **Diverse slate indicators** - Post-search analysis to warn when candidate pool lacks diversity across dimensions

The four-fifths rule (80% threshold) is the industry-standard for adverse impact detection, though Fairlearn's documentation explicitly warns against misapplication outside its US employment law context. Implementation should focus on selection rate ratios rather than attempting legal interpretation.

**Primary recommendation:** Implement anonymization as response middleware (cleanest separation), run proxy audit on scoring.ts signal weights, deploy Fairlearn metrics as a Python worker bound to hh-admin-svc, and build slate diversity analysis as a post-search pass in hh-search-svc.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Fairlearn | ^0.13.0 | Bias metrics (demographic parity, selection rates, equalized odds) | MIT license, actively maintained, simpler API than AIF360, official Microsoft project |
| pandas | ^2.2.0 | Data manipulation for metrics computation | Required dependency for Fairlearn MetricFrame |
| numpy | ^1.26.0 | Numerical operations | Required dependency for Fairlearn |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Recharts | ^2.12.0 | React charts for bias dashboard | Selection rate trends, impact ratio visualization |
| Tremor | ^3.17.0 | Dashboard components | Pre-built bar charts, tables for admin metrics display |
| scikit-learn | ^1.4.0 | Metrics utilities (confusion_matrix, etc.) | Already in stack, provides foundation for Fairlearn |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Fairlearn | AIF360 (IBM) | AIF360 has more algorithms but heavier, more complex API |
| Fairlearn | What-If Tool (Google) | WIT is visualization-focused, less programmatic |
| Custom metrics | Hand-rolled four-fifths calc | Don't - edge cases in small sample sizes, confidence intervals |

**Installation:**
```bash
# Python (add to scripts/requirements.txt)
pip install fairlearn>=0.13.0 pandas>=2.2.0

# React (already have these in headhunter-ui)
npm install recharts tremor  # If not already installed
```

## Architecture Patterns

### Recommended Project Structure
```
services/hh-search-svc/src/
├── middleware/
│   └── anonymization.ts      # Response transformer for anonymized view
├── bias/
│   └── slate-diversity.ts    # Post-search diversity analysis
└── ...

services/hh-admin-svc/src/
├── routes/
│   └── bias-metrics.ts       # Proxy routes to Python worker
└── ...

scripts/
├── bias_metrics_worker.py    # Fairlearn-based metrics computation
└── ...

headhunter-ui/src/
├── components/Admin/
│   ├── BiasMetricsDashboard.tsx
│   ├── SelectionRateChart.tsx
│   └── ImpactRatioAlert.tsx
└── ...
```

### Pattern 1: Anonymization Middleware
**What:** Response transformer that strips PII fields based on request flag
**When to use:** When recruiter toggles "Anonymized View" in UI
**Example:**
```typescript
// Source: Industry-standard blind hiring pattern
interface AnonymizationConfig {
  stripFields: string[];      // ['fullName', 'headline', 'educationInstitutions']
  maskPatterns: RegExp[];     // University names, company names if needed
  keepFields: string[];       // ['skills', 'yearsExperience', 'signalScores']
}

export function anonymizeCandidate(
  candidate: HybridSearchResultItem,
  config: AnonymizationConfig
): AnonymizedCandidate {
  const result: AnonymizedCandidate = {
    candidateId: candidate.candidateId,  // Keep for tracking
    score: candidate.score,
    yearsExperience: candidate.yearsExperience,
    skills: candidate.skills,
    signalScores: candidate.signalScores,
    matchReasons: candidate.matchReasons,
    // Strip PII
    fullName: undefined,
    headline: undefined,
    location: undefined,  // Optional: may reveal demographics
  };

  return result;
}
```

### Pattern 2: Fairlearn MetricFrame Integration
**What:** Compute selection rates and impact ratios by demographic group
**When to use:** Admin dashboard metrics, periodic bias audits
**Example:**
```python
# Source: https://fairlearn.org/main/user_guide/assessment/common_fairness_metrics.html
from fairlearn.metrics import MetricFrame, selection_rate, demographic_parity_ratio

def compute_bias_metrics(
    y_true: np.ndarray,      # Ground truth (was candidate selected/hired)
    y_pred: np.ndarray,      # Predictions (was candidate shown/shortlisted)
    sensitive_features: pd.Series  # Demographic group membership
) -> dict:
    """
    Compute selection rates and impact ratios using Fairlearn MetricFrame.
    """
    mf = MetricFrame(
        metrics={'selection_rate': selection_rate},
        y_true=y_true,
        y_pred=y_pred,
        sensitive_features=sensitive_features
    )

    # Get per-group selection rates
    group_rates = mf.by_group['selection_rate'].to_dict()

    # Compute impact ratio (four-fifths rule)
    max_rate = max(group_rates.values())
    impact_ratios = {
        group: rate / max_rate if max_rate > 0 else 0
        for group, rate in group_rates.items()
    }

    # Flag groups below 80% threshold
    adverse_impact_groups = [
        group for group, ratio in impact_ratios.items()
        if ratio < 0.8
    ]

    return {
        'selection_rates': group_rates,
        'impact_ratios': impact_ratios,
        'adverse_impact_detected': len(adverse_impact_groups) > 0,
        'adverse_impact_groups': adverse_impact_groups,
        'demographic_parity_ratio': demographic_parity_ratio(
            y_true, y_pred, sensitive_features=sensitive_features
        )
    }
```

### Pattern 3: Slate Diversity Analysis
**What:** Post-search analysis to detect homogeneous candidate pools
**When to use:** Every search response, displayed as warning indicator
**Example:**
```typescript
// Source: Rooney Rule / diverse slate best practices
interface SlateDiversity {
  dimension: string;           // 'companyTier', 'yearsExperience', 'specialty'
  distribution: Record<string, number>;  // { 'faang': 8, 'startup': 2 }
  concentrationPct: number;    // 80% = 8/10 from same group
  warning?: string;            // "This slate is 80% from enterprise tier - consider broadening"
}

export function analyzeSlatediversity(
  candidates: HybridSearchResultItem[],
  dimensions: string[]
): SlateDiversity[] {
  return dimensions.map(dim => {
    const distribution = countByDimension(candidates, dim);
    const maxCount = Math.max(...Object.values(distribution));
    const concentrationPct = (maxCount / candidates.length) * 100;

    return {
      dimension: dim,
      distribution,
      concentrationPct,
      warning: concentrationPct > 70
        ? `This slate is ${concentrationPct}% from same ${dim} - consider broadening`
        : undefined
    };
  });
}
```

### Anti-Patterns to Avoid
- **Anonymization at source:** Don't anonymize in database - do it at response layer to preserve auditability
- **Four-fifths as hard rule:** Don't auto-reject searches based on impact ratio - it's a signal, not a gate
- **Ignoring small sample sizes:** Don't compute impact ratios with <20 candidates per group - statistically meaningless
- **Proxy detection in real-time:** Don't try to detect proxies dynamically - do static audit and document

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Selection rate calculation | Simple division | Fairlearn `selection_rate` | Edge cases with empty groups, NaN handling |
| Impact ratio computation | max/min ratio | Fairlearn `demographic_parity_ratio` | Statistical adjustments for small samples |
| Confidence intervals | Bootstrap yourself | Fairlearn with `scipy.stats` | Bias in small samples, proper interval estimation |
| Four-fifths rule alerts | Simple 0.8 threshold | Fairlearn + statistical significance test | False alarms in small samples need p-value |
| PII detection/redaction | Regex patterns | Existing NLP entity recognition or allowlist | Name patterns vary by culture, regex fails |

**Key insight:** Bias metrics are deceptively simple - the formulas are straightforward but edge cases (small groups, missing data, intersectionality) create subtle bugs. Fairlearn handles these cases correctly.

## Common Pitfalls

### Pitfall 1: Proxy Leakage in Anonymization
**What goes wrong:** Anonymizing name but keeping university reveals demographic (e.g., HBCUs indicate race)
**Why it happens:** Developers think of PII as "obviously personal" fields, not indirect indicators
**How to avoid:** Comprehensive proxy audit - document ALL fields that could correlate with protected characteristics:
- Graduation year → age
- Zip code / location → race, socioeconomic status
- University name → race, socioeconomic status
- Company names → may correlate with demographics
**Warning signs:** Recruiters can "guess" demographics from anonymized profiles

### Pitfall 2: Four-Fifths Rule Misapplication
**What goes wrong:** Treating 80% threshold as legal compliance, not statistical signal
**Why it happens:** Conflating regulatory guidance with technical requirement
**How to avoid:**
- Use four-fifths as alert threshold only, not automatic rejection
- Always include sample sizes in dashboard
- Add statistical significance test (chi-square or Fisher's exact)
- Document that ratio < 0.8 requires investigation, not remediation
**Warning signs:** Automated actions based solely on impact ratio

### Pitfall 3: Small Sample Size False Alarms
**What goes wrong:** Impact ratio alerts fire when 1 of 2 candidates from group X is selected (50% rate)
**Why it happens:** Ratio-based metrics are unstable with small N
**How to avoid:**
- Set minimum sample size threshold (recommend N>=20 per group)
- Display confidence intervals, not point estimates
- Use Fisher's exact test for small samples instead of chi-square
**Warning signs:** Frequent alerts that disappear when more data is collected

### Pitfall 4: Demographic Data Collection Without Purpose
**What goes wrong:** Collecting protected attributes to compute metrics, then that data becomes liability
**Why it happens:** Need demographics to measure bias, but collecting creates privacy/legal risk
**How to avoid:**
- Aggregate metrics only - never store individual demographic flags
- Use inferred proxies (university tier, location region) for analysis
- Implement strict access controls on any demographic data
- Document data minimization policy
**Warning signs:** Individual-level demographic data in search logs

### Pitfall 5: Bias Audit with Test Data
**What goes wrong:** Running compliance audit on synthetic or test data, not production
**Why it happens:** Production data is messy, test data is clean
**How to avoid:**
- NYC LL144 explicitly requires audit on "historical" (production) data
- Use production data exports with PII stripped
- Document data provenance in audit report
**Warning signs:** Audit report based on data generated specifically for audit

## Code Examples

Verified patterns from official sources:

### MetricFrame Basic Usage
```python
# Source: https://fairlearn.org/main/user_guide/assessment/common_fairness_metrics.html
from fairlearn.metrics import MetricFrame, selection_rate
import pandas as pd

# Data: y_true is whether candidate was actually hired
# y_pred is whether candidate was shown/shortlisted
# sensitive_features is demographic group (can be inferred from data)

mf = MetricFrame(
    metrics={'selection_rate': selection_rate},
    y_true=y_true,
    y_pred=y_pred,
    sensitive_features=sensitive_features
)

# Overall selection rate
print(f"Overall: {mf.overall['selection_rate']:.2%}")

# Per-group breakdown
print(mf.by_group)

# Disparity metrics
print(f"Difference: {mf.difference()}")
print(f"Ratio: {mf.ratio()}")
```

### Dashboard API Endpoint
```python
# Source: FastAPI + Fairlearn integration pattern
from fastapi import FastAPI, Query
from fairlearn.metrics import MetricFrame, selection_rate, demographic_parity_ratio
from datetime import datetime, timedelta

app = FastAPI()

@app.get("/admin/bias-metrics")
async def get_bias_metrics(
    start_date: datetime = Query(default=datetime.now() - timedelta(days=30)),
    end_date: datetime = Query(default=datetime.now()),
    dimension: str = Query(default="company_tier")  # company_tier, experience_band, specialty
):
    """
    Compute bias metrics for a given time period and grouping dimension.
    Returns selection rates, impact ratios, and adverse impact warnings.
    """
    # Fetch selection data from PostgreSQL
    # y_true: was candidate advanced (shortlisted, interviewed, hired)
    # y_pred: was candidate shown in results
    # sensitive_features: company_tier, experience band, etc.

    data = await fetch_selection_data(start_date, end_date, dimension)

    mf = MetricFrame(
        metrics={'selection_rate': selection_rate},
        y_true=data['advanced'],
        y_pred=data['shown'],
        sensitive_features=data[dimension]
    )

    return {
        "period": {"start": start_date, "end": end_date},
        "dimension": dimension,
        "overall_rate": mf.overall['selection_rate'],
        "by_group": mf.by_group['selection_rate'].to_dict(),
        "ratio": mf.ratio()['selection_rate'],
        "difference": mf.difference()['selection_rate'],
        "adverse_impact": mf.ratio()['selection_rate'] < 0.8
    }
```

### React Anonymization Toggle
```tsx
// Source: Standard blind hiring UI pattern
interface SearchControlsProps {
  anonymizedView: boolean;
  onToggleAnonymized: (enabled: boolean) => void;
}

export const SearchControls: React.FC<SearchControlsProps> = ({
  anonymizedView,
  onToggleAnonymized
}) => {
  return (
    <div className="search-controls">
      <label className="anonymized-toggle">
        <input
          type="checkbox"
          checked={anonymizedView}
          onChange={(e) => onToggleAnonymized(e.target.checked)}
        />
        <span className="toggle-label">
          Anonymized View
          <Tooltip title="Hides candidate names, photos, and school names to reduce unconscious bias">
            <InfoIcon />
          </Tooltip>
        </span>
      </label>
    </div>
  );
};
```

### Anonymized Candidate Card
```tsx
// Source: Blind hiring UI pattern
interface AnonymizedCandidateCardProps {
  candidate: HybridSearchResultItem;
  rank: number;
}

export const AnonymizedCandidateCard: React.FC<AnonymizedCandidateCardProps> = ({
  candidate,
  rank
}) => {
  // Show only bias-neutral information
  return (
    <div className="anonymized-candidate-card">
      <div className="rank-badge">#{rank}</div>

      <div className="experience-summary">
        <span className="years">{candidate.yearsExperience} years experience</span>
        <span className="level">{candidate.signalScores?.seniorityAlignment > 0.8 ? 'Senior' : 'Mid'} level</span>
      </div>

      <div className="skills-section">
        <h4>Skills</h4>
        <div className="skill-chips">
          {candidate.skills?.slice(0, 10).map(skill => (
            <span key={skill.name} className="skill-chip">{skill.name}</span>
          ))}
        </div>
      </div>

      <div className="match-score">
        <span className="score">{Math.round(candidate.score * 100)}%</span>
        <span className="label">Match Score</span>
      </div>

      {/* Signal breakdown - all bias-neutral signals */}
      <SignalScoreBreakdown
        signalScores={candidate.signalScores}
        excludeSignals={['companyPedigree']}  // May be proxy
      />
    </div>
  );
};
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual PII redaction | AI-assisted entity detection + allowlist | 2024-2025 | Faster, more accurate anonymization |
| Simple ratio thresholds | Statistical significance testing with ratios | 2023-2024 | Fewer false alarms on small samples |
| Post-hoc bias analysis | Integrated pipeline metrics | 2024-2025 | Real-time monitoring, faster detection |
| Single demographic dimension | Intersectional analysis | 2023-2024 | Catches compound discrimination |
| AIF360 (IBM) dominant | Fairlearn gaining share | 2023-2024 | Simpler API, better maintenance |

**Deprecated/outdated:**
- FairlearnDashboard widget - deprecated in favor of Responsible AI Toolbox
- Simple four-fifths without confidence intervals - leads to false alarms
- Binary demographic categories - intersectionality is now expected

## Proxy Variable Audit

Fields in current scoring that could serve as demographic proxies:

| Field | Proxy Risk | Current Use | Recommendation |
|-------|-----------|-------------|----------------|
| `location` | HIGH - correlates with race, income | Filter, display | Remove from scoring, keep for filtering only |
| `yearsExperience` | MEDIUM - correlates with age | Scoring signal | Keep but document as legitimate job-related factor |
| `companyPedigree` | MEDIUM - "FAANG" correlates with demographics | Scoring signal | Consider reducing weight or using industry instead |
| `educationInstitutions` | HIGH - strongly correlates with race, socioeconomic | Display only | Strip in anonymized view, never use in scoring |
| `graduationYear` | HIGH - directly reveals age | Not used | Ensure never added |
| `headline` | LOW-MEDIUM - may contain school/company names | Display | Strip in anonymized view |
| `seniorityAlignment` | LOW - job-related | Scoring signal | Keep - legitimate requirement |
| `skillsExactMatch` | LOW - job-related | Scoring signal | Keep - legitimate requirement |
| `trajectoryFit` | LOW - job-related | Scoring signal | Keep - legitimate requirement |

**Recommended actions:**
1. Audit `scoring.ts` and `signal-weights.ts` to confirm no zip code, graduation year use
2. Document that `companyPedigree` has proxy risk but is job-related (may defend if challenged)
3. Ensure `educationInstitutions` is display-only, never influences score
4. Add scoring algorithm documentation for BIAS-02 compliance

## Integration Points

### hh-search-svc Integration
- Add `anonymizedView` boolean to `HybridSearchRequest`
- Add anonymization middleware to response pipeline
- Add slate diversity analysis after ranking
- Return diversity warnings in response metadata

### hh-admin-svc Integration
- New routes for bias metrics API
- Proxy to Python worker for Fairlearn computations
- Periodic job to compute aggregate metrics

### headhunter-ui Integration
- Anonymization toggle in search controls
- AnonymizedCandidateCard component (variant of SkillAwareCandidateCard)
- BiasMetricsDashboard in Admin section
- ImpactRatioAlert component for warnings

### Data Flow
```
Search Request (anonymizedView: true)
    ↓
hh-search-svc (normal search pipeline)
    ↓
Anonymization Middleware (strips PII)
    ↓
Slate Diversity Analysis (computes warnings)
    ↓
Response (anonymized candidates + diversity warnings)

Selection Events (async)
    ↓
PostgreSQL audit log
    ↓
Python worker (periodic)
    ↓
Fairlearn MetricFrame computation
    ↓
hh-admin-svc cache
    ↓
Admin Dashboard API
```

## Open Questions

Things that couldn't be fully resolved:

1. **Demographic data source**
   - What we know: Need demographic groups to compute selection rates
   - What's unclear: Do we have any demographic data? If not, what proxies to use?
   - Recommendation: Use inferred dimensions (company tier, experience band, specialty) rather than collecting demographics

2. **Selection event definition**
   - What we know: Four-fifths rule compares selection rates
   - What's unclear: What counts as "selected"? Shown in results? Shortlisted? Hired?
   - Recommendation: Define multiple thresholds (shown, clicked, shortlisted) and track all

3. **Historical data availability**
   - What we know: NYC LL144 requires audit on historical data
   - What's unclear: How much selection history exists? Is it sufficient for statistical significance?
   - Recommendation: Start logging selection events now, even if Phase 14 deploy delayed

4. **Intersectionality scope**
   - What we know: Fairlearn supports intersecting groups
   - What's unclear: How many dimensions to track? Company tier + experience + specialty = combinatorial explosion
   - Recommendation: Start with single dimensions, add intersections if sample sizes support

## Sources

### Primary (HIGH confidence)
- [Fairlearn 0.13.0 PyPI](https://pypi.org/project/fairlearn/) - Version, Python requirements, installation
- [Fairlearn Common Fairness Metrics](https://fairlearn.org/main/user_guide/assessment/common_fairness_metrics.html) - API usage, MetricFrame, four-fifths rule caveats
- [Fairlearn API Reference](https://fairlearn.org/main/api_reference/index.html) - Function signatures, class documentation

### Secondary (MEDIUM confidence)
- [Four-Fifths Rule Legal Context](https://www.law.cornell.edu/cfr/text/29/1607.4) - 29 CFR 1607.4, official regulation
- [Adverse Impact Calculation](https://www.adverseimpact.org/CalculatingAdverseImpact/Four-FifthsRule.htm) - Practical examples
- [Blind Resume Screening Guide](https://www.redactable.com/blog/redact-a-resume) - What to redact, implementation patterns
- [Proxy Discrimination in Data-Driven Systems](https://arxiv.org/pdf/1707.08120) - Academic reference on proxy variables

### Tertiary (LOW confidence)
- [AI Bias in Hiring 2026](https://www.fisherphillips.com/en/news-insights/why-you-need-to-care-about-ai-bias-in-2026.html) - Legal landscape, not technical
- [Diverse Slate Hiring Guide](https://blog.ongig.com/diversity-and-inclusion/diverse-slate-hiring/) - Industry practices, not technical implementation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Fairlearn 0.13.0 verified on PyPI, API documented
- Architecture: MEDIUM-HIGH - Patterns are industry-standard, integration points clear
- Pitfalls: HIGH - Well-documented in legal and technical literature
- Proxy audit: MEDIUM - Requires validation against actual scoring code

**Research date:** 2026-01-26
**Valid until:** 60 days (fairness domain is mature, Fairlearn stable)
