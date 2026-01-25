/**
 * Confidence calibrator using isotonic regression.
 * Ensures predicted probabilities match actual frequencies.
 *
 * Based on scikit-learn's IsotonicRegression from Python training pipeline.
 */
import * as fs from 'fs';

export interface CalibrationData {
  /** X values (breakpoints) for interpolation */
  breakpoints: number[];
  /** Y values (calibrated confidences) corresponding to breakpoints */
  values: number[];
  /** Minimum input value */
  minX: number;
  /** Maximum input value */
  maxX: number;
}

export class Calibrator {
  private data: CalibrationData | null = null;
  private confidenceThreshold: number;

  /**
   * Create calibrator instance.
   *
   * @param calibrationPath - Path to calibration JSON file (optional)
   * @param confidenceThreshold - Threshold for low confidence flagging (default: 0.6)
   */
  constructor(calibrationPath?: string, confidenceThreshold: number = 0.6) {
    this.confidenceThreshold = confidenceThreshold;

    if (calibrationPath) {
      this.loadCalibrationData(calibrationPath);
    }
  }

  /**
   * Load calibration data from JSON file.
   *
   * @param calibrationPath - Path to calibration JSON file
   */
  private loadCalibrationData(calibrationPath: string): void {
    console.log(`[Calibrator] Loading calibration data from ${calibrationPath}...`);

    const data = fs.readFileSync(calibrationPath, 'utf-8');
    this.data = JSON.parse(data) as CalibrationData;

    console.log(
      `[Calibrator] Loaded calibration with ${this.data.breakpoints.length} points`
    );
  }

  /**
   * Calibrate raw confidence using linear interpolation between breakpoints.
   * Implements isotonic regression prediction.
   *
   * @param rawConfidence - Raw confidence from model (0-1)
   * @returns Calibrated confidence (0-1)
   */
  calibrate(rawConfidence: number): number {
    // If no calibration data, return raw confidence
    if (!this.data) {
      return rawConfidence;
    }

    const { breakpoints, values, minX, maxX } = this.data;

    // Handle edge cases
    if (rawConfidence <= minX) {
      return values[0];
    }
    if (rawConfidence >= maxX) {
      return values[values.length - 1];
    }

    // Find surrounding breakpoints for linear interpolation
    for (let i = 0; i < breakpoints.length - 1; i++) {
      const x0 = breakpoints[i];
      const x1 = breakpoints[i + 1];

      if (rawConfidence >= x0 && rawConfidence <= x1) {
        const y0 = values[i];
        const y1 = values[i + 1];

        // Linear interpolation
        const t = (rawConfidence - x0) / (x1 - x0);
        return y0 + t * (y1 - y0);
      }
    }

    // Fallback (should not reach here if data is valid)
    return rawConfidence;
  }

  /**
   * Check if calibrated confidence is below threshold.
   *
   * @param calibratedConfidence - Calibrated confidence score
   * @returns True if confidence is low
   */
  isLowConfidence(calibratedConfidence: number): boolean {
    return calibratedConfidence < this.confidenceThreshold;
  }

  /**
   * Get confidence threshold.
   *
   * @returns Current threshold value
   */
  getThreshold(): number {
    return this.confidenceThreshold;
  }

  /**
   * Check if calibrator is initialized with data.
   *
   * @returns True if calibration data loaded
   */
  isInitialized(): boolean {
    return this.data !== null;
  }
}
