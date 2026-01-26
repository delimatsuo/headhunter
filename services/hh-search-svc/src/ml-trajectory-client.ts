/**
 * ML Trajectory Client
 *
 * HTTP client for hh-trajectory-svc to fetch ML-based trajectory predictions.
 * Includes circuit breaker for graceful degradation when service is unavailable.
 *
 * @module ml-trajectory-client
 */

import { getLogger } from '@hh/common';
import type { Logger } from 'pino';

/**
 * ML trajectory prediction result.
 * Matches the PredictResponse structure from hh-trajectory-svc.
 */
export interface MLTrajectoryPrediction {
  /** Predicted next job title/role */
  nextRole: string;
  /** Confidence score for next role prediction (0-1) */
  nextRoleConfidence: number;
  /** Estimated tenure in months (range) */
  tenureMonths: {
    min: number;
    max: number;
  };
  /** Hireability score (0-100) */
  hireability: number;
  /** Flag indicating prediction has low confidence */
  lowConfidence: boolean;
  /** Reason for low confidence (if applicable) */
  uncertaintyReason?: string;
}

/**
 * Request payload for /predict endpoint
 */
export interface MLTrajectoryRequest {
  /** Candidate identifier */
  candidateId: string;
  /** Sequence of job titles in chronological order */
  titleSequence: string[];
  /** Optional: Tenure durations in months for each title */
  tenureDurations?: number[];
}

/**
 * Circuit breaker state tracking
 */
interface CircuitBreakerState {
  failures: number;
  lastFailure: Date | null;
  open: boolean;
}

/**
 * HTTP client for hh-trajectory-svc.
 * Provides trajectory predictions with circuit breaker protection.
 */
export class MLTrajectoryClient {
  private readonly baseUrl: string;
  private readonly timeout: number;
  private readonly enabled: boolean;
  private readonly logger: Logger;
  private readonly circuitBreaker: CircuitBreakerState;
  private resetTimer: NodeJS.Timeout | null = null;

  constructor(config: {
    baseUrl: string;
    timeout?: number;
    enabled?: boolean;
    logger?: Logger;
  }) {
    this.baseUrl = config.baseUrl.endsWith('/') ? config.baseUrl.slice(0, -1) : config.baseUrl;
    this.timeout = config.timeout ?? 100; // 100ms default - must not impact overall latency
    this.enabled = config.enabled ?? true;
    this.logger = (config.logger ?? getLogger({ module: 'ml-trajectory-client' })).child({
      module: 'ml-trajectory-client'
    });
    this.circuitBreaker = {
      failures: 0,
      lastFailure: null,
      open: false
    };
  }

  /**
   * Check if ML trajectory service is available.
   * Returns false if circuit breaker is open or service is disabled.
   */
  isAvailable(): boolean {
    return this.enabled && !this.circuitBreaker.open;
  }

  /**
   * Health check for hh-trajectory-svc.
   * Calls /health endpoint and returns availability status.
   */
  async healthCheck(): Promise<boolean> {
    if (!this.enabled) {
      return false;
    }

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.timeout);

      const response = await fetch(`${this.baseUrl}/health`, {
        method: 'GET',
        signal: controller.signal
      });

      clearTimeout(timeoutId);
      return response.status === 200;
    } catch (error) {
      this.logger.debug({ error }, 'ML trajectory health check failed');
      return false;
    }
  }

  /**
   * Request ML trajectory prediction for a candidate.
   *
   * Graceful degradation:
   * - If circuit breaker open, returns null immediately
   * - If request times out, returns null and logs warning
   * - If service unavailable, opens circuit breaker after 3 failures
   *
   * @param request - Candidate data for prediction
   * @returns Prediction result or null if unavailable
   */
  async predict(request: MLTrajectoryRequest): Promise<MLTrajectoryPrediction | null> {
    if (!this.enabled) {
      this.logger.debug('ML trajectory predictions disabled');
      return null;
    }

    // Circuit breaker check
    if (this.circuitBreaker.open) {
      this.logger.debug(
        { candidateId: request.candidateId, failures: this.circuitBreaker.failures },
        'Circuit breaker open - skipping ML prediction'
      );
      return null;
    }

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.timeout);

      const response = await fetch(`${this.baseUrl}/predict`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(request),
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`ML trajectory service returned ${response.status}`);
      }

      const data: unknown = await response.json();

      // Reset circuit breaker on success
      this.resetCircuitBreaker();

      // Extract prediction from response
      if (
        typeof data === 'object' &&
        data !== null &&
        'prediction' in data &&
        typeof data.prediction === 'object' &&
        data.prediction !== null
      ) {
        return data.prediction as MLTrajectoryPrediction;
      }

      throw new Error('Invalid response format from ML trajectory service');
    } catch (error) {
      // Handle errors gracefully
      if ((error as Error).name === 'AbortError') {
        this.logger.warn(
          { candidateId: request.candidateId, timeout: this.timeout },
          'ML trajectory prediction timeout'
        );
      } else {
        this.logger.warn(
          { error, candidateId: request.candidateId },
          'ML trajectory prediction failed'
        );
      }

      // Increment failure count and potentially open circuit breaker
      this.incrementFailures();

      return null;
    }
  }

  /**
   * Increment circuit breaker failure count.
   * Opens breaker if failures exceed threshold (3).
   */
  private incrementFailures(): void {
    this.circuitBreaker.failures++;
    this.circuitBreaker.lastFailure = new Date();

    if (this.circuitBreaker.failures > 3 && !this.circuitBreaker.open) {
      this.circuitBreaker.open = true;
      this.logger.warn(
        { failures: this.circuitBreaker.failures },
        'Circuit breaker opened - ML trajectory predictions suspended for 30s'
      );

      // Schedule circuit breaker reset after 30 seconds
      this.scheduleCircuitBreakerReset();
    }
  }

  /**
   * Reset circuit breaker state on successful request.
   */
  private resetCircuitBreaker(): void {
    if (this.circuitBreaker.failures > 0 || this.circuitBreaker.open) {
      this.logger.info('Circuit breaker reset - ML trajectory service recovered');
      this.circuitBreaker.failures = 0;
      this.circuitBreaker.lastFailure = null;
      this.circuitBreaker.open = false;

      // Cancel pending reset timer
      if (this.resetTimer) {
        clearTimeout(this.resetTimer);
        this.resetTimer = null;
      }
    }
  }

  /**
   * Schedule circuit breaker reset after cooldown period (30 seconds).
   */
  private scheduleCircuitBreakerReset(): void {
    // Cancel existing timer
    if (this.resetTimer) {
      clearTimeout(this.resetTimer);
    }

    // Schedule new reset
    this.resetTimer = setTimeout(() => {
      this.logger.info('Circuit breaker cooldown complete - attempting recovery');
      this.circuitBreaker.open = false;
      this.circuitBreaker.failures = 0;
      this.resetTimer = null;
    }, 30_000); // 30 seconds
  }

  /**
   * Clean up resources (cancel pending timers).
   */
  dispose(): void {
    if (this.resetTimer) {
      clearTimeout(this.resetTimer);
      this.resetTimer = null;
    }
  }
}
