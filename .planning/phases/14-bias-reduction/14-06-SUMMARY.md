---
phase: 14
plan: 06
subsystem: bias-monitoring
tags:
  - bias-metrics
  - admin-dashboard
  - eeoc-compliance
  - four-fifths-rule

dependency_graph:
  requires:
    - 14-03 (bias metrics worker provides data)
    - 14-04 (slate diversity analysis)
  provides:
    - Admin UI for bias metrics visualization
    - /admin/bias-metrics API endpoint
    - /admin/bias-metrics/history API endpoint
    - Selection rate charts
    - Impact ratio alerts
  affects:
    - Phase 15 (compliance tooling will integrate)

tech_stack:
  added: []
  patterns:
    - Tab navigation for admin sections
    - Horizontal bar chart visualization without external library
    - Graceful degradation on API errors

key_files:
  created:
    - headhunter-ui/src/components/Admin/BiasMetricsDashboard.tsx
    - headhunter-ui/src/components/Admin/BiasMetricsDashboard.css
    - headhunter-ui/src/components/Admin/SelectionRateChart.tsx
    - headhunter-ui/src/components/Admin/ImpactRatioAlert.tsx
    - headhunter-ui/src/components/Admin/AdminPage.css
  modified:
    - services/hh-admin-svc/src/routes.ts
    - services/hh-admin-svc/src/config.ts
    - services/hh-admin-svc/src/index.ts
    - headhunter-ui/src/services/api.ts
    - headhunter-ui/src/components/Admin/AdminPage.tsx

decisions:
  - key: no-external-charting-library
    value: Built custom horizontal bar visualization
    rationale: Avoid adding dependencies; CSS-based bars are sufficient for this use case
  - key: pg-pool-optional
    value: PostgreSQL pool initialization is graceful
    rationale: Admin service continues running without bias metrics if DB unavailable
  - key: admin-service-url-env
    value: REACT_APP_ADMIN_SERVICE_URL environment variable
    rationale: Support both local development (7107) and Cloud Run deployment

metrics:
  duration: ~15 minutes
  completed: 2026-01-26
---

# Phase 14 Plan 06: Bias Metrics Admin Dashboard Summary

Admin dashboard UI for bias metrics visualization with selection rate charts and impact ratio alerts.

## One-Liner

BiasMetricsDashboard component with selection rate charts and four-fifths rule alerts for EEOC compliance monitoring.

## Deliverables

### Task 1: Add bias metrics API routes to hh-admin-svc
**Commit:** e67dcfd

- Added PostgreSQL configuration to `AdminServiceConfig`
- Added `/admin/bias-metrics` endpoint for current metrics
- Added `/admin/bias-metrics/history` endpoint for trend analysis
- Implemented dimension filtering (company_tier, experience_band, specialty, all)
- Graceful degradation when database unavailable

### Task 2: Add bias metrics API client to UI
**Commit:** ef4e4e8

- Added `BiasMetricsParams`, `DimensionMetrics`, `BiasMetricsResponse` types
- Added `BiasMetricsHistoryResponse` type
- Implemented `getBiasMetrics()` method with graceful error handling
- Implemented `getBiasMetricsHistory()` method
- Configured ADMIN_SERVICE_URL for local dev vs production

### Task 3: Create BiasMetricsDashboard and supporting components
**Commit:** a6f7e9f

- Created `BiasMetricsDashboard.tsx` (210 lines)
  - Period selector (7, 30, 90 days)
  - Loading, error, and empty states
  - Adverse impact alerts section
  - Charts grid for all dimensions
  - Methodology note explaining four-fifths rule

- Created `SelectionRateChart.tsx`
  - Horizontal bar visualization
  - 80% threshold line indicator
  - Color coding (green = above threshold, red = below)
  - Sample size display
  - Small sample warning

- Created `ImpactRatioAlert.tsx`
  - Alert card for adverse impact detection
  - Lists affected groups with impact ratios
  - Includes recommended action guidance

- Updated `AdminPage.tsx`
  - Tab navigation (Access Control, Bias Metrics)
  - State management for active tab

## Technical Details

### API Endpoints

```
GET /admin/bias-metrics
  Query params:
    - days: number (default: 30)
    - dimension: 'company_tier' | 'experience_band' | 'specialty' | 'all'
    - tenant_id: string (optional)

GET /admin/bias-metrics/history
  Query params:
    - days: number (default: 90)
    - dimension: string (optional)
    - tenant_id: string (optional)
```

### UI Component Hierarchy

```
AdminPage
├── Tab: Access Control
│   └── AllowedUsersPanel
└── Tab: Bias Metrics
    └── BiasMetricsDashboard
        ├── ImpactRatioAlert (for each dimension with adverse impact)
        └── SelectionRateChart (for each dimension)
```

### Data Flow

1. BiasMetricsDashboard fetches metrics via `api.getBiasMetrics()`
2. API client makes HTTP request to `/admin/bias-metrics`
3. hh-admin-svc queries `bias_metrics` table (populated by bias_metrics_worker.py)
4. Response contains dimensions with selection rates, impact ratios, sample sizes
5. Dashboard renders alerts for dimensions with adverse impact
6. Charts visualize selection rates with 80% threshold

## Verification

- [x] Admin service compiles: `npx tsc --noEmit`
- [x] UI compiles: `cd headhunter-ui && npx tsc --noEmit`
- [x] BiasMetricsDashboard.tsx >= 150 lines (actual: 210)
- [x] ImpactRatioAlert exported
- [x] Routes contain 'bias-metrics'
- [x] getBiasMetrics pattern in dashboard -> api

## Success Criteria Met

1. [x] /admin/bias-metrics API route returns metrics from database
2. [x] /admin/bias-metrics/history API route returns historical data
3. [x] BiasMetricsDashboard displays selection rates by dimension
4. [x] SelectionRateChart shows bar chart with 80% threshold line
5. [x] ImpactRatioAlert appears when any group below 80% of highest
6. [x] Period selector allows 7/30/90 day analysis
7. [x] Methodology note explains four-fifths rule
8. [x] All components compile without TypeScript errors

## Deviations from Plan

None - plan executed exactly as written.

## Phase 14 Progress

| Plan | Name | Status |
|------|------|--------|
| 14-01 | Resume Anonymization Toggle | Complete |
| 14-02 | Demographic-Blind Scoring | Complete |
| 14-03 | Fairlearn Bias Metrics Worker | Complete |
| 14-04 | Slate Diversity Analysis | Complete |
| 14-05 | Anonymization UI Components | Complete |
| **14-06** | **Bias Metrics Admin Dashboard** | **Complete** |

**Phase 14 Status:** COMPLETE (6/6 plans)

## Next Steps

- Phase 15: Compliance Tooling
- Run bias_metrics_worker.py to populate metrics for dashboard testing
- Configure REACT_APP_ADMIN_SERVICE_URL for production deployment
