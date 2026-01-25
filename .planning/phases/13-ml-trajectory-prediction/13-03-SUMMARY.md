---
phase: 13-ml-trajectory-prediction
plan: 03
subsystem: ml-inference
tags: [onnx, inference, calibration, typescript, fastify]

# Dependency graph
requires:
  - phase: 13-01
    provides: hh-trajectory-svc service scaffold with health and predict endpoints
  - phase: 13-02
    provides: ONNX model export, vocabulary, and calibration data from Python training
provides:
  - ONNX inference engine with singleton session management
  - Input encoder mirroring Python TitleEncoder normalization
  - Isotonic regression calibrator for confidence scores
  - TrajectoryPredictor orchestrating inference, encoding, and calibration
  - /predict endpoint using ML inference with calibrated confidence
  - /predict/health endpoint for predictor status
  - Uncertainty reason generation for low confidence predictions
affects:
  - 13-04 (shadow mode will use predictor for ML vs rule-based comparison)
  - 13-05 (integration testing will validate prediction accuracy)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Singleton pattern for ONNX session management
    - Linear interpolation for isotonic regression calibration
    - Softmax application for probability distribution
    - Entropy calculation for uncertainty detection
    - Lazy initialization with setImmediate for non-blocking startup
    - Graceful shutdown with ONNX session disposal

key-files:
  created:
    - services/hh-trajectory-svc/src/inference/onnx-session.ts
    - services/hh-trajectory-svc/src/inference/input-encoder.ts
    - services/hh-trajectory-svc/src/inference/calibrator.ts
    - services/hh-trajectory-svc/src/inference/trajectory-predictor.ts
    - services/hh-trajectory-svc/src/inference/index.ts
  modified:
    - services/hh-trajectory-svc/src/routes/predict.ts
    - services/hh-trajectory-svc/src/routes/shadow-stats.ts
    - services/hh-trajectory-svc/src/index.ts

key-decisions:
  - "Singleton pattern for ONNX session to prevent repeated model loading"
  - "Linear interpolation between breakpoints for calibration (matches scikit-learn IsotonicRegression)"
  - "Confidence threshold 0.6 for low confidence flagging (configurable via environment)"
  - "Uncertainty reasons: limited history (<3 positions), ambiguous prediction (top-2 gap < 0.1), high entropy (>0.8)"
  - "Sub-50ms inference target per RESEARCH.md with duration logging"
  - "Model version: trajectory-lstm-v1.0.0"

patterns-established:
  - "ONNX session singleton with cached instance and in-flight promise tracking"
  - "Input encoder with abbreviation mapping matching Python TitleEncoder"
  - "Calibrator with JSON data loading and linear interpolation"
  - "TrajectoryPredictor orchestration: encode → inference → calibrate → uncertainty"
  - "Background initialization with setImmediate after server.listen()"
  - "Graceful shutdown with ONNX session disposal"

# Metrics
duration: 6min
completed: 2026-01-25
---

# Phase 13 Plan 03: ONNX Inference Integration Summary

**ONNX inference engine with singleton session, isotonic calibration, and uncertainty-aware predictions for hh-trajectory-svc**

## Performance

- **Duration:** 6 minutes
- **Started:** 2026-01-25T23:49:46Z
- **Completed:** 2026-01-25T23:55:52Z
- **Tasks:** 3
- **Files created:** 5
- **Files modified:** 3

## Accomplishments
- ONNX session singleton prevents repeated model loading across requests
- Input encoder normalizes titles matching Python TitleEncoder (abbreviations, lowercase, punctuation)
- Isotonic regression calibrator applies linear interpolation for confidence scores
- TrajectoryPredictor orchestrates end-to-end inference with uncertainty detection
- /predict endpoint uses real ML inference with calibrated confidence and uncertainty reasons
- Inference duration logging for sub-50ms performance monitoring

## Task Commits

Each task was committed atomically:

1. **Task 1: ONNX session singleton and input encoder** - `896dca7` (feat)
2. **Task 2: Calibrator and trajectory predictor** - `603ee3f` (feat)
3. **Task 3: Wire predict route to use TrajectoryPredictor** - `2c3aa7a` (feat)

## Files Created/Modified

**Created:**
- `services/hh-trajectory-svc/src/inference/onnx-session.ts` - Singleton ONNX session with optimized config (CPU, graph optimization, 4 threads)
- `services/hh-trajectory-svc/src/inference/input-encoder.ts` - Title normalization and encoding to BigInt64Array tensors
- `services/hh-trajectory-svc/src/inference/calibrator.ts` - Isotonic regression via linear interpolation between breakpoints
- `services/hh-trajectory-svc/src/inference/trajectory-predictor.ts` - Inference orchestration with softmax, calibration, uncertainty
- `services/hh-trajectory-svc/src/inference/index.ts` - Barrel export for inference module

**Modified:**
- `services/hh-trajectory-svc/src/routes/predict.ts` - POST /predict uses TrajectoryPredictor, GET /predict/health added
- `services/hh-trajectory-svc/src/routes/shadow-stats.ts` - Fixed TypeScript unused param warnings
- `services/hh-trajectory-svc/src/index.ts` - Predictor initialization in background, ONNX disposal on shutdown

## Decisions Made

### 1. Singleton pattern for ONNX session
**Context:** ONNX model loading is expensive (~100ms+), should happen once per service instance
**Decision:** Static singleton with in-flight promise tracking to prevent duplicate initialization
**Impact:** Efficient resource usage, fast subsequent predictions

### 2. Linear interpolation for calibration
**Context:** Python training uses scikit-learn IsotonicRegression with breakpoints
**Decision:** Implement linear interpolation between breakpoints in TypeScript
**Impact:** Matches Python calibration behavior without scikit-learn dependency

### 3. Confidence threshold 0.6
**Context:** Need to flag low confidence predictions for user awareness
**Decision:** Default 0.6 threshold (configurable via TRAJECTORY_CONFIDENCE_THRESHOLD)
**Impact:** Balance between precision and recall for uncertainty flagging

### 4. Uncertainty reason generation
**Context:** Low confidence predictions need explanation for users
**Decision:** Generate specific reasons based on heuristics:
  - Limited career history (<3 positions)
  - Ambiguous next role (top-2 gap < 0.1)
  - Unusual career pattern (entropy > 0.8)
**Impact:** Actionable feedback for users and model improvement insights

### 5. Background initialization
**Context:** Cloud Run requires fast startup (<10s)
**Decision:** Use setImmediate() for non-blocking model loading after server.listen()
**Impact:** Health endpoint responds immediately, /predict returns 503 until ready

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed TypeScript unused parameter warnings**
- **Found during:** Task 3 (TypeScript compilation)
- **Issue:** `predictedIdx` parameter in `getUncertaintyReason()` not used, `request` params in shadow-stats routes unused
- **Fix:** Prefixed unused params with underscore (`_predictedIdx`, `_request`)
- **Files modified:** trajectory-predictor.ts, shadow-stats.ts
- **Verification:** TypeScript compilation passes without errors
- **Committed in:** 603ee3f, 2c3aa7a (part of task commits)

**2. [Rule 3 - Blocking] Removed unused import**
- **Found during:** Task 3 (TypeScript compilation)
- **Issue:** `TrajectoryServiceConfig` imported but not used in predict.ts
- **Fix:** Removed import statement
- **Files modified:** routes/predict.ts
- **Verification:** TypeScript compilation passes
- **Committed in:** 2c3aa7a (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Minor code quality fixes, no functional changes. Essential for TypeScript compilation.

## Issues Encountered

None - plan executed smoothly with TypeScript compilation verified at each step.

## How It Works

### Inference Flow

```typescript
// 1. Service startup
const predictor = new TrajectoryPredictor(config);
await predictor.initialize(); // Loads ONNX, vocab, calibrator

// 2. Prediction request
const prediction = await predictor.predict({
  candidateId: "...",
  titleSequence: ["Software Engineer", "Senior Engineer", "Staff Engineer"]
});

// 3. Internal steps
// - Encode titles → BigInt64Array [1, 15, 42]
// - Create ONNX tensors (title_ids, lengths)
// - Run inference → next_role_logits, tenure_pred, hireability
// - Apply softmax → probabilities
// - Get top prediction → "Principal Engineer" (raw confidence 0.82)
// - Calibrate → 0.75 calibrated confidence
// - Check threshold → lowConfidence = false
// - Return prediction with all fields
```

### Uncertainty Detection

```typescript
// Low confidence flagged when calibrated < 0.6
if (calibratedConfidence < 0.6) {
  // Generate specific reason
  if (titleSequence.length < 3) {
    uncertaintyReason = "Limited career history (fewer than 3 positions)";
  } else if (topProb - secondProb < 0.1) {
    uncertaintyReason = "Ambiguous next role (multiple likely paths)";
  } else if (entropy / maxEntropy > 0.8) {
    uncertaintyReason = "Unusual career pattern detected";
  }
}
```

## Next Phase Readiness

**Blocks:** None - inference engine complete and ready for integration

**Enables:**
- 13-04: Shadow mode can now compare ML predictions to rule-based baseline
- 13-05: Integration tests can validate prediction accuracy
- 13-06: API Gateway can route requests to /predict endpoint

**Recommendations:**
1. Add actual ONNX model file and vocabulary JSON for testing
2. Create sample calibration data for development
3. Add integration tests with mock ONNX model
4. Monitor inference duration in production (target: <50ms)
5. Collect uncertainty reason distribution for model improvement

**Ready for:** Shadow mode implementation (Plan 13-04)

---
*Phase: 13-ml-trajectory-prediction*
*Completed: 2026-01-25*
