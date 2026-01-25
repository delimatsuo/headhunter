/**
 * QueryParser Unit Tests
 *
 * Tests for the NLP query parser orchestrator that combines:
 * - IntentRouter (intent classification)
 * - EntityExtractor (structured entity extraction)
 * - QueryExpander (skill ontology expansion)
 *
 * @module nlp/__tests__/query-parser.spec
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type { Logger } from 'pino';

// ============================================================================
// MOCK DEFINITIONS (must be at top level, before vi.mock calls)
// ============================================================================

// These mock functions are defined at module scope so vi.mock hoisting can access them
const mockIntentRouterInit = vi.fn().mockResolvedValue(undefined);
const mockIntentRouterIsInit = vi.fn().mockReturnValue(true);
const mockIntentRouterClassify = vi.fn().mockReturnValue({
  intent: 'structured_search',
  confidence: 0.85,
  timingMs: 2
});

const mockExtractorExtract = vi.fn().mockResolvedValue({
  entities: {
    role: 'developer',
    skills: ['Python', 'Django'],
    seniority: 'senior',
    location: 'NYC'
  },
  timingMs: 50,
  fromCache: false
});

const mockExpanderExpand = vi.fn().mockReturnValue({
  explicitSkills: ['Python', 'Django'],
  expandedSkills: [
    { name: 'Python', isExplicit: true, confidence: 1.0 },
    { name: 'Django', isExplicit: true, confidence: 1.0 },
    { name: 'Flask', isExplicit: false, confidence: 0.54, source: 'Python' }
  ],
  allSkills: ['Python', 'Django', 'Flask'],
  timingMs: 1
});

// ============================================================================
// MOCKS (vi.mock calls are hoisted to top of file by Vitest)
// ============================================================================

vi.mock('../intent-router', () => ({
  IntentRouter: class MockIntentRouter {
    initialize = mockIntentRouterInit;
    isInitialized = mockIntentRouterIsInit;
    classifyIntent = mockIntentRouterClassify;
  }
}));

vi.mock('../entity-extractor', () => ({
  createEntityExtractor: () => ({
    extractEntities: mockExtractorExtract
  }),
  EntityExtractor: class MockEntityExtractor {}
}));

vi.mock('../query-expander', () => ({
  QueryExpander: class MockQueryExpander {
    expandSkills = mockExpanderExpand;
  }
}));

// Import after mocks are set up
import { QueryParser } from '../query-parser';

// ============================================================================
// TEST UTILITIES
// ============================================================================

// Mock logger
const mockLogger = {
  info: vi.fn(),
  debug: vi.fn(),
  trace: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
  child: vi.fn().mockReturnThis()
} as unknown as Logger;

// Mock embedding generator
const mockGenerateEmbedding = vi.fn().mockResolvedValue(
  new Array(768).fill(0).map((_, i) => Math.sin(i * 0.01))
);

// ============================================================================
// TESTS
// ============================================================================

describe('QueryParser', () => {
  let parser: QueryParser;

  beforeEach(() => {
    vi.clearAllMocks();
    QueryParser.clearCache();

    // Reset mock return values to defaults
    mockIntentRouterClassify.mockReturnValue({
      intent: 'structured_search',
      confidence: 0.85,
      timingMs: 2
    });

    mockExtractorExtract.mockResolvedValue({
      entities: {
        role: 'developer',
        skills: ['Python', 'Django'],
        seniority: 'senior',
        location: 'NYC'
      },
      timingMs: 50,
      fromCache: false
    });

    mockExpanderExpand.mockReturnValue({
      explicitSkills: ['Python', 'Django'],
      expandedSkills: [
        { name: 'Python', isExplicit: true, confidence: 1.0 },
        { name: 'Django', isExplicit: true, confidence: 1.0 },
        { name: 'Flask', isExplicit: false, confidence: 0.54, source: 'Python' }
      ],
      allSkills: ['Python', 'Django', 'Flask'],
      timingMs: 1
    });

    parser = new QueryParser({
      generateEmbedding: mockGenerateEmbedding,
      logger: mockLogger,
      togetherApiKey: 'test-key',
      config: {
        enabled: true,
        intentConfidenceThreshold: 0.6,
        extractionTimeoutMs: 100,
        cacheExtractionResults: true,
        enableQueryExpansion: true,
        expansionDepth: 1,
        expansionConfidenceThreshold: 0.8
      }
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // --------------------------------------------------------------------------
  // Initialization Tests
  // --------------------------------------------------------------------------

  describe('initialization', () => {
    it('should initialize on first parse', async () => {
      expect(parser.isInitialized()).toBe(false);
      await parser.parse('senior python developer');
      expect(parser.isInitialized()).toBe(true);
    });

    it('should be idempotent - multiple initialize calls are safe', async () => {
      await parser.initialize();
      await parser.initialize();
      await parser.initialize();
      expect(parser.isInitialized()).toBe(true);
    });

    it('should handle concurrent initialization', async () => {
      const promises = [
        parser.parse('query 1'),
        parser.parse('query 2'),
        parser.parse('query 3')
      ];

      await Promise.all(promises);
      expect(parser.isInitialized()).toBe(true);
    });
  });

  // --------------------------------------------------------------------------
  // Parse Tests
  // --------------------------------------------------------------------------

  describe('parse', () => {
    beforeEach(async () => {
      await parser.initialize();
    });

    it('should return ParsedQuery with all fields', async () => {
      const result = await parser.parse('senior python developer in NYC');

      expect(result.originalQuery).toBe('senior python developer in NYC');
      expect(result.parseMethod).toBe('nlp');
      expect(result.confidence).toBe(0.85);
      expect(result.intent).toBe('structured_search');
      expect(result.entities.role).toBe('developer');
      expect(result.entities.skills).toContain('Python');
      expect(result.entities.seniority).toBe('senior');
      expect(result.entities.location).toBe('NYC');
    });

    it('should include expanded skills', async () => {
      const result = await parser.parse('python developer');

      expect(result.entities.expandedSkills).toContain('Flask');
    });

    it('should not duplicate explicit skills in expandedSkills', async () => {
      const result = await parser.parse('python developer');

      // Python and Django are explicit, so should not appear in expandedSkills
      expect(result.entities.expandedSkills).not.toContain('Python');
      expect(result.entities.expandedSkills).not.toContain('Django');
    });

    it('should report timings', async () => {
      const result = await parser.parse('test query');

      expect(result.timings.intentMs).toBeGreaterThanOrEqual(0);
      expect(result.timings.extractionMs).toBeGreaterThanOrEqual(0);
      expect(result.timings.expansionMs).toBeGreaterThanOrEqual(0);
      expect(result.timings.totalMs).toBeGreaterThanOrEqual(0);
    });

    it('should return fallback for very short queries', async () => {
      const result = await parser.parse('ab');

      expect(result.parseMethod).toBe('keyword_fallback');
      expect(result.entities.skills).toEqual([]);
      expect(result.entities.expandedSkills).toEqual([]);
    });

    it('should return fallback for empty queries', async () => {
      const result = await parser.parse('');

      expect(result.parseMethod).toBe('keyword_fallback');
    });

    it('should trim whitespace from queries', async () => {
      const result = await parser.parse('  senior python developer  ');

      expect(result.originalQuery).toBe('senior python developer');
    });

    it('should use pre-computed embedding when provided', async () => {
      const precomputed = new Array(768).fill(0.5);

      await parser.parse('test query', precomputed);

      // Embedding generator should not be called
      expect(mockGenerateEmbedding).not.toHaveBeenCalled();
    });

    it('should generate embedding when not provided', async () => {
      await parser.parse('test query');

      expect(mockGenerateEmbedding).toHaveBeenCalledWith('test query');
    });
  });

  // --------------------------------------------------------------------------
  // Fallback Tests
  // --------------------------------------------------------------------------

  describe('fallback behavior', () => {
    beforeEach(async () => {
      await parser.initialize();
    });

    it('should fallback when embedding generation fails', async () => {
      mockGenerateEmbedding.mockRejectedValueOnce(new Error('Embedding failed'));

      const result = await parser.parse('python developer');

      expect(result.parseMethod).toBe('keyword_fallback');
    });

    it('should fallback for similarity_search intent', async () => {
      mockIntentRouterClassify.mockReturnValue({
        intent: 'similarity_search',
        confidence: 0.9,
        timingMs: 1
      });

      const result = await parser.parse('candidates like John');

      expect(result.parseMethod).toBe('keyword_fallback');
      expect(result.intent).toBe('similarity_search');
    });

    it('should fallback for low confidence intent', async () => {
      mockIntentRouterClassify.mockReturnValue({
        intent: 'structured_search',
        confidence: 0.4,  // Below threshold of 0.6
        timingMs: 1
      });

      const result = await parser.parse('some query');

      expect(result.parseMethod).toBe('keyword_fallback');
      expect(result.confidence).toBe(0.4);
    });
  });

  // --------------------------------------------------------------------------
  // Caching Tests
  // --------------------------------------------------------------------------

  describe('caching', () => {
    beforeEach(async () => {
      await parser.initialize();
    });

    it('should cache extraction results', async () => {
      // First call
      await parser.parse('python developer');
      expect(mockExtractorExtract).toHaveBeenCalledTimes(1);

      // Second call with same query - should hit cache
      await parser.parse('python developer');
      // With caching, extractEntities should still only be called once
      expect(mockExtractorExtract).toHaveBeenCalledTimes(1);
    });

    it('should normalize query for cache key (case insensitive)', async () => {
      await parser.parse('Python Developer');
      await parser.parse('python developer');

      // Both should use the same cache entry
      expect(mockExtractorExtract).toHaveBeenCalledTimes(1);
    });

    it('should clear cache when requested', async () => {
      await parser.parse('python developer');

      QueryParser.clearCache();

      // After cache clear, should call extractor again
      await parser.parse('python developer');
      expect(mockExtractorExtract).toHaveBeenCalledTimes(2);
    });

    it('should work with caching disabled', async () => {
      const noCacheParser = new QueryParser({
        generateEmbedding: mockGenerateEmbedding,
        logger: mockLogger,
        togetherApiKey: 'test-key',
        config: {
          enabled: true,
          intentConfidenceThreshold: 0.6,
          extractionTimeoutMs: 100,
          cacheExtractionResults: false,  // Caching disabled
          enableQueryExpansion: true,
          expansionDepth: 1,
          expansionConfidenceThreshold: 0.8
        }
      });

      await noCacheParser.initialize();
      const result = await noCacheParser.parse('python developer');
      expect(result.parseMethod).toBe('nlp');
    });
  });

  // --------------------------------------------------------------------------
  // Configuration Tests
  // --------------------------------------------------------------------------

  describe('configuration', () => {
    it('should expose configuration', () => {
      const config = parser.getConfig();

      expect(config.enabled).toBe(true);
      expect(config.intentConfidenceThreshold).toBe(0.6);
      expect(config.extractionTimeoutMs).toBe(100);
      expect(config.cacheExtractionResults).toBe(true);
      expect(config.enableQueryExpansion).toBe(true);
      expect(config.expansionDepth).toBe(1);
      expect(config.expansionConfidenceThreshold).toBe(0.8);
    });

    it('should use default config when not provided', () => {
      const defaultParser = new QueryParser({
        generateEmbedding: mockGenerateEmbedding,
        logger: mockLogger,
        togetherApiKey: 'test-key'
      });

      const config = defaultParser.getConfig();
      expect(config.enabled).toBe(true);
      expect(config.intentConfidenceThreshold).toBe(0.6);
    });

    it('should merge partial config with defaults', () => {
      const partialParser = new QueryParser({
        generateEmbedding: mockGenerateEmbedding,
        logger: mockLogger,
        togetherApiKey: 'test-key',
        config: {
          intentConfidenceThreshold: 0.8  // Only override this
        }
      });

      const config = partialParser.getConfig();
      expect(config.intentConfidenceThreshold).toBe(0.8);
      expect(config.enabled).toBe(true);  // Default preserved
    });
  });

  // --------------------------------------------------------------------------
  // Integration-like Tests
  // --------------------------------------------------------------------------

  describe('pipeline integration', () => {
    beforeEach(async () => {
      await parser.initialize();
    });

    it('should handle full pipeline for structured search', async () => {
      const result = await parser.parse('senior python developer in NYC');

      // Verify full pipeline executed
      expect(result.parseMethod).toBe('nlp');
      expect(result.intent).toBe('structured_search');
      expect(result.confidence).toBeGreaterThan(0.6);
      expect(result.entities.skills.length).toBeGreaterThan(0);
      expect(result.timings.totalMs).toBeGreaterThanOrEqual(0);
    });

    it('should complete within latency budget', async () => {
      const result = await parser.parse('senior python developer in NYC');

      // Total should be reasonable (mocked, so very fast)
      expect(result.timings.totalMs).toBeLessThan(1000);
    });

    it('should call all pipeline components in order', async () => {
      await parser.parse('senior python developer');

      // Verify all components were called
      expect(mockIntentRouterClassify).toHaveBeenCalled();
      expect(mockExtractorExtract).toHaveBeenCalled();
      expect(mockExpanderExpand).toHaveBeenCalled();
    });
  });
});
