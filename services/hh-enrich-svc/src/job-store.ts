import { createHash } from 'node:crypto';

import { getLogger } from '@hh/common';
import type { RedisClientType } from 'redis';
import { getRedisClient } from '@hh/common';

import type { EnrichServiceConfig } from './config';
import type { EnrichmentJobRecord, EnrichmentJobResult } from './types';

const METRICS_STATUS_KEY = 'status';
const METRICS_QUEUE_KEY = 'queue_depth_samples';

export class EnrichmentJobStore {
  private readonly logger = getLogger({ module: 'enrich-job-store' });

  constructor(private readonly config: EnrichServiceConfig) {}

  private jobKey(jobId: string): string {
    return `${this.config.queue.resultKeyPrefix}${jobId}`;
  }

  private dedupeKey(tenantId: string, source: string): string {
    const hash = createHash('sha1').update(source).digest('hex');
    return `${this.config.queue.dedupeKeyPrefix}${tenantId}:${hash}`;
  }

  private metricsKey(): string {
    return `${this.config.queue.resultKeyPrefix}metrics`;
  }

  private statusMetricsKey(): string {
    return `${this.metricsKey()}:${METRICS_STATUS_KEY}`;
  }

  async createJob(
    redis: RedisClientType,
    {
      tenantId,
      candidateId,
      candidateDocumentId,
      requestId,
      force,
      payload,
      correlationId
    }: {
      tenantId: string;
      candidateId: string;
      candidateDocumentId: string;
      requestId: string;
      force: boolean;
      payload?: Record<string, unknown>;
      correlationId: string;
    }
  ): Promise<{ job: EnrichmentJobRecord; created: boolean }> {
    const sourcePayload = JSON.stringify({ candidateId, payload });
    const dedupeKey = this.dedupeKey(tenantId, sourcePayload);

    if (!force) {
      const existingJobId = await redis.get(dedupeKey);
      if (existingJobId) {
        const existing = await redis.hGetAll(this.jobKey(existingJobId));
        if (existing && existing.status && existing.tenantId === tenantId) {
          const job = this.deserialize(existing as Record<string, string>);
          this.logger.debug(
            { jobId: job.jobId, tenantId, candidateId, correlationId },
            'Returning existing enrichment job from dedupe cache.'
          );
          await this.incrementDedupeMetric(redis, tenantId);
          return { job, created: false };
        }
      }
    }

    const jobId = createHash('sha1')
      .update(`${tenantId}:${candidateId}:${Date.now()}:${Math.random()}`)
      .digest('hex');

    const now = new Date().toISOString();
    const priority = force ? 1 : 5;
    const record: EnrichmentJobRecord = {
      jobId,
      tenantId,
      candidateId,
      candidateDocumentId,
      dedupeKey,
      status: 'queued',
      createdAt: now,
      updatedAt: now,
      correlationId,
      priority,
      attemptCount: 0
    };

    await redis.hSet(this.jobKey(jobId), this.serialize(record));
    await redis.expire(this.jobKey(jobId), this.config.queue.jobTtlSeconds);
    await redis.set(dedupeKey, jobId, { EX: this.config.queue.dedupeTtlSeconds });
    await this.incrementStatusMetric(redis, 'queued');

    this.logger.info(
      {
        jobId,
        tenantId,
        candidateId,
        correlationId,
        priority,
        requestId
      },
      'Created enrichment job.'
    );
    return { job: record, created: true };
  }

  async getJob(redis: RedisClientType, jobId: string): Promise<EnrichmentJobRecord | null> {
    const data = await redis.hGetAll(this.jobKey(jobId));
    if (!data || Object.keys(data).length === 0) {
      return null;
    }
    return this.deserialize(data as Record<string, string>);
  }

  async updateStatus(
    redis: RedisClientType,
    jobId: string,
    status: EnrichmentJobRecord['status'],
    patch?: Partial<Pick<EnrichmentJobRecord, 'error' | 'result' | 'updatedAt'>>
  ): Promise<void> {
    const key = this.jobKey(jobId);
    const now = new Date().toISOString();
    const previousStatus = await redis.hGet(key, 'status');
    const update: Record<string, string> = {
      status,
      updatedAt: patch?.updatedAt ?? now,
      ...(patch?.result ? { result: JSON.stringify(patch.result) } : {})
    };

    if (patch && 'error' in patch) {
      if (patch.error && patch.error.length > 0) {
        update.error = patch.error;
      } else {
        await redis.hDel(key, 'error');
      }
    }

    await redis.hSet(key, update);

    if (previousStatus && previousStatus !== status) {
      await this.decrementStatusMetric(redis, previousStatus as EnrichmentJobRecord['status']);
    }
    await this.incrementStatusMetric(redis, status);

    const job = await redis.hGetAll(key);
    if (job && Object.keys(job).length > 0) {
      const parsed = this.deserialize(job as Record<string, string>);
      this.logger.info(
        {
          jobId,
          tenantId: parsed.tenantId,
          status,
          previousStatus,
          correlationId: parsed.correlationId,
          error: patch?.error,
          resultSummary: patch?.result ? this.extractResultSummary(patch.result) : undefined
        },
        'Updated enrichment job status.'
      );
    }
  }

  async pushQueue(redis: RedisClientType, jobId: string, correlationId?: string): Promise<void> {
    await redis.lPush(this.config.queue.queueKey, jobId);
    const depth = await redis.lLen(this.config.queue.queueKey);
    await redis.hSet(this.metricsKey(), METRICS_QUEUE_KEY, depth.toString());
    this.logger.debug({ jobId, queueDepth: depth, correlationId }, 'Queued enrichment job.');
  }

  private serialize(record: EnrichmentJobRecord): Record<string, string> {
    const base: Record<string, string> = {
      jobId: record.jobId,
      tenantId: record.tenantId,
      candidateId: record.candidateId,
      candidateDocumentId: record.candidateDocumentId,
      status: record.status,
      createdAt: record.createdAt,
      updatedAt: record.updatedAt,
      dedupeKey: record.dedupeKey,
      correlationId: record.correlationId ?? '',
      priority: record.priority?.toString() ?? '5',
      attemptCount: record.attemptCount?.toString() ?? '0'
    };
    if (record.error) {
      base.error = record.error;
    }
    if (record.result) {
      base.result = JSON.stringify(record.result);
    }
    return base;
  }

  private deserialize(hash: Record<string, string>): EnrichmentJobRecord {
    const result = hash.result ? (JSON.parse(hash.result) as EnrichmentJobResult) : undefined;

    return {
      jobId: hash.jobId,
      tenantId: hash.tenantId,
      candidateId: hash.candidateId,
      candidateDocumentId: hash.candidateDocumentId,
      status: hash.status as EnrichmentJobRecord['status'],
      createdAt: hash.createdAt,
      updatedAt: hash.updatedAt,
      dedupeKey: hash.dedupeKey,
      error: hash.error,
      result,
      correlationId: hash.correlationId || undefined,
      priority: hash.priority ? Number(hash.priority) : undefined,
      attemptCount: hash.attemptCount ? Number(hash.attemptCount) : undefined
    } satisfies EnrichmentJobRecord;
  }

  async getRedis(): Promise<RedisClientType> {
    try {
      const client = await getRedisClient();
      return client;
    } catch (error) {
      this.logger.error({ error }, 'Failed to acquire Redis client.');
      throw error;
    }
  }

  async incrementAttempt(redis: RedisClientType, jobId: string): Promise<number> {
    const key = this.jobKey(jobId);
    const value = await redis.hIncrBy(key, 'attemptCount', 1);
    return value;
  }

  async getQueueDepth(redis: RedisClientType): Promise<number> {
    return redis.lLen(this.config.queue.queueKey);
  }

  async getStatusCounts(redis: RedisClientType): Promise<Record<string, number>> {
    const raw = await redis.hGetAll(this.statusMetricsKey());
    const counts: Record<string, number> = {};
    for (const [key, value] of Object.entries(raw)) {
      counts[key] = Number(value);
    }
    return counts;
  }

  private async incrementStatusMetric(redis: RedisClientType, status: EnrichmentJobRecord['status']): Promise<void> {
    await redis.hIncrBy(this.statusMetricsKey(), status, 1);
  }

  private async decrementStatusMetric(redis: RedisClientType, status: EnrichmentJobRecord['status']): Promise<void> {
    await redis.hIncrBy(this.statusMetricsKey(), status, -1);
  }

  private async incrementDedupeMetric(redis: RedisClientType, tenantId: string): Promise<void> {
    const key = `${this.metricsKey()}:dedupe`;
    await redis.hIncrBy(key, tenantId, 1);
  }

  private extractResultSummary(result: EnrichmentJobResult): Record<string, unknown> {
    return {
      processingTimeSeconds: result.processingTimeSeconds,
      embeddingUpserted: result.embeddingUpserted,
      modelVersion: result.modelVersion,
      promptVersion: result.promptVersion
    };
  }
}
