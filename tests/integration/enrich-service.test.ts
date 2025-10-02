import { afterEach, beforeEach, describe, expect, it, jest } from '@jest/globals';

import type { EnrichServiceConfig } from '../../services/hh-enrich-svc/src/config';
import { EnrichmentJobStore } from '../../services/hh-enrich-svc/src/job-store';
import { EnrichmentService } from '../../services/hh-enrich-svc/src/enrichment-service';
import { EnrichmentWorker } from '../../services/hh-enrich-svc/src/worker';
import type { EnrichmentJobRecord } from '../../services/hh-enrich-svc/src/types';

class InMemoryRedisClient {
  private readonly hashes = new Map<string, Map<string, string>>();
  private readonly strings = new Map<string, string>();
  private readonly lists = new Map<string, string[]>();

  async hSet(key: string, fieldOrObject: any, value?: string): Promise<number> {
    const hash = this.hashes.get(key) ?? new Map<string, string>();
    if (typeof fieldOrObject === 'string') {
      hash.set(fieldOrObject, value ?? '');
    } else {
      for (const [field, fieldValue] of Object.entries(fieldOrObject)) {
        hash.set(field, String(fieldValue));
      }
    }
    this.hashes.set(key, hash);
    return hash.size;
  }

  async hGetAll(key: string): Promise<Record<string, string>> {
    const hash = this.hashes.get(key);
    if (!hash) {
      return {};
    }
    return Object.fromEntries(hash.entries());
  }

  async hGet(key: string, field: string): Promise<string | null> {
    const hash = this.hashes.get(key);
    if (!hash) {
      return null;
    }
    return hash.get(field) ?? null;
  }

  async hIncrBy(key: string, field: string, increment: number): Promise<number> {
    const hash = this.hashes.get(key) ?? new Map<string, string>();
    const current = Number(hash.get(field) ?? '0');
    const next = current + increment;
    hash.set(field, String(next));
    this.hashes.set(key, hash);
    return next;
  }

  async hDel(key: string, field: string): Promise<number> {
    const hash = this.hashes.get(key);
    if (!hash) {
      return 0;
    }
    const deleted = hash.delete(field) ? 1 : 0;
    if (hash.size === 0) {
      this.hashes.delete(key);
    }
    return deleted;
  }

  async set(key: string, value: string): Promise<'OK'> {
    this.strings.set(key, value);
    return 'OK';
  }

  async get(key: string): Promise<string | null> {
    return this.strings.get(key) ?? null;
  }

  async expire(): Promise<number> {
    return 1;
  }

  async lPush(key: string, value: string): Promise<number> {
    const list = this.lists.get(key) ?? [];
    list.unshift(value);
    this.lists.set(key, list);
    return list.length;
  }

  async lLen(key: string): Promise<number> {
    const list = this.lists.get(key) ?? [];
    return list.length;
  }

  duplicate(): this {
    return this;
  }
}

class TestJobStore extends EnrichmentJobStore {
  constructor(config: EnrichServiceConfig, private readonly redis: InMemoryRedisClient) {
    super(config);
  }

  async getRedis(): Promise<any> {
    return this.redis as any;
  }
}

const config: EnrichServiceConfig = {
  base: {} as any,
  queue: {
    queueKey: 'hh:test:queue',
    resultKeyPrefix: 'hh:test:job:',
    dedupeKeyPrefix: 'hh:test:dedupe:',
    maxConcurrency: 4,
    jobTtlSeconds: 3_600,
    dedupeTtlSeconds: 900,
    pythonExecutable: 'python3',
    pythonScript: '/tmp/run.py',
    jobTimeoutMs: 10_000,
    pollIntervalMs: 500,
    retryLimit: 2,
    retryBaseDelayMs: 100,
    retryMaxDelayMs: 2_000,
    circuitBreakerFailures: 3,
    circuitBreakerCooldownMs: 45_000
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
    circuitBreakerResetMs: 45_000
  },
  versioning: {
    modelVersion: 'integration-test-model',
    promptVersion: 'integration-test-prompt'
  }
};

describe('Enrichment pipeline integration', () => {
  let redis: InMemoryRedisClient;
  let store: TestJobStore;
  let service: EnrichmentService;
  let worker: EnrichmentWorker;

  const context = {
    tenant: { id: 'tenant-integration' } as any,
    requestId: 'integration-req-1'
  };

  beforeEach(() => {
    redis = new InMemoryRedisClient();
    store = new TestJobStore(config, redis);
    service = new EnrichmentService(config, store);
    worker = new EnrichmentWorker(config, store, service);

    (worker as any).embeddingClient = {
      upsertEmbedding: jest.fn().mockResolvedValue({ success: true, durationMs: 5, attempts: 1 })
    };
    (worker as any).invokePython = jest.fn().mockResolvedValue({
      candidate: { resume_text: 'Integration resume text', location: 'Remote' },
      processing_time_seconds: 1.2
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  async function processJob(jobId: string): Promise<void> {
    await (worker as any).processJob(jobId);
  }

  it('processes a job end-to-end and records metrics', async () => {
    const submission = await service.submitJob(context as any, { candidateId: 'cand-integration' });
    expect(submission.created).toBe(true);
    expect(submission.job.status).toBe('queued');

    await processJob(submission.job.jobId);

    const status = await service.getStatus(submission.job.jobId);
    expect(status?.status).toBe('completed');
    expect(status?.result?.embeddingUpserted).toBe(true);
    expect(status?.result?.phaseDurationsMs).toBeDefined();
    expect(((worker as any).embeddingClient.upsertEmbedding as jest.Mock)).toHaveBeenCalledTimes(1);

    const secondSubmission = await service.submitJob(context as any, { candidateId: 'cand-integration' });
    expect(secondSubmission.created).toBe(false);
    expect(secondSubmission.job.jobId).toBe(submission.job.jobId);
  });

  it('retries transient python failures before succeeding', async () => {
    const pythonMock = (worker as any).invokePython as jest.Mock;
    pythonMock.mockRejectedValueOnce(new Error('temporary timeout'));
    pythonMock.mockResolvedValueOnce({
      candidate: { resume_text: 'Recovered resume' },
      processing_time_seconds: 1.0
    });

    const submission = await service.submitJob(context as any, { candidateId: 'cand-retry' });
    await processJob(submission.job.jobId);

    const status = await service.getStatus(submission.job.jobId);
    expect(status?.status).toBe('completed');
    expect(status?.result?.attempts).toBe(2);
    expect(pythonMock).toHaveBeenCalledTimes(2);
  });

  it('marks job as completed even when embedding upsert fails', async () => {
    (worker as any).embeddingClient.upsertEmbedding = jest
      .fn()
      .mockResolvedValue({ success: false, durationMs: 20, attempts: 2, errorCategory: 'timeout' });

    const submission = await service.submitJob(context as any, { candidateId: 'cand-embed-fail' });
    await processJob(submission.job.jobId);

    const status = await service.getStatus(submission.job.jobId);
    expect(status?.status).toBe('completed');
    expect(status?.result?.embeddingUpserted).toBe(false);
    expect(status?.result?.phaseDurationsMs?.embed).toBeGreaterThanOrEqual(0);
  });
});
