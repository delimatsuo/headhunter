import { describe, it, expect, beforeEach, afterEach, afterAll, vi, type Mock } from 'vitest';

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
import type { PgHybridSearchRow, NLPParseResult } from '../types';
import type { PerformanceTracker } from '../performance-tracker';
import type { QueryParser, ParsedQuery } from '../nlp';

const logger = {
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
  debug: vi.fn(),
  child: vi.fn()
};
(logger.child as Mock).mockReturnValue(logger);

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

const createPgClient = (): PgVectorClient => ({
  hybridSearch: vi.fn(),
  close: vi.fn(),
  healthCheck: vi.fn().mockResolvedValue({ status: 'healthy' }),
  initialize: vi.fn()
} as unknown as PgVectorClient);

const createRedisClient = (): SearchRedisClient => ({
  get: vi.fn(),
  set: vi.fn(),
  delete: vi.fn(),
  buildHybridKey: vi.fn().mockReturnValue('hybrid-key'),
  buildEmbeddingKey: vi.fn().mockReturnValue('embedding-key'),
  healthCheck: vi.fn().mockResolvedValue({ status: 'healthy' }),
  close: vi.fn(),
  isDisabled: vi.fn().mockReturnValue(false)
} as unknown as SearchRedisClient);

const createEmbedClient = (): EmbedClient => ({
  generateEmbedding: vi.fn(),
  healthCheck: vi.fn().mockResolvedValue({ status: 'healthy' })
} as unknown as EmbedClient);

// Unused factory - tests create inline mocks for specific scenarios
const _createRerankClient = (): RerankClient => ({
  rerank: vi.fn(),
  healthCheck: vi.fn().mockResolvedValue({ status: 'healthy' }),
  isEnabled: vi.fn().mockReturnValue(true)
} as unknown as RerankClient);
void _createRerankClient; // Silence unused warning

const createPerformanceTracker = () => ({
  record: vi.fn()
});

describe('SearchService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetModules();
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

    const rerankClient = {
      isEnabled: vi.fn(() => true),
      rerank: vi.fn().mockResolvedValue(rerankResponse),
      healthCheck: vi.fn()
    } as unknown as RerankClient;

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

  // =====================================================
  // NLP Integration Tests (NLNG-05)
  // =====================================================
  describe('NLP Integration', () => {
    // Mock QueryParser
    const createMockQueryParser = () => ({
      parse: vi.fn(),
      initialize: vi.fn().mockResolvedValue(undefined),
      isInitialized: vi.fn().mockReturnValue(true)
    });

    it('should skip NLP when enableNlp is false', async () => {
      const config = createBaseConfig();
      const mockQueryParser = createMockQueryParser();

      const pgRow: PgHybridSearchRow = {
        candidate_id: 'cand-nlp-001',
        vector_score: 0.5,
        text_score: 0.1,
        hybrid_score: 0.5,
        analysis_confidence: 0.9,
        full_name: 'Test Candidate'
      };

      const pgClient = createPgClient();
      pgClient.hybridSearch.mockResolvedValue([pgRow]);

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

      const performanceTracker = createPerformanceTracker() as unknown as PerformanceTracker;

      const service = new SearchService({
        config,
        pgClient,
        embedClient,
        redisClient,
        performanceTracker,
        logger: getTestLogger(),
        queryParser: mockQueryParser as unknown as QueryParser
      });

      await service.hybridSearch(
        {
          tenant: { id: 'tenant-alpha', isActive: true },
          requestId: 'req-nlp-skip'
        },
        {
          query: 'senior python developer',
          enableNlp: false
        }
      );

      expect(mockQueryParser.parse).not.toHaveBeenCalled();
    });

    it('should apply NLP-extracted skills to filters', async () => {
      const config = createBaseConfig();
      const mockQueryParser = createMockQueryParser();

      mockQueryParser.parse.mockResolvedValue({
        originalQuery: 'senior python developer',
        parseMethod: 'nlp',
        confidence: 0.85,
        intent: 'structured_search',
        entities: {
          role: 'developer',
          skills: ['Python'],
          expandedSkills: ['Django', 'Flask'],
          seniority: 'senior'
        },
        semanticExpansion: {
          expandedSeniorities: ['senior', 'sr', 'sr.', 'staff', 'principal'],
          expandedRoles: ['developer', 'engineer', 'programmer']
        },
        timings: { intentMs: 5, extractionMs: 50, expansionMs: 2, totalMs: 57 }
      } as ParsedQuery);

      const pgRow: PgHybridSearchRow = {
        candidate_id: 'cand-nlp-002',
        vector_score: 0.5,
        text_score: 0.1,
        hybrid_score: 0.5,
        analysis_confidence: 0.9,
        full_name: 'Python Dev'
      };

      const pgClient = createPgClient();
      pgClient.hybridSearch.mockResolvedValue([pgRow]);

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

      const performanceTracker = createPerformanceTracker() as unknown as PerformanceTracker;

      const service = new SearchService({
        config,
        pgClient,
        embedClient,
        redisClient,
        performanceTracker,
        logger: getTestLogger(),
        queryParser: mockQueryParser as unknown as QueryParser
      });

      await service.hybridSearch(
        {
          tenant: { id: 'tenant-alpha', isActive: true },
          requestId: 'req-nlp-skills'
        },
        {
          query: 'senior python developer',
          enableNlp: true
        }
      );

      expect(mockQueryParser.parse).toHaveBeenCalledWith('senior python developer');

      // Verify filters were applied
      const callArgs = pgClient.hybridSearch.mock.calls[0]?.[0];
      expect(callArgs?.filters?.skills).toContain('Python');
      expect(callArgs?.filters?.skills).toContain('Django');
      expect(callArgs?.filters?.skills).toContain('Flask');
    });

    it('should apply semantic seniority expansion - Lead matches Senior/Staff/Principal', async () => {
      const config = createBaseConfig();
      const mockQueryParser = createMockQueryParser();

      mockQueryParser.parse.mockResolvedValue({
        originalQuery: 'lead engineer',
        parseMethod: 'nlp',
        confidence: 0.85,
        intent: 'structured_search',
        entities: {
          role: 'engineer',
          skills: [],
          expandedSkills: [],
          seniority: 'lead'
        },
        semanticExpansion: {
          expandedSeniorities: ['lead', 'tech lead', 'team lead', 'senior', 'staff'],
          expandedRoles: ['engineer', 'developer', 'programmer']
        },
        timings: { intentMs: 3, extractionMs: 40, expansionMs: 2, totalMs: 45 }
      } as ParsedQuery);

      const pgRow: PgHybridSearchRow = {
        candidate_id: 'cand-nlp-003',
        vector_score: 0.5,
        text_score: 0.1,
        hybrid_score: 0.5,
        analysis_confidence: 0.9,
        full_name: 'Lead Engineer'
      };

      const pgClient = createPgClient();
      pgClient.hybridSearch.mockResolvedValue([pgRow]);

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

      const performanceTracker = createPerformanceTracker() as unknown as PerformanceTracker;

      const service = new SearchService({
        config,
        pgClient,
        embedClient,
        redisClient,
        performanceTracker,
        logger: getTestLogger(),
        queryParser: mockQueryParser as unknown as QueryParser
      });

      await service.hybridSearch(
        {
          tenant: { id: 'tenant-alpha', isActive: true },
          requestId: 'req-nlp-seniority'
        },
        {
          query: 'lead engineer',
          enableNlp: true
        }
      );

      // CRITICAL: Verify expanded seniorities are used, not just 'lead'
      const callArgs = pgClient.hybridSearch.mock.calls[0]?.[0];
      expect(callArgs?.filters?.seniorityLevels).toContain('lead');
      expect(callArgs?.filters?.seniorityLevels).toContain('senior');
      expect(callArgs?.filters?.seniorityLevels).toContain('staff');
    });

    it('should include NLP metadata in response', async () => {
      const config = createBaseConfig();
      const mockQueryParser = createMockQueryParser();

      mockQueryParser.parse.mockResolvedValue({
        originalQuery: 'python dev',
        parseMethod: 'nlp',
        confidence: 0.78,
        intent: 'structured_search',
        entities: {
          skills: ['Python'],
          expandedSkills: []
        },
        semanticExpansion: {
          expandedSeniorities: [],
          expandedRoles: []
        },
        timings: { intentMs: 3, extractionMs: 45, expansionMs: 1, totalMs: 49 }
      } as ParsedQuery);

      const pgRow: PgHybridSearchRow = {
        candidate_id: 'cand-nlp-004',
        vector_score: 0.5,
        text_score: 0.1,
        hybrid_score: 0.5,
        analysis_confidence: 0.9,
        full_name: 'Python Developer'
      };

      const pgClient = createPgClient();
      pgClient.hybridSearch.mockResolvedValue([pgRow]);

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

      const performanceTracker = createPerformanceTracker() as unknown as PerformanceTracker;

      const service = new SearchService({
        config,
        pgClient,
        embedClient,
        redisClient,
        performanceTracker,
        logger: getTestLogger(),
        queryParser: mockQueryParser as unknown as QueryParser
      });

      const response = await service.hybridSearch(
        {
          tenant: { id: 'tenant-alpha', isActive: true },
          requestId: 'req-nlp-metadata'
        },
        {
          query: 'python dev',
          enableNlp: true
        }
      );

      const nlpMeta = response.metadata?.nlp as NLPParseResult | undefined;
      expect(nlpMeta).toBeDefined();
      expect(nlpMeta?.parseMethod).toBe('nlp');
      expect(nlpMeta?.confidence).toBe(0.78);
      expect(nlpMeta?.semanticExpansion).toBeDefined();
    });

    it('should fall back gracefully when NLP fails', async () => {
      const config = createBaseConfig();
      const mockQueryParser = createMockQueryParser();

      mockQueryParser.parse.mockRejectedValue(new Error('NLP service unavailable'));

      const pgRow: PgHybridSearchRow = {
        candidate_id: 'cand-nlp-005',
        vector_score: 0.5,
        text_score: 0.1,
        hybrid_score: 0.5,
        analysis_confidence: 0.9,
        full_name: 'Fallback Candidate'
      };

      const pgClient = createPgClient();
      pgClient.hybridSearch.mockResolvedValue([pgRow]);

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

      const performanceTracker = createPerformanceTracker() as unknown as PerformanceTracker;

      const service = new SearchService({
        config,
        pgClient,
        embedClient,
        redisClient,
        performanceTracker,
        logger: getTestLogger(),
        queryParser: mockQueryParser as unknown as QueryParser
      });

      // Should not throw
      const response = await service.hybridSearch(
        {
          tenant: { id: 'tenant-alpha', isActive: true },
          requestId: 'req-nlp-fallback'
        },
        {
          query: 'python developer',
          enableNlp: true
        }
      );

      expect(response.results).toBeDefined();
      expect(response.metadata?.nlp).toBeUndefined();
    });

    it('should preserve original query for BM25 text search', async () => {
      const config = createBaseConfig();
      const mockQueryParser = createMockQueryParser();

      mockQueryParser.parse.mockResolvedValue({
        originalQuery: 'senior python developer in NYC',
        parseMethod: 'nlp',
        confidence: 0.85,
        intent: 'structured_search',
        entities: {
          skills: ['Python'],
          expandedSkills: [],
          location: 'NYC',
          seniority: 'senior'
        },
        semanticExpansion: {
          expandedSeniorities: ['senior', 'sr', 'staff', 'principal'],
          expandedRoles: []
        },
        timings: { intentMs: 3, extractionMs: 50, expansionMs: 1, totalMs: 54 }
      } as ParsedQuery);

      const pgRow: PgHybridSearchRow = {
        candidate_id: 'cand-nlp-006',
        vector_score: 0.5,
        text_score: 0.1,
        hybrid_score: 0.5,
        analysis_confidence: 0.9,
        full_name: 'NYC Python Dev'
      };

      const pgClient = createPgClient();
      pgClient.hybridSearch.mockResolvedValue([pgRow]);

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

      const performanceTracker = createPerformanceTracker() as unknown as PerformanceTracker;

      const service = new SearchService({
        config,
        pgClient,
        embedClient,
        redisClient,
        performanceTracker,
        logger: getTestLogger(),
        queryParser: mockQueryParser as unknown as QueryParser
      });

      await service.hybridSearch(
        {
          tenant: { id: 'tenant-alpha', isActive: true },
          requestId: 'req-nlp-preserve-query'
        },
        {
          query: 'senior python developer in NYC',
          enableNlp: true
        }
      );

      // Text query should remain the original for BM25
      const callArgs = pgClient.hybridSearch.mock.calls[0]?.[0];
      expect(callArgs?.textQuery).toBe('senior python developer in NYC');
    });
  });
});

// Firestore fallback is not exercised directly, but this type satisfies constructor typing requirements.
interface FirestoreEnabledService extends SearchService {
  firestore?: Firestore | null;
}

// Assert SearchService#setFirestore accepts the Firestore mock shape for future tests.
const _firestoreTypeCheck: FirestoreEnabledService | undefined = undefined;
void _firestoreTypeCheck;
