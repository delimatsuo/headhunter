import type { Logger } from 'pino';
import type { SearchRedisClient } from './redis-client';
import type { RedisCacheConfig } from './config';

/**
 * Cache layer configuration with TTL and invalidation strategy.
 */
export interface CacheLayerConfig {
  /** Base TTL in seconds */
  ttlSeconds: number;
  /** Whether to use TTL jitter */
  useJitter: boolean;
  /** Key prefix for this layer */
  keyPrefix: string;
}

/**
 * Predefined cache layers with recommended TTLs.
 * Based on research: different data types have different staleness tolerance.
 */
export const CacheLayers = {
  SEARCH_RESULTS: {
    ttlSeconds: 600,      // 10 minutes - balance freshness vs hit rate
    useJitter: true,
    keyPrefix: 'search'
  },
  RERANK_SCORES: {
    ttlSeconds: 21600,    // 6 hours - expensive to compute, rarely changes
    useJitter: true,
    keyPrefix: 'rerank'
  },
  SPECIALTY_LOOKUP: {
    ttlSeconds: 86400,    // 24 hours - static reference data
    useJitter: false,
    keyPrefix: 'specialty'
  },
  EMBEDDING: {
    ttlSeconds: 3600,     // 1 hour - query embeddings
    useJitter: true,
    keyPrefix: 'embedding'
  }
} as const satisfies Record<string, CacheLayerConfig>;

export type CacheLayerName = keyof typeof CacheLayers;

/**
 * Create cache layers with configuration from environment.
 */
export function createCacheLayers(config: RedisCacheConfig): Record<CacheLayerName, CacheLayerConfig> {
  return {
    SEARCH_RESULTS: {
      ttlSeconds: config.searchResultsTtlSeconds,
      useJitter: true,
      keyPrefix: 'search'
    },
    RERANK_SCORES: {
      ttlSeconds: config.rerankScoresTtlSeconds,
      useJitter: true,
      keyPrefix: 'rerank'
    },
    SPECIALTY_LOOKUP: {
      ttlSeconds: config.specialtyLookupTtlSeconds,
      useJitter: false,
      keyPrefix: 'specialty'
    },
    EMBEDDING: {
      ttlSeconds: config.embeddingTtlSeconds,
      useJitter: true,
      keyPrefix: 'embedding'
    }
  };
}

/**
 * Multi-layer cache strategy for search operations.
 * Each layer has its own TTL and invalidation strategy.
 */
export class CacheStrategy {
  constructor(
    private readonly redisClient: SearchRedisClient,
    private readonly logger: Logger
  ) {}

  /**
   * Build a cache key for a specific layer with tenant isolation.
   */
  buildKey(layer: CacheLayerName, tenantId: string, identifier: string): string {
    const config = CacheLayers[layer];
    return `hh:${config.keyPrefix}:${tenantId}:${identifier}`;
  }

  /**
   * Get a value from a specific cache layer.
   */
  async get<T>(layer: CacheLayerName, tenantId: string, identifier: string): Promise<T | null> {
    if (this.redisClient.isDisabled()) {
      return null;
    }

    const key = this.buildKey(layer, tenantId, identifier);
    const value = await this.redisClient.get<T>(key);

    this.logger.debug(
      { layer, tenantId, hit: value !== null },
      'Cache lookup'
    );

    return value;
  }

  /**
   * Set a value in a specific cache layer with appropriate TTL.
   */
  async set<T>(layer: CacheLayerName, tenantId: string, identifier: string, value: T): Promise<void> {
    if (this.redisClient.isDisabled()) {
      return;
    }

    const config = CacheLayers[layer];
    const key = this.buildKey(layer, tenantId, identifier);

    if (config.useJitter) {
      await this.redisClient.setWithJitter(key, value, config.ttlSeconds);
    } else {
      await this.redisClient.set(key, value, config.ttlSeconds);
    }

    this.logger.debug(
      { layer, tenantId, ttl: config.ttlSeconds, jitter: config.useJitter },
      'Cache set'
    );
  }

  /**
   * Invalidate a specific cache entry.
   */
  async invalidate(layer: CacheLayerName, tenantId: string, identifier: string): Promise<void> {
    if (this.redisClient.isDisabled()) {
      return;
    }

    const key = this.buildKey(layer, tenantId, identifier);
    await this.redisClient.delete(key);

    this.logger.debug({ layer, tenantId, key }, 'Cache invalidated');
  }

  /**
   * Invalidate all cache entries for a tenant in a specific layer.
   * Note: This uses SCAN which can be expensive - use sparingly.
   */
  async invalidateTenantLayer(layer: CacheLayerName, tenantId: string): Promise<number> {
    if (this.redisClient.isDisabled()) {
      return 0;
    }

    const config = CacheLayers[layer];
    const pattern = `hh:${config.keyPrefix}:${tenantId}:*`;

    // Get all matching keys (note: this can be expensive)
    const keys = await this.redisClient.scanKeys(pattern);
    if (keys.length === 0) {
      return 0;
    }

    // Delete in batches
    for (const key of keys) {
      await this.redisClient.delete(key);
    }

    this.logger.info(
      { layer, tenantId, keysDeleted: keys.length },
      'Tenant cache layer invalidated'
    );

    return keys.length;
  }
}
