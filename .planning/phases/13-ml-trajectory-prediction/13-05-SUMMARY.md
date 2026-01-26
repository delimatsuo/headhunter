---
phase: 13-ml-trajectory-prediction
plan: 05
subsystem: api
tags: [ml, trajectory, onnx, shadow-mode, circuit-breaker, hh-search-svc, hh-trajectory-svc]

# Dependency graph
requires:
  - phase: 13-03
    provides: ONNX inference engine in hh-trajectory-svc
  - phase: 13-04
    provides: Shadow mode infrastructure for ML validation
provides:
  - ML trajectory predictions integrated into search results
  - Circuit breaker protection for hh-trajectory-svc
  - Shadow mode comparison logging (ML vs rule-based)
  - Health endpoint reporting ML trajectory availability
affects: [13-06, 14-bias-reduction]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Circuit breaker pattern for external service calls
    - Shadow mode for ML model validation
    - Graceful degradation for ML predictions

key-files:
  created:
    - services/hh-search-svc/src/ml-trajectory-client.ts
  modified:
    - services/hh-search-svc/src/config.ts
    - services/hh-search-svc/src/types.ts
    - services/hh-search-svc/src/scoring.ts
    - services/hh-search-svc/src/search-service.ts
    - services/hh-search-svc/src/index.ts
    - services/hh-search-svc/src/routes.ts

key-decisions:
  - "100ms timeout for ML predictions to prevent impact on search latency"
  - "Circuit breaker opens after 3 failures, resets after 30s cooldown"
  - "Batch predictions for top 50 candidates only for efficiency"
  - "Shadow mode: ML predictions returned in results but don't affect scoring"
  - "30s periodic health checks for hh-trajectory-svc availability"

patterns-established:
  - "Circuit breaker pattern: Protects search from cascade failures when ML service unavailable"
  - "Shadow mode pattern: Run ML and rule-based predictions side-by-side, log disagreements for validation"
  - "Graceful degradation: Search succeeds even if hh-trajectory-svc is down"

# Metrics
duration: 25min
completed: 2026-01-26
---

# Phase 13 Plan 05: hh-search-svc Integration Summary

**ML trajectory predictions enriching search results via circuit-breaker-protected HTTP client, with shadow mode comparison logging and graceful fallback**

## Performance

- **Duration:** 25 min
- **Started:** 2026-01-25T23:59:58Z
- **Completed:** 2026-01-26T00:25:00Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments
- MLTrajectoryClient with circuit breaker prevents cascade failures
- Search results include ML trajectory predictions for top 50 candidates
- Shadow mode logging compares ML vs rule-based predictions (logs when delta >30%)
- Health endpoint reports ML trajectory availability status
- Graceful degradation: search succeeds even if hh-trajectory-svc unavailable

## Task Commits

Each task was committed atomically:

1. **Task 1: Create ML trajectory HTTP client** - `c3f6314` (feat)
2. **Task 2: Extend types and integrate with scoring** - `6fcabc4` (feat)
3. **Task 3: Wire ML predictions into search flow** - `3e7d7b9` (feat)

## Files Created/Modified
- `services/hh-search-svc/src/ml-trajectory-client.ts` - HTTP client with circuit breaker for hh-trajectory-svc
- `services/hh-search-svc/src/config.ts` - Added MLTrajectoryConfig with url/enabled/timeout
- `services/hh-search-svc/src/types.ts` - Added MLTrajectoryPrediction, TrajectoryConfig, mlTrajectory field
- `services/hh-search-svc/src/scoring.ts` - Added applyMLTrajectoryScoring() and logMLRuleBasedComparison()
- `services/hh-search-svc/src/search-service.ts` - Integrated enrichWithMLTrajectoryPredictions()
- `services/hh-search-svc/src/index.ts` - Initialize MLTrajectoryClient with periodic health checks
- `services/hh-search-svc/src/routes.ts` - Added mlTrajectory status to health endpoint

## Decisions Made

**100ms timeout for ML predictions:**
- Must not impact overall search latency budget (<500ms p95 target from Phase 11)
- Predictions that timeout return null gracefully, search continues with rule-based scoring

**Circuit breaker opens after 3 failures:**
- Prevents repeated calls to unavailable service
- 30-second cooldown before attempting recovery
- Protects search service from cascade failures

**Batch predictions for top 50 candidates:**
- Balance between ML coverage and efficiency
- Most users focus on top results anyway
- Reduces load on hh-trajectory-svc

**Shadow mode implementation:**
- ML predictions returned in search results for UI display
- Rule-based trajectoryFit score still drives ranking
- Logs when ML and rule-based predictions disagree by >30% for monitoring
- Allows safe A/B comparison in production before switching to ML scoring

**30-second periodic health checks:**
- Detects when hh-trajectory-svc recovers after outage
- Updates health endpoint status for observability
- Non-blocking - runs in background interval

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

**Environment variables (optional):**
- `ML_TRAJECTORY_URL` - hh-trajectory-svc endpoint (default: http://localhost:7109)
- `ML_TRAJECTORY_ENABLED` - Enable ML predictions (default: true)
- `ML_TRAJECTORY_TIMEOUT` - Timeout in ms (default: 100)

## Next Phase Readiness

**Ready for Plan 06 (UI Components):**
- Search results include `mlTrajectory` field with:
  - nextRole and nextRoleConfidence
  - tenureMonths (min/max)
  - hireability score
  - lowConfidence flag
  - uncertaintyReason when applicable
- UI components can display ML predictions alongside rule-based signals

**Shadow mode validation enabled:**
- Comparison logs will accumulate for 4-6 weeks
- Plan 07 will analyze shadow logs to validate ML matches baseline
- Decision gate: switch to ML scoring if agreement >85% direction, >80% velocity

**Blockers:** None

**Concerns:** None

---
*Phase: 13-ml-trajectory-prediction*
*Completed: 2026-01-26*
