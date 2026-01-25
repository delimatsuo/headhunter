import { describe, it, expect, vi, beforeEach } from 'vitest';
import { IntentRouter, classifyIntent } from '../intent-router';
import { cosineSimilarity, averageEmbeddings } from '../vector-utils';
import type { Logger } from 'pino';

// Mock logger
const mockLogger = {
  info: vi.fn(),
  debug: vi.fn(),
  trace: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
  child: vi.fn().mockReturnThis()
} as unknown as Logger;

// Mock embedding generator - returns deterministic embeddings
function createMockEmbeddingGenerator(dimension = 768) {
  return async (text: string): Promise<number[]> => {
    // Create deterministic embedding based on text hash
    const hash = text.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
    const embedding = new Array(dimension).fill(0);
    for (let i = 0; i < dimension; i++) {
      embedding[i] = Math.sin(hash * (i + 1) * 0.001);
    }
    return embedding;
  };
}

describe('vector-utils', () => {
  describe('cosineSimilarity', () => {
    it('should return 1 for identical vectors', () => {
      const vector = [1, 2, 3, 4, 5];
      expect(cosineSimilarity(vector, vector)).toBeCloseTo(1.0);
    });

    it('should return 0 for orthogonal vectors', () => {
      const a = [1, 0, 0];
      const b = [0, 1, 0];
      expect(cosineSimilarity(a, b)).toBeCloseTo(0.0);
    });

    it('should return -1 for opposite vectors', () => {
      const a = [1, 2, 3];
      const b = [-1, -2, -3];
      expect(cosineSimilarity(a, b)).toBeCloseTo(-1.0);
    });

    it('should throw on mismatched lengths', () => {
      expect(() => cosineSimilarity([1, 2], [1, 2, 3])).toThrow('Vector length mismatch');
    });

    it('should handle zero vectors', () => {
      const zero = [0, 0, 0];
      const other = [1, 2, 3];
      expect(cosineSimilarity(zero, other)).toBe(0);
    });
  });

  describe('averageEmbeddings', () => {
    it('should return same vector for single embedding', () => {
      const embedding = [1, 2, 3];
      const result = averageEmbeddings([embedding]);
      expect(result).toEqual([1, 2, 3]);
    });

    it('should compute average correctly', () => {
      const embeddings = [
        [0, 2, 4],
        [2, 4, 6],
        [4, 6, 8]
      ];
      const result = averageEmbeddings(embeddings);
      expect(result).toEqual([2, 4, 6]);
    });

    it('should throw on empty array', () => {
      expect(() => averageEmbeddings([])).toThrow('Cannot average empty embeddings array');
    });

    it('should throw on mismatched dimensions', () => {
      const embeddings = [
        [1, 2, 3],
        [1, 2]
      ];
      expect(() => averageEmbeddings(embeddings)).toThrow('Embedding dimension mismatch');
    });
  });
});

describe('IntentRouter', () => {
  let router: IntentRouter;
  let mockGenerateEmbedding: ReturnType<typeof createMockEmbeddingGenerator>;

  beforeEach(() => {
    vi.clearAllMocks();
    mockGenerateEmbedding = createMockEmbeddingGenerator();
    router = new IntentRouter(
      { generateEmbedding: mockGenerateEmbedding, logger: mockLogger },
      0.5  // Lower threshold for testing
    );
  });

  describe('initialization', () => {
    it('should initialize route embeddings', async () => {
      await router.initialize();
      expect(router.isInitialized()).toBe(true);
    });

    it('should compute embeddings for all routes', async () => {
      await router.initialize();

      expect(router.getRouteEmbedding('structured_search')).toBeDefined();
      expect(router.getRouteEmbedding('similarity_search')).toBeDefined();
      expect(router.getRouteEmbedding('keyword_fallback')).toBeDefined();
    });

    it('should handle concurrent initialization calls', async () => {
      const promises = [
        router.initialize(),
        router.initialize(),
        router.initialize()
      ];

      await Promise.all(promises);
      expect(router.isInitialized()).toBe(true);
    });

    it('should not re-initialize after success', async () => {
      await router.initialize();
      const firstEmbedding = router.getRouteEmbedding('structured_search');

      await router.initialize();
      const secondEmbedding = router.getRouteEmbedding('structured_search');

      expect(firstEmbedding).toBe(secondEmbedding);
    });
  });

  describe('classifyIntent', () => {
    beforeEach(async () => {
      await router.initialize();
    });

    it('should throw if not initialized', () => {
      const uninitializedRouter = new IntentRouter(
        { generateEmbedding: mockGenerateEmbedding, logger: mockLogger }
      );

      expect(() => uninitializedRouter.classifyIntent([1, 2, 3])).toThrow('not initialized');
    });

    it('should return classification with confidence', async () => {
      const queryEmbedding = await mockGenerateEmbedding('senior python developer');
      const result = router.classifyIntent(queryEmbedding);

      expect(result).toHaveProperty('intent');
      expect(result).toHaveProperty('confidence');
      expect(result).toHaveProperty('timingMs');
      expect(typeof result.confidence).toBe('number');
      expect(result.confidence).toBeGreaterThanOrEqual(0);
      expect(result.confidence).toBeLessThanOrEqual(1);
    });

    it('should classify quickly (under 5ms for similarity calculation)', async () => {
      const queryEmbedding = await mockGenerateEmbedding('test query');
      const result = router.classifyIntent(queryEmbedding);

      // Classification should be very fast (just cosine similarity)
      expect(result.timingMs).toBeLessThan(5);
    });

    it('should fall back to keyword_fallback for low confidence', async () => {
      // Create a query that produces a low-confidence classification
      const router2 = new IntentRouter(
        { generateEmbedding: mockGenerateEmbedding, logger: mockLogger },
        0.99  // Very high threshold
      );
      await router2.initialize();

      const queryEmbedding = await mockGenerateEmbedding('random gibberish xyz');
      const result = router2.classifyIntent(queryEmbedding);

      expect(result.intent).toBe('keyword_fallback');
    });

    it('should clamp confidence to [0, 1]', async () => {
      const queryEmbedding = await mockGenerateEmbedding('test');
      const result = router.classifyIntent(queryEmbedding);

      expect(result.confidence).toBeGreaterThanOrEqual(0);
      expect(result.confidence).toBeLessThanOrEqual(1);
    });
  });

  describe('classifyIntent helper function', () => {
    beforeEach(async () => {
      await router.initialize();
    });

    it('should work with helper function', async () => {
      const queryEmbedding = await mockGenerateEmbedding('python developer');
      const result = classifyIntent(router, queryEmbedding);

      expect(result).toHaveProperty('intent');
      expect(result).toHaveProperty('confidence');
    });
  });
});
