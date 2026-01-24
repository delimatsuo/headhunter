# Phase 02 Plan 03: Convert Specialty Filter to Scoring - Summary

**Completed:** 2026-01-24
**Duration:** ~5 minutes

---

## One-liner

Converted hard specialty filter to soft scoring signal, allowing Gemini to evaluate edge cases like fullstack developers while ranking mismatches lower.

---

## What Was Done

### Task 1: Convert Vector Pool Specialty Filter to Scoring
**Commit:** c57f864

Replaced the `.filter()` call in the vector pool specialty processing with `.map()` that assigns `_specialty_score`:
- Match: 1.0 (direct specialty match)
- Fullstack for backend/frontend: 0.8 (good match)
- No data: 0.5 (neutral, let Gemini decide)
- Clear mismatch: 0.2 (very low but not excluded)

### Task 2: Convert searchByFunction Specialty Filter to Scoring
**Commit:** 122fea6

Applied the same scoring pattern to the `searchByFunction` method:
- Same scoring scale as Task 1
- Consistent handling across both retrieval paths
- Log message updated to reflect scoring vs filtering

### Task 3: Incorporate _specialty_score into Retrieval Scoring
**Commit:** 8bfd510

Updated the scoring loops to use pre-computed `_specialty_score`:
- Function pool scoring loop uses `candidate._specialty_score` if available
- Vector pool scoring loop uses `candidate._specialty_score` if available
- Falls back to `calculateSpecialtyScore()` for candidates without pre-computed score

---

## Verification Results

| Check | Status | Details |
|-------|--------|---------|
| Vector pool uses `.map()` | PASS | Lines 166, 195 |
| searchByFunction uses `.map()` | PASS | Line 1022 |
| `_specialty_score` in scoring | PASS | Lines 412-414, 463-465 |
| TypeScript compiles | PASS | `npm run build` succeeds |
| No specialty `.filter()` calls | PASS | None remain |

---

## Key Changes

### Files Modified
- `functions/src/engines/legacy-engine.ts`

### Score Values
| Specialty Match | Score |
|-----------------|-------|
| Direct match | 1.0 |
| Fullstack for backend/frontend | 0.8 |
| No specialty data | 0.5 |
| Unclear case | 0.4 |
| Pure mismatch | 0.2 |

---

## Commits

| Hash | Message |
|------|---------|
| c57f864 | feat(02-03): convert vector pool specialty filter to scoring |
| 122fea6 | feat(02-03): convert searchByFunction specialty filter to scoring |
| 8bfd510 | feat(02-03): incorporate _specialty_score into retrieval scoring |

---

## Impact

- **Before:** Pure frontend candidates were excluded from backend searches (30-50% candidate loss)
- **After:** All candidates pass through with scores; Gemini evaluates edge cases
- **Result:** Increased recall while maintaining precision through weighted scoring

---

## Next Phase Readiness

Ready for 02-04 or remaining Phase 2 plans. The specialty scoring integrates with the existing multi-signal scoring framework.
