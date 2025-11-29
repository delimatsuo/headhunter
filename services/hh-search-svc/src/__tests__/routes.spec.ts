const originalEnv = {
  GOOGLE_CLOUD_PROJECT: process.env.GOOGLE_CLOUD_PROJECT,
  AUTH_MODE: process.env.AUTH_MODE,
  ENABLE_GATEWAY_TOKENS: process.env.ENABLE_GATEWAY_TOKENS
};

process.env.GOOGLE_CLOUD_PROJECT = 'test-project';
process.env.AUTH_MODE = 'none';
process.env.ENABLE_GATEWAY_TOKENS = 'false';

import Fastify from 'fastify';

import type { SearchServiceConfig } from '../config';
import type { EmbedClient } from '../embed-client';
import type { PgVectorClient } from '../pgvector-client';
import type { SearchRedisClient } from '../redis-client';
import type { RerankClient } from '../rerank-client';
import type { PerformanceSnapshot, PerformanceTracker } from '../performance-tracker';
import { registerRoutes } from '../routes';
import type { SearchService } from '../search-service';

const baseConfig = (): SearchServiceConfig => ({
  base: {
    env: 'test',
    runtime: {
      serviceName: 'hh-search-svc',
      version: 'test',
      commitSha: 'test',
      serviceId: 'hh-search-svc',
      port: 7102,
      cacheTtlSeconds: 60,
      enableGatewayTokens: false
    },
    redis: {
      host: '127.0.0.1',
      port: 6379,
      password: undefined,
      tls: false,
      tlsRejectUnauthorized: true
    }
  },
  embed: {
    baseUrl: 'http://localhost:7101',
    timeoutMs: 1000,
    authToken: undefined,
    idTokenAudience: undefined,
    retries: 0,
    retryDelayMs: 0,
    circuitBreakerFailures: 3,
    circuitBreakerCooldownMs: 1000,
    healthTenantId: undefined
  },
  pgvector: {
    host: 'localhost',
    port: 5432,
    database: 'headhunter',
    user: 'postgres',
    password: 'password',
    ssl: false,
    schema: 'search',
    embeddingsTable: 'candidate_embeddings',
    profilesTable: 'candidate_profiles',
    dimensions: 2,
    poolMax: 5,
    poolMin: 0,
    idleTimeoutMs: 30_000,
    connectionTimeoutMs: 5_000,
    statementTimeoutMs: 30_000,
    enableAutoMigrate: false
  },
  redis: {
    host: '127.0.0.1',
    port: 6379,
    password: undefined,
    tls: false,
    tlsRejectUnauthorized: true,
    caCert: undefined,
    keyPrefix: 'hh:hybrid',
    ttlSeconds: 60,
    disable: false
  },
  rerank: {
    baseUrl: 'http://localhost:7103',
    timeoutMs: 500,
    retries: 0,
    retryDelayMs: 0,
    idTokenAudience: undefined,
    authToken: undefined,
    enabled: false
  },
  search: {
    vectorWeight: 0.6,
    textWeight: 0.4,
    minSimilarity: 0.35,
    maxResults: 20,
    ecoBoostFactor: 1,
    confidenceFloor: 0.2,
    warmupMultiplier: 2,
    rerankCandidateLimit: 100,
    rerankIncludeReasons: true
  },
  firestoreFallback: {
    enabled: false,
    concurrency: 4
  }
});

describe('registerRoutes', () => {
  const buildDependencies = () => {
    const config = baseConfig();

    const pgClient = {
      healthCheck: vi.fn().mockResolvedValue({ status: 'healthy' }),
      close: vi.fn()
    } as unknown as PgVectorClient;

    const redisClient = {
      healthCheck: vi.fn().mockResolvedValue({ status: 'healthy' }),
      get: vi.fn(),
      set: vi.fn(),
      buildHybridKey: vi.fn(),
      close: vi.fn(),
      isDisabled: vi.fn(() => false)
    } as unknown as SearchRedisClient;

    const embedClient = {
      healthCheck: vi.fn().mockResolvedValue({ status: 'healthy' }),
      embed: vi.fn()
    } as unknown as EmbedClient;

    const rerankClient = {
      healthCheck: vi.fn().mockResolvedValue({ status: 'healthy' }),
      rerank: vi.fn(),
      isEnabled: vi.fn().mockReturnValue(true)
    } as unknown as RerankClient;

    const performanceSnapshot: PerformanceSnapshot = {
      totalCount: 2,
      nonCacheCount: 1,
      cacheHitCount: 1,
      cacheHitRatio: 0.5,
      windowSize: 500,
      lastUpdatedAt: 1234567890,
      totals: { p50: 120, p90: 300, p95: 360, p99: 400, average: 180, max: 360, min: 120 },
      embedding: { p50: 60, p90: 70, p95: 75, p99: 80, average: 62, max: 75, min: 50 },
      retrieval: { p50: 40, p90: 55, p95: 60, p99: 70, average: 45, max: 60, min: 40 },
      rerank: { p50: null, p90: null, p95: null, p99: null, average: null, max: null, min: null }
    };

    const performanceTracker = {
      record: vi.fn(),
      getSnapshot: vi.fn().mockReturnValue(performanceSnapshot)
    } as unknown as PerformanceTracker;

    const state = { isReady: true };

    const dependencies = {
      service: null as SearchService | null,
      config,
      redisClient,
      pgClient,
      embedClient,
      rerankClient,
      performanceTracker,
      state
    };

    return { dependencies, performanceSnapshot, performanceTracker, redisClient };
  };

  afterAll(() => {
    if (originalEnv.GOOGLE_CLOUD_PROJECT) {
      process.env.GOOGLE_CLOUD_PROJECT = originalEnv.GOOGLE_CLOUD_PROJECT;
    } else {
      delete process.env.GOOGLE_CLOUD_PROJECT;
    }

    if (originalEnv.AUTH_MODE) {
      process.env.AUTH_MODE = originalEnv.AUTH_MODE;
    } else {
      delete process.env.AUTH_MODE;
    }

    if (originalEnv.ENABLE_GATEWAY_TOKENS) {
      process.env.ENABLE_GATEWAY_TOKENS = originalEnv.ENABLE_GATEWAY_TOKENS;
    } else {
      delete process.env.ENABLE_GATEWAY_TOKENS;
    }
  });

  it('includes metrics snapshot in readiness response', async () => {
    const { dependencies, performanceSnapshot } = buildDependencies();
    const app = Fastify();
    app.setValidatorCompiler(() => () => true);
    app.setSerializerCompiler(() => (payload: unknown) => JSON.stringify(payload));

    await registerRoutes(app, dependencies);

    const response = await app.inject({ method: 'GET', url: '/health' });
    expect(response.statusCode).toBe(200);
    const payload = response.json();
    expect(payload.metrics).toEqual(performanceSnapshot);
  });

  it('records cache hits using performance tracker', async () => {
    const { dependencies, performanceTracker, redisClient } = buildDependencies();

    const cachedResponse = {
      results: [],
      total: 0,
      cacheHit: false,
      requestId: 'cached-req',
      timings: {
        totalMs: 180,
        embeddingMs: 60,
        retrievalMs: 50,
        rankingMs: 30
      },
      metadata: {}
    };

    (redisClient.get as jest.Mock).mockResolvedValue(cachedResponse);

    const service = {
      computeCacheToken: vi.fn(() => 'token')
    } as unknown as SearchService;
    dependencies.service = service;

    const app = Fastify();
    app.setValidatorCompiler(() => () => true);
    app.setSerializerCompiler(() => (payload: unknown) => JSON.stringify(payload));
    app.decorateRequest('tenant', null);
    app.decorateRequest('user', null);
    app.decorateRequest('requestContext', null);
    app.addHook('onRequest', async (request) => {
      (request as any).tenant = { id: 'tenant-alpha', isActive: true };
      (request as any).requestContext = { requestId: 'req-123' };
    });

    await registerRoutes(app, dependencies);

    const response = await app.inject({
      method: 'POST',
      url: '/v1/search/hybrid',
      payload: {
        query: 'test'
      }
    });

    expect(response.statusCode).toBe(200);
    expect(performanceTracker.record).toHaveBeenCalledWith(
      expect.objectContaining({ cacheHit: true, totalMs: 180 })
    );
  });

  it('returns metrics even when service is degraded', async () => {
    const { dependencies, performanceSnapshot } = buildDependencies();
    const app = Fastify();
    app.setValidatorCompiler(() => () => true);
    app.setSerializerCompiler(() => (payload: unknown) => JSON.stringify(payload));

    (dependencies.pgClient.healthCheck as jest.Mock).mockResolvedValue({ status: 'degraded', message: 'pg down' });

    await registerRoutes(app, dependencies);

    const response = await app.inject({ method: 'GET', url: '/health' });
    expect(response.statusCode).toBe(503);
    const payload = response.json();
    expect(payload.metrics).toEqual(performanceSnapshot);
    expect(payload.components.pgvector.status).toBe('degraded');
  });
});
