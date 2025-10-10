import { spawn } from 'node:child_process';
import { performance } from 'node:perf_hooks';
import { setTimeout as delay } from 'node:timers/promises';
import type { Logger } from 'pino';
import { getLogger } from '@hh/common';
import type { Redis } from 'ioredis';

import type { EnrichServiceConfig } from './config';
import { EnrichmentJobStore } from './job-store';
import type { EnrichmentJobRecord, EnrichmentJobResult } from './types';
import { EmbeddingClient } from './embedding-client';
import { EnrichmentService } from './enrichment-service';
import { MetricsExporter, type CircuitState } from './metrics-exporter';

class WorkerError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly retryable: boolean,
    options?: { cause?: unknown }
  ) {
    super(message, options);
    this.name = 'WorkerError';
  }
}

class CircuitBreaker {
  private state: CircuitState = 'closed';
  private failures = 0;
  private nextAttemptAt = 0;

  constructor(
    private readonly name: string,
    private readonly threshold: number,
    private readonly cooldownMs: number,
    private readonly logger: Logger,
    private readonly onStateChange?: (state: CircuitState) => void
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
    if (this.state !== 'closed' || this.failures !== 0) {
      this.failures = 0;
      this.transition('closed');
    }
  }

  recordFailure(): void {
    this.failures += 1;
    if (this.failures >= this.threshold) {
      this.nextAttemptAt = Date.now() + this.cooldownMs;
      this.transition('open');
      this.logger.warn({ name: this.name, cooldownMs: this.cooldownMs }, 'Circuit breaker opened.');
    } else if (this.state === 'half-open') {
      this.nextAttemptAt = Date.now() + this.cooldownMs;
      this.transition('open');
    }
  }

  stateName(): CircuitState {
    return this.state;
  }

  private transition(state: CircuitState): void {
    if (this.state !== state) {
      this.state = state;
      this.onStateChange?.(state);
      this.logger.debug({ name: this.name, state }, 'Circuit breaker state changed.');
    }
  }
}

interface RetryOptions<T> {
  component: string;
  limit: number;
  baseDelay: number;
  maxDelay: number;
  breaker?: CircuitBreaker;
  operation: (attempt: number) => Promise<T>;
  onRetry?: (attempt: number, error: WorkerError, delayMs: number) => void;
  onFinalFailure?: (error: WorkerError) => void;
}

interface PythonJobResult {
  payload: Record<string, any>;
  durationMs: number;
  attemptCount: number;
}

export class EnrichmentWorker {
  private readonly logger = getLogger({ module: 'enrich-worker' });
  private readonly metricsLogger = this.logger.child({ component: 'worker-metrics' });
  private readonly embeddingClient: EmbeddingClient;
  private running = false;
  private queueClient: Redis | null = null;
  private readonly completionSamples: number[] = [];
  private readonly pythonBreaker: CircuitBreaker;
  private activeJobs = 0;
  private succeeded = 0;
  private failed = 0;

  constructor(
    private readonly config: EnrichServiceConfig,
    private readonly store: EnrichmentJobStore,
    private readonly service: EnrichmentService,
    private readonly metricsExporter?: MetricsExporter
  ) {
    this.pythonBreaker = new CircuitBreaker(
      'python-subprocess',
      config.queue.circuitBreakerFailures,
      config.queue.circuitBreakerCooldownMs,
      this.logger.child({ component: 'python-circuit' }),
      (state) => this.service.markPythonHealth(state !== 'open')
    );
    this.embeddingClient = new EmbeddingClient(
      config,
      (healthy, _state) => {
        this.service.markEmbedHealth(healthy);
      },
      this.metricsExporter
    );
  }

  async start(): Promise<void> {
    if (this.running) {
      return;
    }

    const baseClient = await this.store.getRedis();
    this.queueClient = baseClient.duplicate();
    await this.queueClient.connect();

    this.running = true;
    for (let i = 0; i < this.config.queue.maxConcurrency; i += 1) {
      void this.loop();
    }

    this.logger.info({ concurrency: this.config.queue.maxConcurrency }, 'Enrichment worker started.');
  }

  async stop(): Promise<void> {
    this.running = false;
    if (this.queueClient) {
      await this.queueClient.quit();
      this.queueClient = null;
    }
  }

  private async loop(): Promise<void> {
    if (!this.queueClient) {
      return;
    }

    while (this.running) {
      try {
        const timeoutSeconds = Math.max(1, Math.round(this.config.queue.pollIntervalMs / 1000));
        const res = await this.queueClient.brpop(this.config.queue.queueKey, timeoutSeconds);
        if (!res) {
          continue;
        }
        const jobId = res[1];  // brpop returns [key, value]
        await this.processJob(jobId);
      } catch (error) {
        this.logger.error({ error }, 'Worker loop encountered an error.');
        await delay(1000);
      }
    }
  }

  private async processJob(jobId: string): Promise<void> {
    const redis = await this.store.getRedis();
    const record = await this.store.getJob(redis, jobId);
    if (!record) {
      this.logger.warn({ jobId }, 'Job not found when attempting to process.');
      return;
    }

    const jobLogger = this.logger.child({
      jobId,
      tenantId: record.tenantId,
      correlationId: record.correlationId
    });

    if (record.status !== 'queued') {
      jobLogger.info({ status: record.status }, 'Skipping job because it is not queued.');
      return;
    }

    this.activeJobs += 1;
    const queueDurationMs = Math.max(0, Date.now() - new Date(record.createdAt).getTime());
    const phaseDurations: Record<string, number> = { queue: queueDurationMs };
    const startedAt = performance.now();

    await this.store.updateStatus(redis, jobId, 'processing');

    try {
      jobLogger.info({ queueDurationMs }, 'Processing enrichment job.');

      const pythonResult = await this.runPythonWithRetries(redis, record, jobLogger);
      phaseDurations.python = pythonResult.durationMs;

      const candidateSnapshot = pythonResult.payload.candidate ?? {};

      const embedMetrics = await this.embeddingClient.upsertEmbedding(record, candidateSnapshot, jobLogger);
      phaseDurations.embed = embedMetrics.durationMs;

      const totalDurationMs = performance.now() - startedAt;
      phaseDurations.total = totalDurationMs;

      const jobResult: EnrichmentJobResult = {
        processingTimeSeconds:
          pythonResult.payload.processing_time_seconds ?? pythonResult.payload.processingTimeSeconds ?? totalDurationMs / 1000,
        candidateSnapshot,
        embeddingUpserted: embedMetrics.skipped ? false : embedMetrics.success,
        embeddingSkippedReason: embedMetrics.skipped ? embedMetrics.skipReason : undefined,
        modelVersion: this.config.versioning.modelVersion,
        promptVersion: this.config.versioning.promptVersion,
        phaseDurationsMs: phaseDurations,
        attempts: pythonResult.attemptCount,
        queueDurationMs
      } satisfies EnrichmentJobResult;

      await this.store.updateStatus(redis, jobId, 'completed', {
        result: jobResult
      });

      this.succeeded += 1;
      const percentiles = this.recordCompletion(totalDurationMs);
      this.metricsExporter?.recordJobCompletion(record.tenantId);
      this.metricsExporter?.recordLatencyPercentile('p50', percentiles.p50);
      this.metricsExporter?.recordLatencyPercentile('p95', percentiles.p95);
      this.metricsExporter?.recordLatencyPercentile('p99', percentiles.p99);
      jobLogger.info(
        {
          totalDurationMs,
          phaseDurations,
          attempts: pythonResult.attemptCount,
          embeddingAttempts: embedMetrics.attempts,
          percentiles
        },
        'Enrichment job completed.'
      );

      this.publishWorkerMetrics(percentiles);
    } catch (error) {
      const workerError = error instanceof WorkerError ? error : new WorkerError('job_failure', this.extractErrorMessage(error), false, { cause: error });
      await this.store.updateStatus(redis, jobId, 'failed', { error: workerError.message });
      this.failed += 1;
      this.metricsExporter?.recordJobFailure(record.tenantId);
      jobLogger.error(
        {
          error: workerError.message,
          code: workerError.code,
          retryable: workerError.retryable,
          phaseDurations
        },
        'Enrichment job failed.'
      );
      this.publishWorkerMetrics();
    } finally {
      this.activeJobs = Math.max(0, this.activeJobs - 1);
    }
  }

  private async runPythonWithRetries(
    redis: Redis,
    record: EnrichmentJobRecord,
    jobLogger: Logger
  ): Promise<PythonJobResult> {
    return this.withRetries<PythonJobResult>({
      component: 'python',
      limit: this.config.queue.retryLimit,
      baseDelay: this.config.queue.retryBaseDelayMs,
      maxDelay: this.config.queue.retryMaxDelayMs,
      breaker: this.pythonBreaker,
      operation: async (attempt) => {
        const attemptCount = await this.store.incrementAttempt(redis, record.jobId);
        const pythonStart = performance.now();
        const payload = await this.invokePython(record, attempt, jobLogger);
        const durationMs = performance.now() - pythonStart;
        this.service.markPythonHealth(true);
        return { payload, durationMs, attemptCount } satisfies PythonJobResult;
      },
      onRetry: (attempt, error, delayMs) => {
        jobLogger.warn(
          {
            attempt,
            delayMs,
            code: error.code,
            retryable: error.retryable,
            breakerState: this.pythonBreaker.stateName()
          },
          'Python processor attempt failed. Retrying.'
        );
        this.service.markPythonHealth(false);
      },
      onFinalFailure: (error) => {
        jobLogger.error({ code: error.code, retryable: error.retryable }, 'Python processor failed permanently.');
      }
    });
  }

  private async invokePython(record: EnrichmentJobRecord, attempt: number, _jobLogger: Logger): Promise<Record<string, any>> {
    if (!this.pythonBreaker.canExecute()) {
      throw new WorkerError('python_circuit_open', 'Python processor circuit breaker is open.', false);
    }

    const args = [this.config.queue.pythonScript, '--candidate-id', record.candidateDocumentId, '--json'];
    if (process.env.ENRICH_TESTING === 'true') {
      args.push('--testing');
    }

    return new Promise((resolve, reject) => {
      const child = spawn(this.config.queue.pythonExecutable, args, {
        env: {
          ...process.env,
          ENRICH_JOB_ID: record.jobId,
          ENRICH_JOB_ATTEMPT: String(attempt + 1),
          GOOGLE_CLOUD_PROJECT: process.env.GOOGLE_CLOUD_PROJECT ?? 'headhunter-local'
        }
      });

      let stdout = '';
      let stderr = '';

      child.stdout?.on('data', (chunk) => {
        stdout += chunk.toString();
      });

      child.stderr?.on('data', (chunk) => {
        stderr += chunk.toString();
      });

      child.on('error', (error) => {
        reject(this.normalizePythonError(error));
      });

      child.on('close', (code) => {
        if (code !== 0) {
          const message = stderr.trim() || `Python exited with code ${code}`;
          reject(this.normalizePythonError(new Error(message)));
          return;
        }
        try {
          const parsed = JSON.parse(stdout.trim());
          resolve(parsed as Record<string, any>);
        } catch (error) {
          reject(new WorkerError('python_output_parse', `Failed to parse python output: ${(error as Error).message}`, false, { cause: error }));
        }
      });

      const killTimer = setTimeout(() => {
        child.kill('SIGKILL');
        reject(new WorkerError('python_timeout', 'Python processor timed out.', true));
      }, this.config.queue.jobTimeoutMs);

      child.on('exit', () => {
        clearTimeout(killTimer);
      });
    });
  }

  private normalizePythonError(error: unknown): WorkerError {
    if (error instanceof WorkerError) {
      return error;
    }
    const message = this.extractErrorMessage(error);
    const normalized = message.toLowerCase();
    if (normalized.includes('timeout') || normalized.includes('timed out')) {
      return new WorkerError('python_timeout', message, true, { cause: error });
    }
    if (normalized.includes('killed') || normalized.includes('signal')) {
      return new WorkerError('python_signal', message, true, { cause: error });
    }
    if (normalized.includes('parse')) {
      return new WorkerError('python_output_parse', message, false, { cause: error });
    }
    return new WorkerError('python_error', message, true, { cause: error });
  }

  private async withRetries<T>(options: RetryOptions<T>): Promise<T> {
    const limit = Math.max(0, options.limit);
    let attempt = 0;
    let lastError: WorkerError | null = null;

    while (attempt <= limit) {
      if (options.breaker && !options.breaker.canExecute()) {
        throw new WorkerError(`${options.component}_circuit_open`, `${options.component} circuit breaker is open.`, false);
      }

      try {
        const result = await options.operation(attempt);
        options.breaker?.recordSuccess();
        return result;
      } catch (error) {
        const workerError = error instanceof WorkerError ? error : new WorkerError(`${options.component}_failure`, this.extractErrorMessage(error), false, { cause: error });
        lastError = workerError;
        options.breaker?.recordFailure();

        if (!workerError.retryable || attempt === limit) {
          options.onFinalFailure?.(workerError);
          throw workerError;
        }

        const delayMs = this.computeDelay(options.baseDelay, options.maxDelay, attempt);
        options.onRetry?.(attempt, workerError, delayMs);
        attempt += 1;
        await delay(delayMs + this.jitter(Math.min(delayMs, 250)));
      }
    }

    throw lastError ?? new WorkerError(`${options.component}_failure`, 'Unknown failure', false);
  }

  private computeDelay(base: number, max: number, attempt: number): number {
    const expo = base * 2 ** attempt;
    return Math.min(max, expo);
  }

  private jitter(bound: number): number {
    if (bound <= 0) {
      return 0;
    }
    return Math.floor(Math.random() * bound);
  }

  private recordCompletion(durationMs: number): { p50: number; p95: number; p99: number } {
    this.completionSamples.push(durationMs);
    if (this.completionSamples.length > 200) {
      this.completionSamples.shift();
    }
    const sorted = [...this.completionSamples].sort((a, b) => a - b);
    const percentile = (p: number) => {
      if (sorted.length === 0) {
        return 0;
      }
      const index = Math.min(sorted.length - 1, Math.round((p / 100) * (sorted.length - 1)));
      return Number(sorted[index].toFixed(2));
    };
    return {
      p50: percentile(50),
      p95: percentile(95),
      p99: percentile(99)
    };
  }

  private publishWorkerMetrics(percentiles?: { p50: number; p95: number; p99: number }): void {
    const snapshot = {
      activeJobs: this.activeJobs,
      succeeded: this.succeeded,
      failed: this.failed,
      pythonCircuitState: this.pythonBreaker.stateName(),
      percentiles
    };
    this.metricsLogger.info(snapshot, 'worker metrics');
    void this.service
      .logOperationalSnapshot()
      .catch((error) => this.logger.warn({ error }, 'Failed to emit operational snapshot from worker.'));
  }

  private extractErrorMessage(error: unknown): string {
    if (error instanceof Error) {
      return error.message;
    }
    return typeof error === 'string' ? error : JSON.stringify(error);
  }
}
