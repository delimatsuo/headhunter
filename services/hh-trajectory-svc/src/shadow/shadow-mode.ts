/**
 * Shadow Mode Orchestrator
 *
 * Coordinates ML vs rule-based comparison logging during validation period.
 */

import RuleBasedBridge from './rule-based-bridge.js';
import ComparisonLogger, { type ComparisonLoggerConfig, type ShadowComparison, type ShadowStats } from './comparison-logger.js';
import type { PredictRequest } from '../types.js';

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * ML trajectory prediction for shadow comparison.
 */
export interface TrajectoryPrediction {
  nextRole: string;
  nextRoleConfidence: number;
  tenureMonths: {
    min: number;
    max: number;
  };
  hireability: number;
}

/**
 * Shadow mode configuration.
 */
export interface ShadowModeConfig {
  /** Whether shadow mode is enabled */
  enabled: boolean;
  /** Comparison logger configuration */
  loggerConfig: ComparisonLoggerConfig;
}

// ============================================================================
// Shadow Mode Class
// ============================================================================

/**
 * Orchestrates shadow mode comparison between ML and rule-based predictions.
 */
export default class ShadowMode {
  private bridge: RuleBasedBridge;
  private logger: ComparisonLogger;
  private enabled: boolean;

  constructor(config: ShadowModeConfig) {
    this.enabled = config.enabled;
    this.bridge = new RuleBasedBridge();
    this.logger = new ComparisonLogger(config.loggerConfig);
  }

  /**
   * Checks if shadow mode is enabled.
   */
  isEnabled(): boolean {
    return this.enabled;
  }

  /**
   * Compares ML prediction with rule-based metrics and logs the result.
   *
   * @param request - Original prediction request
   * @param mlPrediction - ML model prediction
   */
  async compare(request: PredictRequest, mlPrediction: TrajectoryPrediction): Promise<void> {
    if (!this.enabled) {
      return; // Shadow mode disabled
    }

    // Compute rule-based metrics using Phase 8 logic
    const ruleBased = this.bridge.compute(request.titleSequence);

    // Infer direction from ML prediction
    // High hireability suggests upward trajectory
    let mlDirection: 'upward' | 'lateral' | 'downward';
    if (mlPrediction.hireability > 0.7) {
      mlDirection = 'upward';
    } else if (mlPrediction.hireability > 0.4) {
      mlDirection = 'lateral';
    } else {
      mlDirection = 'downward';
    }

    // Infer velocity from tenure prediction
    // Shorter predicted tenure suggests faster progression
    const avgTenure = (mlPrediction.tenureMonths.min + mlPrediction.tenureMonths.max) / 2;
    let mlVelocity: 'fast' | 'normal' | 'slow';
    if (avgTenure < 24) {
      mlVelocity = 'fast';
    } else if (avgTenure > 48) {
      mlVelocity = 'slow';
    } else {
      mlVelocity = 'normal';
    }

    // Infer type from next role keywords
    const mlType = this.inferTypeFromRole(mlPrediction.nextRole);

    // Calculate agreement
    const agreement = {
      directionMatch: mlDirection === ruleBased.direction,
      velocityMatch: mlVelocity === ruleBased.velocity,
      typeMatch: mlType === ruleBased.type
    };

    // Create shadow comparison
    const comparison: ShadowComparison = {
      candidateId: request.candidateId,
      timestamp: new Date(),
      agreement,
      ruleBased,
      mlBased: {
        nextRole: mlPrediction.nextRole,
        confidence: mlPrediction.nextRoleConfidence,
        tenureMonths: mlPrediction.tenureMonths,
        hireability: mlPrediction.hireability
      },
      inputFeatures: {
        titleSequence: request.titleSequence,
        tenureDurations: request.tenureDurations
      }
    };

    // Log comparison
    this.logger.log(comparison);
  }

  /**
   * Infers trajectory type from next role prediction using keyword matching.
   *
   * @param nextRole - Predicted next role
   * @returns Trajectory type
   */
  private inferTypeFromRole(nextRole: string): 'technical_growth' | 'leadership_track' | 'lateral_move' | 'career_pivot' {
    const lower = nextRole.toLowerCase();

    // Leadership indicators
    if (/\b(manager|director|vp|vice president|cto|ceo|coo|head of)\b/i.test(lower)) {
      return 'leadership_track';
    }

    // Technical growth indicators (senior IC roles)
    if (/\b(staff|principal|distinguished|fellow|architect)\b/i.test(lower)) {
      return 'technical_growth';
    }

    // Career pivot indicators (function changes)
    // This is harder to infer from a single role, so we use specific keywords
    if (/\b(transition|pivot|switch|change)\b/i.test(lower)) {
      return 'career_pivot';
    }

    // Default to lateral move if no clear indicators
    return 'lateral_move';
  }

  /**
   * Gets current shadow mode statistics.
   *
   * @returns Shadow statistics
   */
  getStats(): ShadowStats {
    return this.logger.getStats();
  }

  /**
   * Gets recent comparisons for debugging.
   *
   * @param limit - Number of recent comparisons to return
   * @returns Recent comparisons
   */
  getRecent(limit?: number): ShadowComparison[] {
    return this.logger.getRecent(limit);
  }

  /**
   * Disposes shadow mode: flushes logs and cleans up.
   */
  async dispose(): Promise<void> {
    await this.logger.dispose();
  }
}
