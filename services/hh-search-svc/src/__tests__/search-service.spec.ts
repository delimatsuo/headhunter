const originalEnv = {
  GOOGLE_CLOUD_PROJECT: process.env.GOOGLE_CLOUD_PROJECT,
  AUTH_MODE: process.env.AUTH_MODE,
  ENABLE_GATEWAY_TOKENS: process.env.ENABLE_GATEWAY_TOKENS
};

process.env.GOOGLE_CLOUD_PROJECT = 'test-project';
process.env.AUTH_MODE = 'none';
process.env.ENABLE_GATEWAY_TOKENS = 'false';

import type { Firestore } from '@google-cloud/firestore';
import type { SearchServiceConfig } from '../config';
import type { EmbedClient } from '../embed-client';
import type { PgVectorClient } from '../pgvector-client';
import type { SearchRedisClient } from '../redis-client';
import type { RerankClient, RerankResponse } from '../rerank-client';
import { SearchService } from '../search-service';
import type { HybridSearchRequest, HybridSearchResponse, PgHybridSearchRow } from '../types';
import type { PerformanceTracker } from '../performance-tracker';

const logger = {
  info: jest.fn(),
  warn: jest.fn(),
  error: jest.fn(),
  child: () => logger
};

const baseConfigTemplate = (): SearchServiceConfig => ({
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
      host: 'localhost',
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

const getTestLogger = () => logger;

const createBaseConfig = (): SearchServiceConfig =>
  JSON.parse(JSON.stringify(baseConfigTemplate())) as SearchServiceConfig;

const createRedisClient = (): jest.Mocked<SearchRedisClient> => ({
  buildEmbeddingKey: jest.fn(() => 'embedding-key'),
  buildHybridKey: jest.fn(() => 'hybrid-key'),
  get: jest.fn(),
  set: jest.fn(),
  close: jest.fn(),
  healthCheck: jest.fn().mockResolvedValue({ status: 'healthy' }),
  isDisabled: jest.fn(() => false)
});

const createPgClient = (): jest.Mocked<PgVectorClient> => ({
  hybridSearch: jest.fn(),
  close: jest.fn(),
  healthCheck: jest.fn().mockResolvedValue({ status: 'healthy' }),
  initialize: jest.fn()
});

const createEmbedClient = (): jest.Mocked<EmbedClient> => ({
  generateEmbedding: jest.fn(),
  close: jest.fn(),
  healthCheck: jest.fn().mockResolvedValue({ status: 'healthy' })
});

const createPerformanceTracker = () => ({
  record: jest.fn()
});

describe('SearchService', () => {
  beforeEach(() => {
    jest.resetAllMocks();
  });

  afterEach(() => {
    jest.resetModules();
  });

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

  it('uses cached embedding when available', async () => {
    const config = createBaseConfig();
    const cachedEmbedding = [0.42, 0.24];

    const pgRow: PgHybridSearchRow = {
      candidate_id: 'cand-001',
      vector_score: 0.5,
      text_score: 0.1,
      hybrid_score: 0.5,
      analysis_confidence: 0.9,
      full_name: 'Cached Candidate'
    };

    const pgClient = createPgClient();
    pgClient.hybridSearch.mockResolvedValue([pgRow]);

    const embedClient = createEmbedClient();

    const redisClient = createRedisClient();
    redisClient.get.mockResolvedValue(cachedEmbedding);

    const performanceTracker = createPerformanceTracker() as unknown as PerformanceTracker;

    const service = new SearchService({
      config,
      pgClient,
      embedClient,
      redisClient,
      performanceTracker,
      logger: getTestLogger()
    });

    const response = await service.hybridSearch(
      {
        tenant: { id: 'tenant-alpha', isActive: true },
        requestId: 'req-cache'
      },
      {
        query: 'cached embedding query',
        includeDebug: false
      }
    );

    expect(pgClient.hybridSearch).toHaveBeenCalledTimes(1);
    const callArgs = pgClient.hybridSearch.mock.calls[0]?.[0];
    expect(callArgs?.embedding).toBe(cachedEmbedding);
    expect(embedClient.generateEmbedding).not.toHaveBeenCalled();
    expect(redisClient.get).toHaveBeenCalledWith('embedding-key');
    expect(response.results).toHaveLength(1);
  });

  it('stores generated embedding when cache miss occurs', async () => {
    const config = createBaseConfig();

    const pgRow: PgHybridSearchRow = {
      candidate_id: 'cand-002',
      vector_score: 0.4,
      text_score: 0.05,
      hybrid_score: 0.42,
      analysis_confidence: 0.82,
      full_name: 'Generated Candidate'
    };

    const generatedEmbedding = [0.1, 0.2];

    const pgClient = createPgClient();
    pgClient.hybridSearch.mockResolvedValue([pgRow]);

    const embedClient = createEmbedClient();
    embedClient.generateEmbedding.mockResolvedValue({
      embedding: generatedEmbedding,
      provider: 'test',
      model: 'test-model',
      dimensions: 2,
      latencyMs: 5
    });

    const redisClient = createRedisClient();
    redisClient.get.mockResolvedValue(null);

    const performanceTracker = createPerformanceTracker() as unknown as PerformanceTracker;

    const service = new SearchService({
      config,
      pgClient,
      embedClient,
      redisClient,
      performanceTracker,
      logger: getTestLogger()
    });

    await service.hybridSearch(
      {
        tenant: { id: 'tenant-alpha', isActive: true },
        requestId: 'req-generate'
      },
      {
        query: 'generate embedding',
        includeDebug: false
      }
    );

    expect(redisClient.get).toHaveBeenCalledWith('embedding-key');
    expect(embedClient.generateEmbedding).toHaveBeenCalledTimes(1);
    expect(redisClient.set).toHaveBeenCalledWith('embedding-key', generatedEmbedding);
  });

  it('applies rerank ordering when enabled', async () => {
    const config = createBaseConfig();
    config.rerank.enabled = true;

    const pgRows: PgHybridSearchRow[] = [
      {
        candidate_id: 'cand-A',
        vector_score: 0.9,
        text_score: 0.2,
        hybrid_score: 0.85,
        analysis_confidence: 0.9,
        full_name: 'Candidate A'
      } as PgHybridSearchRow,
      {
        candidate_id: 'cand-B',
        vector_score: 0.7,
        text_score: 0.4,
        hybrid_score: 0.8,
        analysis_confidence: 0.92,
        full_name: 'Candidate B'
      } as PgHybridSearchRow
    ];

    const pgClient = createPgClient();
    pgClient.hybridSearch.mockResolvedValue(pgRows);

    const embedClient = createEmbedClient();
    embedClient.generateEmbedding.mockResolvedValue({
      embedding: [0.1, 0.2],
      provider: 'test',
      model: 'test-model',
      dimensions: 2,
      latencyMs: 5
    });

    const redisClient = createRedisClient();
    redisClient.get.mockResolvedValue(null);

    const rerankResponse: RerankResponse = {
      results: [
        {
          candidateId: 'cand-B',
          rank: 1,
          score: 0.95,
          reasons: ['LLM preferred candidate']
        },
        {
          candidateId: 'cand-A',
          rank: 2,
          score: 0.6,
          reasons: []
        }
      ],
      cacheHit: false,
      usedFallback: false,
      requestId: 'rerank-req',
      timings: {
        totalMs: 12
      }
    };

    const rerankClient: jest.Mocked<RerankClient> = {
      isEnabled: jest.fn(() => true),
      rerank: jest.fn().mockResolvedValue(rerankResponse),
      healthCheck: jest.fn()
    } as unknown as jest.Mocked<RerankClient>;

    const performanceTracker = createPerformanceTracker() as unknown as PerformanceTracker;

    const service = new SearchService({
      config,
      pgClient,
      embedClient,
      redisClient,
      rerankClient,
      performanceTracker,
      logger: getTestLogger()
    });

    const response = await service.hybridSearch(
      {
        tenant: { id: 'tenant-alpha', isActive: true },
        requestId: 'req-rerank'
      },
      {
        jobDescription: 'Example job description',
        query: 'search query',
        limit: 2
      }
    );

    expect(rerankClient.rerank).toHaveBeenCalledTimes(1);
    expect(response.results[0].candidateId).toBe('cand-B');
    expect(response.results[0].matchReasons).toContain('LLM preferred candidate');
    expect(response.timings.rerankMs).toBe(12);
    expect(response.metadata?.rerank).toMatchObject({ cacheHit: false, usedFallback: false });
  });
});

// Firestore fallback is not exercised directly, but this type satisfies constructor typing requirements.
interface FirestoreEnabledService extends SearchService {
  firestore?: Firestore | null;
}

// Assert SearchService#setFirestore accepts the Firestore mock shape for future tests.
const _firestoreTypeCheck: FirestoreEnabledService | undefined = undefined;
void _firestoreTypeCheck;
