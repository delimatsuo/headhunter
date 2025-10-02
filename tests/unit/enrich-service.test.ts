import { afterEach, beforeEach, describe, expect, it, jest } from '@jest/globals';

import type { EnrichServiceConfig } from '../../services/hh-enrich-svc/src/config';
import { EnrichmentService } from '../../services/hh-enrich-svc/src/enrichment-service';
import type { EnrichmentContext, EnrichmentJobRecord } from '../../services/hh-enrich-svc/src/types';

const baseConfig: EnrichServiceConfig = {
  base: {} as any,
  queue: {
    queueKey: 'hh:test:queue',
    resultKeyPrefix: 'hh:test:job:',
    dedupeKeyPrefix: 'hh:test:dedupe:',
    maxConcurrency: 2,
    jobTtlSeconds: 3600,
    dedupeTtlSeconds: 3600,
    pythonExecutable: 'python3',
    pythonScript: '/tmp/run.py',
    jobTimeoutMs: 10_000,
    pollIntervalMs: 500,
    retryLimit: 2,
    retryBaseDelayMs: 100,
    retryMaxDelayMs: 2_000,
    circuitBreakerFailures: 3,
    circuitBreakerCooldownMs: 30_000
  },
  embed: {
    enabled: true,
    baseUrl: 'http://localhost:7101',
    timeoutMs: 5_000,
    tenantHeader: 'X-Tenant-ID',
    retryLimit: 2,
    retryBaseDelayMs: 100,
    retryMaxDelayMs: 2_000,
    circuitBreakerFailures: 3,
    circuitBreakerResetMs: 30_000
  },
  versioning: {
    modelVersion: 'unit-test-model',
    promptVersion: 'unit-test-prompt'
  }
};

describe('EnrichmentService', () => {
  const redisStub = {} as any;
  let jobStore: any;
  let service: EnrichmentService;
  const context: EnrichmentContext = {
    tenant: { id: 'tenant-unit' } as any,
    user: undefined,
    requestId: 'req-1234'
  };
  const jobRecord: EnrichmentJobRecord = {
    jobId: 'job-1',
    tenantId: context.tenant.id,
    candidateId: 'cand-1',
    candidateDocumentId: 'tenant-unit_cand-1',
    dedupeKey: 'dedupe-key',
    status: 'queued',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    correlationId: `${context.tenant.id}:${context.requestId}`,
    priority: 5,
    attemptCount: 0
  };

  beforeEach(() => {
    jest.useFakeTimers();
    jest.spyOn(Date, 'now').mockReturnValue(1_700_000_000_000);

    jobStore = {
      getRedis: jest.fn().mockResolvedValue(redisStub),
      createJob: jest.fn().mockResolvedValue({ job: jobRecord, created: true }),
      pushQueue: jest.fn().mockResolvedValue(undefined),
      getQueueDepth: jest.fn().mockResolvedValue(3),
      getStatusCounts: jest.fn().mockResolvedValue({ queued: 1, processing: 0 }),
      getJob: jest.fn().mockResolvedValue(jobRecord)
    };

    service = new EnrichmentService(baseConfig, jobStore);
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  it('uses provided idempotency key when available', () => {
    const key = service.buildIdempotencyKey(context, {
      candidateId: 'cand-1',
      idempotencyKey: 'custom-key'
    });
    expect(key).toBe('custom-key');
  });

  it('derives idempotency key from tenant and candidate when missing', () => {
    const key = service.buildIdempotencyKey(context, { candidateId: 'cand-1' });
    expect(key).toHaveLength(40);
    expect(typeof key).toBe('string');
  });

  it('submits new job and pushes it onto the queue when created', async () => {
    const { job, created } = await service.submitJob(context, { candidateId: 'cand-1' });

    expect(created).toBe(true);
    expect(job).toMatchObject({ jobId: jobRecord.jobId });
    expect(jobStore.createJob).toHaveBeenCalledWith(redisStub, expect.objectContaining({
      tenantId: context.tenant.id,
      candidateId: 'cand-1',
      correlationId: expect.stringContaining(context.requestId)
    }));
    expect(jobStore.pushQueue).toHaveBeenCalledWith(redisStub, jobRecord.jobId, expect.any(String));
    expect(jobStore.getQueueDepth).toHaveBeenCalledWith(redisStub);
  });

  it('skips queue push when dedupe cache returns existing job', async () => {
    jobStore.createJob.mockResolvedValueOnce({ job: jobRecord, created: false });

    const outcome = await service.submitJob(context, { candidateId: 'cand-1' });

    expect(outcome.created).toBe(false);
    expect(jobStore.pushQueue).not.toHaveBeenCalled();
  });

  it('waits for job completion and respects timeout', async () => {
    const finalRecord: EnrichmentJobRecord = {
      ...jobRecord,
      status: 'completed',
      result: {
        modelVersion: 'unit-test-model',
        promptVersion: 'unit-test-prompt'
      }
    };

    const responses = [jobRecord, jobRecord, finalRecord];
    jobStore.getJob.mockImplementation(async () => responses.shift() ?? finalRecord);

    const waitPromise = service.waitForCompletion(jobRecord.jobId, 2_000);
    await jest.advanceTimersByTimeAsync(1_000);
    const result = await waitPromise;

    expect(jobStore.getJob).toHaveBeenCalled();
    expect(result?.status).toBe('completed');
  });

  it('emits health snapshot without throwing when redis is unavailable', async () => {
    jobStore.getRedis.mockRejectedValueOnce(new Error('redis offline'));

    await expect(service.logOperationalSnapshot()).resolves.toBeUndefined();
  });
});
