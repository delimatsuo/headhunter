import { createHash } from 'node:crypto';

import type { Logger } from 'pino';

import { getLogger } from '@hh/common';

import type { EnrichServiceConfig } from './config';
import { EnrichmentJobStore } from './job-store';
import { MetricsExporter } from './metrics-exporter';
import type { EnrichProfileRequest, EnrichmentContext, EnrichmentJobRecord } from './types';

export class EnrichmentService {
  private readonly logger = getLogger({ module: 'enrich-service' });
  private readonly metricsLogger: Logger = this.logger.child({ component: 'metrics' });
  private readonly tenantMetrics = new Map<string, { submissions: number; dedupeHits: number; forced: number }>();
  private submissions = 0;
  private dedupeHits = 0;
  private readonly healthState = {
    redis: true,
    python: true,
    embed: true,
    lastUpdated: new Date(0).toISOString()
  };

  constructor(
    private readonly config: EnrichServiceConfig,
    private readonly jobStore: EnrichmentJobStore,
    private readonly metricsExporter?: MetricsExporter
  ) {}

  async submitJob(
    context: EnrichmentContext,
    payload: EnrichProfileRequest
  ): Promise<{ job: EnrichmentJobRecord; created: boolean }> {
    const correlationId = `${context.tenant.id}:${context.requestId}`;
    const startedAt = Date.now();

    try {
      const redis = await this.jobStore.getRedis();
      this.markRedisHealth(true);

      const candidateDocumentId = `${context.tenant.id}_${payload.candidateId}`;

      const { job, created } = await this.jobStore.createJob(redis, {
        tenantId: context.tenant.id,
        candidateId: payload.candidateId,
        candidateDocumentId,
        requestId: context.requestId,
        force: payload.force ?? false,
        payload: payload.payload,
        correlationId
      });

      if (created) {
        await this.jobStore.pushQueue(redis, job.jobId, correlationId);
        this.trackSubmission(context.tenant.id, !!payload.force);
      } else {
        this.trackDedupe(context.tenant.id);
      }
      this.metricsExporter?.recordTenantJobCount(context.tenant.id, created);

      const queueDepth = await this.jobStore.getQueueDepth(redis);
      this.metricsExporter?.recordQueueDepth(queueDepth);

      this.emitMetric('job_submission', {
        jobId: job.jobId,
        tenantId: job.tenantId,
        requestId: context.requestId,
        created,
        queueDepth,
        durationMs: Date.now() - startedAt,
        forced: payload.force ?? false
      });

      return { job, created };
    } catch (error) {
      this.logger.error({ error, requestId: context.requestId, tenantId: context.tenant.id }, 'Failed to submit enrichment job.');
      this.markRedisHealth(false);
      throw error;
    }
  }

  async getStatus(jobId: string): Promise<EnrichmentJobRecord | null> {
    const started = Date.now();
    try {
      const redis = await this.jobStore.getRedis();
      this.markRedisHealth(true);
      const job = await this.jobStore.getJob(redis, jobId);
      this.emitMetric('job_status_lookup', {
        jobId,
        found: Boolean(job),
        status: job?.status,
        durationMs: Date.now() - started
      });
      return job;
    } catch (error) {
      this.logger.error({ error, jobId }, 'Failed to load job status.');
      this.markRedisHealth(false);
      throw error;
    }
  }

  buildIdempotencyKey(context: EnrichmentContext, body: EnrichProfileRequest): string {
    if (body.idempotencyKey) {
      return body.idempotencyKey;
    }
    const hash = createHash('sha1')
      .update(context.tenant.id)
      .update(':')
      .update(body.candidateId)
      .digest('hex');
    return hash;
  }

  async waitForCompletion(jobId: string, timeoutMs: number): Promise<EnrichmentJobRecord | null> {
    const redis = await this.jobStore.getRedis();
    const started = Date.now();
    try {
      while (Date.now() - started < timeoutMs) {
        const record = await this.jobStore.getJob(redis, jobId);
        if (!record) {
          this.emitMetric('job_wait_timeout', { jobId, timeoutMs, outcome: 'missing' });
          return null;
        }
        if (record.status === 'completed' || record.status === 'failed') {
          this.emitMetric('job_wait_complete', {
            jobId,
            status: record.status,
            durationMs: Date.now() - started
          });
          return record;
        }
        await new Promise((resolve) => setTimeout(resolve, 500));
      }

      const finalRecord = await this.jobStore.getJob(redis, jobId);
      this.emitMetric('job_wait_timeout', {
        jobId,
        timeoutMs,
        outcome: finalRecord ? finalRecord.status : 'missing'
      });
      return finalRecord;
    } catch (error) {
      this.logger.error({ error, jobId }, 'Error while waiting for job completion.');
      this.markRedisHealth(false);
      throw error;
    }
  }

  async logOperationalSnapshot(): Promise<void> {
    try {
      const redis = await this.jobStore.getRedis();
      this.markRedisHealth(true);
      const queueDepth = await this.jobStore.getQueueDepth(redis);
      const statusCounts = await this.jobStore.getStatusCounts(redis);
      this.metricsExporter?.recordQueueDepth(queueDepth);
      this.emitMetric('operational_snapshot', {
        queueDepth,
        statusCounts,
        health: this.healthState
      });
    } catch (error) {
      this.logger.error({ error }, 'Failed to emit operational snapshot.');
      this.markRedisHealth(false);
    }
  }

  markPythonHealth(healthy: boolean): void {
    if (this.healthState.python !== healthy) {
      this.healthState.python = healthy;
      this.healthState.lastUpdated = new Date().toISOString();
      this.emitMetric('health.python', { healthy });
    }
  }

  markEmbedHealth(healthy: boolean): void {
    if (this.healthState.embed !== healthy) {
      this.healthState.embed = healthy;
      this.healthState.lastUpdated = new Date().toISOString();
      this.emitMetric('health.embed', { healthy });
    }
  }

  private markRedisHealth(healthy: boolean): void {
    if (this.healthState.redis !== healthy) {
      this.healthState.redis = healthy;
      this.healthState.lastUpdated = new Date().toISOString();
      this.emitMetric('health.redis', { healthy });
    }
  }

  private trackSubmission(tenantId: string, forced: boolean): void {
    this.submissions += 1;
    const entry = this.getTenantMetric(tenantId);
    entry.submissions += 1;
    if (forced) {
      entry.forced += 1;
    }
    this.emitMetric('tenant.submission', {
      tenantId,
      total: entry.submissions,
      forcedTotal: entry.forced,
      globalTotal: this.submissions
    });
  }

  private trackDedupe(tenantId: string): void {
    this.dedupeHits += 1;
    const entry = this.getTenantMetric(tenantId);
    entry.dedupeHits += 1;
    this.emitMetric('tenant.dedupe', {
      tenantId,
      tenantDedupeCount: entry.dedupeHits,
      globalDedupeCount: this.dedupeHits
    });
  }

  private getTenantMetric(tenantId: string): { submissions: number; dedupeHits: number; forced: number } {
    let entry = this.tenantMetrics.get(tenantId);
    if (!entry) {
      entry = { submissions: 0, dedupeHits: 0, forced: 0 };
      this.tenantMetrics.set(tenantId, entry);
    }
    return entry;
  }

  private emitMetric(metric: string, details: Record<string, unknown>): void {
    this.metricsLogger.info(
      {
        metric,
        modelVersion: this.config.versioning.modelVersion,
        promptVersion: this.config.versioning.promptVersion,
        ...details
      },
      'enrichment metric'
    );
  }
}
