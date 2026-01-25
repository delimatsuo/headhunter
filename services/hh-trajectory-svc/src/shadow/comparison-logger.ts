/**
 * Comparison Logger for Shadow Mode
 *
 * Batches side-by-side comparisons of ML vs rule-based predictions for validation.
 */

import type { RuleBasedMetrics } from './rule-based-bridge.js';

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * Shadow comparison entry tracking ML vs rule-based agreement.
 */
export interface ShadowComparison {
  /** Candidate identifier */
  candidateId: string;
  /** Timestamp of prediction */
  timestamp: Date;
  /** Agreement metrics */
  agreement: {
    directionMatch: boolean;
    velocityMatch: boolean;
    typeMatch: boolean;
  };
  /** Rule-based prediction from Phase 8 trajectory calculators */
  ruleBased: RuleBasedMetrics;
  /** ML prediction from ONNX model */
  mlBased: {
    nextRole: string;
    confidence: number;
    tenureMonths: {
      min: number;
      max: number;
    };
    hireability: number;
  };
  /** Input features for debugging */
  inputFeatures: {
    titleSequence: string[];
    tenureDurations?: number[];
  };
}

/**
 * Configuration for ComparisonLogger.
 */
export interface ComparisonLoggerConfig {
  /** Batch size before triggering flush (default: 100) */
  batchSize?: number;
  /** Auto-flush interval in milliseconds (optional) */
  flushIntervalMs?: number;
  /** Storage backend type */
  storageType: 'postgres' | 'bigquery' | 'memory';
}

/**
 * Statistics summary for shadow mode validation.
 */
export interface ShadowStats {
  /** Direction agreement percentage (0-1) */
  directionAgreement: number;
  /** Velocity agreement percentage (0-1) */
  velocityAgreement: number;
  /** Type agreement percentage (0-1) */
  typeAgreement: number;
  /** Total number of comparisons logged */
  totalComparisons: number;
}

// ============================================================================
// Comparison Logger Class
// ============================================================================

/**
 * Logger that batches shadow comparisons and flushes to storage.
 */
export default class ComparisonLogger {
  private logs: ShadowComparison[] = [];
  private batchSize: number;
  private storageType: 'postgres' | 'bigquery' | 'memory';
  private flushInterval: NodeJS.Timeout | null = null;

  constructor(config: ComparisonLoggerConfig) {
    this.batchSize = config.batchSize ?? 100;
    this.storageType = config.storageType;

    // Start auto-flush if interval specified
    if (config.flushIntervalMs) {
      this.startAutoFlush(config.flushIntervalMs);
    }
  }

  /**
   * Logs a shadow comparison. Triggers flush when batch size reached.
   *
   * @param comparison - Shadow comparison to log
   */
  log(comparison: ShadowComparison): void {
    this.logs.push(comparison);

    // Trigger flush if batch size reached
    if (this.logs.length >= this.batchSize) {
      // Fire-and-forget async flush
      void this.flush();
    }
  }

  /**
   * Flushes all pending logs to storage.
   */
  async flush(): Promise<void> {
    if (this.logs.length === 0) {
      return; // Nothing to flush
    }

    const logsToFlush = [...this.logs];

    if (this.storageType === 'postgres') {
      await this.flushToPostgres(logsToFlush);
      // Clear logs after successful flush
      this.logs = this.logs.slice(logsToFlush.length);
    } else if (this.storageType === 'bigquery') {
      await this.flushToBigQuery(logsToFlush);
      // Clear logs after successful flush
      this.logs = this.logs.slice(logsToFlush.length);
    } else if (this.storageType === 'memory') {
      // Keep in memory for testing - don't clear
      // (logs stay in array for getStats())
    }
  }

  /**
   * Flushes logs to PostgreSQL shadow_predictions table.
   *
   * @param logs - Logs to flush
   */
  private async flushToPostgres(logs: ShadowComparison[]): Promise<void> {
    // TODO: Implement PostgreSQL batch insert
    // INSERT INTO shadow_predictions (
    //   candidate_id, timestamp, direction_match, velocity_match, type_match,
    //   rule_based, ml_based, input_features
    // ) VALUES ...
    console.log(`[ComparisonLogger] Would flush ${logs.length} logs to PostgreSQL`);
  }

  /**
   * Flushes logs to BigQuery via streaming insert.
   *
   * @param logs - Logs to flush
   */
  private async flushToBigQuery(logs: ShadowComparison[]): Promise<void> {
    // TODO: Implement BigQuery streaming insert
    // const bigquery = new BigQuery();
    // await bigquery.dataset('shadow_mode').table('predictions').insert(logs);
    console.log(`[ComparisonLogger] Would flush ${logs.length} logs to BigQuery`);
  }

  /**
   * Calculates agreement statistics from in-memory logs.
   *
   * @returns Statistics summary
   */
  getStats(): ShadowStats {
    if (this.logs.length === 0) {
      return {
        directionAgreement: 0,
        velocityAgreement: 0,
        typeAgreement: 0,
        totalComparisons: 0
      };
    }

    const directionMatches = this.logs.filter(log => log.agreement.directionMatch).length;
    const velocityMatches = this.logs.filter(log => log.agreement.velocityMatch).length;
    const typeMatches = this.logs.filter(log => log.agreement.typeMatch).length;
    const total = this.logs.length;

    return {
      directionAgreement: directionMatches / total,
      velocityAgreement: velocityMatches / total,
      typeAgreement: typeMatches / total,
      totalComparisons: total
    };
  }

  /**
   * Returns the most recent N comparisons for debugging.
   *
   * @param limit - Number of recent comparisons to return (default: 10)
   * @returns Recent comparisons
   */
  getRecent(limit: number = 10): ShadowComparison[] {
    return this.logs.slice(-limit);
  }

  /**
   * Starts auto-flush interval.
   *
   * @param intervalMs - Flush interval in milliseconds
   */
  startAutoFlush(intervalMs: number): void {
    if (this.flushInterval) {
      clearInterval(this.flushInterval);
    }

    this.flushInterval = setInterval(() => {
      void this.flush();
    }, intervalMs);
  }

  /**
   * Stops auto-flush interval.
   */
  stopAutoFlush(): void {
    if (this.flushInterval) {
      clearInterval(this.flushInterval);
      this.flushInterval = null;
    }
  }

  /**
   * Disposes logger: flushes remaining logs and stops auto-flush.
   */
  async dispose(): Promise<void> {
    this.stopAutoFlush();
    await this.flush();
  }
}
