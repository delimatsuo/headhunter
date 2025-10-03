import { request as httpRequest } from 'node:http';
import { request as httpsRequest } from 'node:https';
import { URL } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
import type { Logger } from 'pino';
import { getIdTokenManager, getLogger } from '@hh/common';

import type { EnrichServiceConfig } from './config';
import type { EnrichmentJobRecord } from './types';
import { MetricsExporter, type CircuitState } from './metrics-exporter';

interface EmbeddingErrorInfo {
  category: string;
  retryable: boolean;
  message: string;
}

export interface EmbeddingOperationMetrics {
  success: boolean;
  durationMs: number;
  attempts: number;
  statusCode?: number;
  errorCategory?: string;
  skipped?: boolean;
  skipReason?: string;
}

class CircuitBreaker {
  private state: CircuitState = 'closed';
  private failures = 0;
  private nextAttemptAt = 0;

  constructor(
    private readonly name: string,
    private readonly threshold: number,
    private readonly resetMs: number,
    private readonly logger: Logger,
    private readonly stateCallback?: (state: CircuitState) => void
  ) {}

  canExecute(): boolean {
    if (this.state === 'open') {
      if (Date.now() >= this.nextAttemptAt) {
        this.transition('half-open');
        return true;
      }
      return false;
    }
    return true;
  }

  recordSuccess(): void {
    this.failures = 0;
    this.transition('closed');
  }

  recordFailure(): void {
    this.failures += 1;
    if (this.failures >= this.threshold) {
      this.nextAttemptAt = Date.now() + this.resetMs;
      this.transition('open');
      this.logger.warn({ name: this.name, resetMs: this.resetMs }, 'Embedding circuit breaker opened.');
    } else if (this.state === 'half-open') {
      this.nextAttemptAt = Date.now() + this.resetMs;
      this.transition('open');
    }
  }

  stateName(): CircuitState {
    return this.state;
  }

  private transition(state: CircuitState): void {
    if (state !== this.state) {
      this.state = state;
      this.stateCallback?.(state);
      this.logger.debug({ name: this.name, state }, 'Embedding circuit breaker state changed.');
    }
  }
}

export class EmbeddingClient {
  private readonly logger = getLogger({ module: 'enrich-embed-client' });
  private readonly breaker: CircuitBreaker;
  private readonly metricsExporter?: MetricsExporter;
  private readonly idTokenAudience?: string;

  constructor(
    private readonly config: EnrichServiceConfig,
    private readonly healthCallback?: (healthy: boolean, state: CircuitState) => void,
    metricsExporter?: MetricsExporter
  ) {
    this.metricsExporter = metricsExporter;
    this.idTokenAudience = config.embed.idTokenAudience;
    this.breaker = new CircuitBreaker(
      'embedding-service',
      config.embed.circuitBreakerFailures,
      config.embed.circuitBreakerResetMs,
      this.logger.child({ component: 'embed-circuit' }),
      (state) => {
        this.healthCallback?.(state !== 'open', state);
        this.metricsExporter?.recordEmbedCircuitState(state);
      }
    );
  }

  async upsertEmbedding(
    job: EnrichmentJobRecord,
    candidate: Record<string, unknown>,
    jobLogger?: Logger
  ): Promise<EmbeddingOperationMetrics> {
    if (!this.config.embed.enabled) {
      const skipReason = 'embedding_disabled';
      const metrics: EmbeddingOperationMetrics = { success: false, durationMs: 0, attempts: 0, skipped: true, skipReason };
      this.metricsExporter?.recordEmbedOutcome({
        tenantId: job.tenantId,
        success: false,
        skipped: true,
        durationMs: 0,
        attempts: 0,
        skippedReason: skipReason
      });
      return metrics;
    }

    const text = typeof candidate?.resume_text === 'string' ? (candidate.resume_text as string) : undefined;
    if (!text || text.trim().length === 0) {
      const message = 'Skipping embedding upsert because resume text is missing.';
      this.logger.warn({ jobId: job.jobId }, message);
      jobLogger?.warn({ jobId: job.jobId }, message);
      const skipReason = 'missing_resume_text';
      const metrics: EmbeddingOperationMetrics = { success: false, durationMs: 0, attempts: 0, skipped: true, skipReason };
      this.metricsExporter?.recordEmbedOutcome({
        tenantId: job.tenantId,
        success: false,
        skipped: true,
        durationMs: 0,
        attempts: 0,
        skippedReason: skipReason
      });
      return metrics;
    }

    if (!this.breaker.canExecute()) {
      const metrics: EmbeddingOperationMetrics = {
        success: false,
        durationMs: 0,
        attempts: 0,
        errorCategory: 'circuit-open'
      };
      this.logger.error({ jobId: job.jobId }, 'Embedding circuit breaker is open. Skipping upsert.');
      jobLogger?.error({ jobId: job.jobId }, 'Embedding circuit breaker is open. Skipping upsert.');
      this.healthCallback?.(false, this.breaker.stateName());
      this.metricsExporter?.recordEmbedOutcome({
        tenantId: job.tenantId,
        success: false,
        skipped: false,
        durationMs: 0,
        attempts: 0
      });
      return metrics;
    }

    const payload = JSON.stringify({
      entityId: `${job.tenantId}:${job.candidateId}`,
      text,
      metadata: {
        source: 'hh-enrich-svc',
        tenantId: job.tenantId,
        modelVersion: this.config.versioning.modelVersion,
        promptVersion: this.config.versioning.promptVersion
      }
    });

    let attempt = 0;
    let lastError: EmbeddingErrorInfo | null = null;
    const start = Date.now();

    while (attempt <= this.config.embed.retryLimit) {
      const attemptStart = Date.now();
      try {
        const response = await this.sendRequest(job, payload);
        const durationMs = Date.now() - attemptStart;
        this.breaker.recordSuccess();
        this.healthCallback?.(true, this.breaker.stateName());

        const metrics: EmbeddingOperationMetrics = {
          success: true,
          durationMs: Date.now() - start,
          attempts: attempt + 1,
          statusCode: response.statusCode
        };

        this.emitMetric('embedding_success', {
          jobId: job.jobId,
          tenantId: job.tenantId,
          statusCode: response.statusCode,
          durationMs,
          attempts: attempt + 1
        });
        this.metricsExporter?.recordEmbedOutcome({
          tenantId: job.tenantId,
          success: true,
          skipped: false,
          durationMs: metrics.durationMs,
          attempts: metrics.attempts
        });
        return metrics;
      } catch (error) {
        const info = this.normalizeError(error);
        lastError = info;
        this.breaker.recordFailure();
        this.healthCallback?.(false, this.breaker.stateName());

        const durationMs = Date.now() - attemptStart;
        const logPayload = {
          jobId: job.jobId,
          tenantId: job.tenantId,
          attempt: attempt + 1,
          category: info.category,
          retryable: info.retryable,
          durationMs,
          breakerState: this.breaker.stateName()
        };

        if (!info.retryable || attempt === this.config.embed.retryLimit) {
          this.logger.error(logPayload, info.message);
          jobLogger?.error(logPayload, info.message);
          break;
        }

        this.logger.warn(logPayload, info.message);
        jobLogger?.warn(logPayload, info.message);
        attempt += 1;
        const delayMs = this.computeDelay(attempt);
        await delay(delayMs);
      }
    }

    const metrics: EmbeddingOperationMetrics = {
      success: false,
      durationMs: Date.now() - start,
      attempts: attempt + 1,
      errorCategory: lastError?.category
    };

    this.emitMetric('embedding_failure', {
      jobId: job.jobId,
      tenantId: job.tenantId,
      category: lastError?.category,
      attempts: metrics.attempts,
      durationMs: metrics.durationMs
    });

    this.metricsExporter?.recordEmbedOutcome({
      tenantId: job.tenantId,
      success: false,
      skipped: false,
      durationMs: metrics.durationMs,
      attempts: metrics.attempts
    });

    return metrics;
  }

  private async sendRequest(job: EnrichmentJobRecord, payload: string): Promise<{ statusCode: number }> {
    const url = new URL('/v1/embeddings/upsert', this.config.embed.baseUrl);
    const isHttps = url.protocol === 'https:';
    const requestImpl = isHttps ? httpsRequest : httpRequest;
    const authHeader = await this.resolveAuthHeader();

    return new Promise((resolve, reject) => {
      const req = requestImpl(
        url,
        {
          method: 'POST',
          timeout: this.config.embed.timeoutMs,
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(payload).toString(),
            [this.config.embed.tenantHeader]: job.tenantId,
            ...(authHeader ? { Authorization: authHeader } : {})
          }
        },
        (res) => {
          const chunks: Buffer[] = [];
          res.on('data', (chunk) => chunks.push(Buffer.from(chunk)));
          res.on('end', () => {
            const status = res.statusCode ?? 0;
            if (status >= 200 && status < 300) {
              resolve({ statusCode: status });
            } else {
              const body = Buffer.concat(chunks).toString('utf8');
              reject(new Error(`Embed service responded with ${status}: ${body}`));
            }
          });
        }
      );

      req.on('error', (error) => {
        reject(error);
      });
      req.on('timeout', () => {
        req.destroy(new Error('Embed request timed out'));
      });

      req.write(payload);
      req.end();
    });
  }

  private normalizeError(error: unknown): EmbeddingErrorInfo {
    const message = error instanceof Error ? error.message : String(error);
    const normalized = message.toLowerCase();

    if (normalized.includes('timed out') || normalized.includes('timeout')) {
      return { category: 'timeout', retryable: true, message } satisfies EmbeddingErrorInfo;
    }
    if (normalized.includes('ecconnrefused') || normalized.includes('econnreset') || normalized.includes('network')) {
      return { category: 'network', retryable: true, message } satisfies EmbeddingErrorInfo;
    }
    if (normalized.includes('5') && normalized.includes('responded')) {
      return { category: 'server', retryable: true, message } satisfies EmbeddingErrorInfo;
    }
    if (normalized.includes('401') || normalized.includes('403')) {
      return { category: 'auth', retryable: false, message } satisfies EmbeddingErrorInfo;
    }
    if (normalized.includes('429')) {
      return { category: 'rate-limit', retryable: true, message } satisfies EmbeddingErrorInfo;
    }
    return { category: 'unknown', retryable: false, message } satisfies EmbeddingErrorInfo;
  }

  private computeDelay(attempt: number): number {
    const base = this.config.embed.retryBaseDelayMs;
    const max = this.config.embed.retryMaxDelayMs;
    const delayMs = Math.min(max, base * 2 ** attempt);
    const jitter = Math.floor(Math.random() * Math.min(delayMs, 250));
    return delayMs + jitter;
  }

  private emitMetric(metric: string, payload: Record<string, unknown>): void {
    this.logger.info({ metric, ...payload }, 'embedding metric');
  }

  private async resolveAuthHeader(): Promise<string | undefined> {
    if (this.config.embed.authToken) {
      return `Bearer ${this.config.embed.authToken}`;
    }

    if (!this.idTokenAudience) {
      return undefined;
    }

    try {
      const token = await getIdTokenManager().getToken(this.idTokenAudience);
      return `Bearer ${token}`;
    } catch (error) {
      this.logger.error({ error }, 'Failed to acquire ID token for embedding service calls.');
      throw error instanceof Error ? error : new Error('Failed to acquire ID token');
    }
  }
}
