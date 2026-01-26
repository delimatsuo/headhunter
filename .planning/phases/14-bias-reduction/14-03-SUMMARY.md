---
type: summary
phase: 14-bias-reduction
plan: 03
subsystem: bias-metrics
tags: [fairlearn, bias-reduction, selection-events, impact-ratio, four-fifths-rule]

dependency_graph:
  requires: ["14-01"]
  provides: ["selection-event-logging", "bias-metrics-worker", "four-fifths-rule-analysis"]
  affects: ["14-04", "14-05"]

tech_stack:
  added: ["fairlearn>=0.13.0", "scipy>=1.11.0"]
  patterns: ["event-sourcing", "dimension-inference", "statistical-significance-testing"]

key_files:
  created:
    - scripts/migrations/013_bias_tables.sql
    - scripts/bias_metrics_worker.py
    - services/hh-search-svc/src/bias/selection-events.ts
    - services/hh-search-svc/src/bias/selection-events.test.ts
  modified:
    - requirements.txt
    - services/hh-search-svc/src/bias/index.ts

decisions:
  - id: "14-03-D1"
    choice: "Renamed inference functions to avoid export conflicts"
    rationale: "slate-diversity module exports similar but differently typed inference functions"
  - id: "14-03-D2"
    choice: "Use 013 for migration number"
    rationale: "Existing migrations go up to 012"
  - id: "14-03-D3"
    choice: "Chi-square + Fisher's exact tests"
    rationale: "Chi-square for larger samples, Fisher's exact for small expected counts (<5)"

metrics:
  duration: "~5 minutes"
  completed: "2026-01-26"
---

# Phase 14 Plan 03: Fairlearn Bias Metrics Worker Summary

**One-liner:** Selection event logging with Fairlearn-based four-fifths rule impact ratio analysis

## What Was Built

### 1. Database Migration (013_bias_tables.sql)
Created PostgreSQL schema for bias tracking:
- **selection_events table**: Tracks candidate interactions (shown, clicked, shortlisted, contacted, interviewed, hired)
- **bias_metrics table**: Stores computed Fairlearn results as JSONB
- Indexes for tenant/timestamp, search_id, event_type, and dimension queries

### 2. Selection Event Logging Module (TypeScript)
Created `services/hh-search-svc/src/bias/selection-events.ts`:
- `SelectionEvent` interface with full event metadata
- `InferredDimensions` interface with strict union types for companyTier, experienceBand, specialty
- Dimension inference functions:
  - `inferSelectionCompanyTier()`: FAANG/enterprise/startup/other classification
  - `inferSelectionExperienceBand()`: 0-3/3-7/7-15/15+ bands
  - `inferSelectionSpecialty()`: backend/frontend/fullstack/devops/data/ml/mobile/other
- `createSelectionEvent()`: Factory function for event creation
- `logSelectionEvent()`: Single event logging to PostgreSQL
- `logSelectionEventsBatch()`: Batch logging for efficiency

### 3. Fairlearn Bias Metrics Worker (Python)
Created `scripts/bias_metrics_worker.py` (366 lines):
- Uses Fairlearn `MetricFrame` for selection rate computation
- Computes impact ratios using four-fifths rule (0.8 threshold)
- Statistical significance testing:
  - Chi-square test when expected counts >= 5
  - Fisher's exact test for small samples
- Human-readable warnings for dashboard display
- CLI interface with arguments:
  - `--days`: Lookback period
  - `--dimension`: Specific dimension to analyze
  - `--all-dimensions`: Compute all three dimensions
  - `--tenant-id`: Filter by tenant
  - `--output`: JSON file output
  - `--save-to-db`: Persist results to bias_metrics table

## Key Design Decisions

1. **Renamed inference functions**: Used `inferSelectionCompanyTier` etc. instead of `inferCompanyTier` to avoid export conflicts with slate-diversity module (different return types)

2. **Strict union types**: Selection events use strict TypeScript union types (`'faang' | 'enterprise' | 'startup' | 'other'`) while slate-diversity uses strings for flexibility

3. **Statistical testing strategy**: Chi-square for normal samples, Fisher's exact for small expected counts (<5), minimum sample size of 20 for validity

4. **Non-blocking logging**: Selection event logging catches errors and logs them but doesn't throw - bias tracking should never break search

## Test Coverage

23 unit tests passing:
- `inferSelectionCompanyTier`: 7 tests (FAANG, enterprise, startup, unknown, case handling)
- `inferSelectionExperienceBand`: 3 tests (bands, undefined handling, edge cases)
- `inferSelectionSpecialty`: 9 tests (all specialties, title vs skills priority)
- `createSelectionEvent`: 4 tests (full event, optional fields, unique IDs, all event types)

## Files Changed

| File | Change | Purpose |
|------|--------|---------|
| `scripts/migrations/013_bias_tables.sql` | Created | PostgreSQL schema for bias tracking |
| `requirements.txt` | Modified | Add fairlearn>=0.13.0, scipy>=1.11.0 |
| `services/hh-search-svc/src/bias/selection-events.ts` | Created | TypeScript event logging module |
| `services/hh-search-svc/src/bias/selection-events.test.ts` | Created | 23 unit tests |
| `services/hh-search-svc/src/bias/index.ts` | Modified | Export selection-events |
| `scripts/bias_metrics_worker.py` | Created | Fairlearn metrics worker |

## Commits

1. `5842bdf` - feat(14-03): add database migration for bias tracking tables
2. `893ad7c` - feat(14-03): add Fairlearn and scipy to requirements.txt
3. `13f3837` - feat(14-03): add selection event logging module for bias tracking
4. `8468752` - feat(14-03): add Fairlearn-based bias metrics worker

## Requirements Satisfied

- **BIAS-03**: Selection event logging for bias tracking - COMPLETE
- **BIAS-04**: Bias metrics computation with Fairlearn - COMPLETE
  - Selection rates per dimension
  - Impact ratio (four-fifths rule) with 0.8 threshold
  - Statistical significance testing
  - Human-readable warnings

## Deviations from Plan

1. **Migration file numbered 013 instead of 011**: Existing migrations already use 011-012
2. **Inference functions renamed**: Added `Selection` prefix to avoid export conflicts with slate-diversity module

## Next Phase Readiness

Plan 14-04 (Admin Dashboard) can proceed:
- Database tables ready for metrics storage
- bias_metrics_worker.py provides data for dashboard
- Selection events module ready for integration with search routes

## Usage Examples

```bash
# Run worker for last 30 days, all dimensions
python scripts/bias_metrics_worker.py --days 30 --all-dimensions

# Single dimension analysis
python scripts/bias_metrics_worker.py --days 7 --dimension company_tier

# Save to database
python scripts/bias_metrics_worker.py --days 30 --tenant-id tenant-abc --save-to-db

# Output to file
python scripts/bias_metrics_worker.py --output /tmp/metrics.json
```

```typescript
// Log selection event in search route
import { createSelectionEvent, logSelectionEvent } from './bias/selection-events';

const event = createSelectionEvent(
  'shown',
  candidate.candidateId,
  searchId,
  tenantId,
  userIdHash,
  {
    companies: candidate.companies,
    yearsExperience: candidate.yearsExperience,
    skills: candidate.skills.map(s => s.name),
    title: candidate.title,
    rank: index,
    score: candidate.score,
  }
);
await logSelectionEvent(pool, event);
```
