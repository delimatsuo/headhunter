import Redis, { Cluster, type ClusterNode, type ClusterOptions, type RedisOptions } from 'ioredis';
import type { Logger } from 'pino';

import type { EcoRedisConfig } from './config.js';
import type { OccupationCacheEntry, OccupationDetailResponse, OccupationSearchResponse } from './types.js';

export class EcoRedisClient {
  private client: Redis | Cluster | null = null;

  constructor(private readonly config: EcoRedisConfig, private readonly logger: Logger) {
    if (config.disable) {
      this.logger.warn('ECO caching disabled via configuration flag.');
    }
  }

  private ensureClient(): Redis | Cluster | null {
    if (this.config.disable) {
      return null;
    }

    if (this.client) {
      return this.client;
    }

    const hosts = this.config.host.split(',').map((host) => host.trim()).filter(Boolean);
    if (hosts.length > 1) {
      const nodes: ClusterNode[] = hosts.map((host) => ({ host, port: this.config.port }));
      const options: ClusterOptions = {
        redisOptions: {
          password: this.config.password,
          tls: this.config.tls ? {} : undefined
        }
      };
      this.client = new Cluster(nodes, options);
    } else {
      const options: RedisOptions = {
        host: hosts[0] ?? this.config.host,
        port: this.config.port,
        password: this.config.password,
        tls: this.config.tls ? {} : undefined
      };
      this.client = new Redis(options);
    }

    this.client.on('error', (error) => {
      this.logger.error({ error }, 'Redis error from ECO client.');
    });

    this.client.on('reconnecting', () => {
      this.logger.warn('Redis ECO client reconnecting.');
    });

    return this.client;
  }

  private buildSearchKey(tenantId: string, normalizedQuery: string): string {
    return `${this.config.searchKeyPrefix}:${tenantId}:${normalizedQuery}`;
  }

  private buildOccupationKey(tenantId: string, ecoId: string, locale: string, country: string): string {
    return `${this.config.occupationKeyPrefix}:${tenantId}:${ecoId}:${locale}:${country}`;
  }

  async readSearch(tenantId: string, normalizedQuery: string): Promise<OccupationCacheEntry<OccupationSearchResponse> | null> {
    const client = this.ensureClient();
    if (!client) {
      return null;
    }

    const key = this.buildSearchKey(tenantId, normalizedQuery);
    try {
      const raw = await client.get(key);
      return raw ? (JSON.parse(raw) as OccupationCacheEntry<OccupationSearchResponse>) : null;
    } catch (error) {
      this.logger.error({ error, tenantId, key }, 'Failed to read ECO search cache.');
      return null;
    }
  }

  async writeSearch(
    tenantId: string,
    normalizedQuery: string,
    entry: OccupationCacheEntry<OccupationSearchResponse>
  ): Promise<void> {
    const client = this.ensureClient();
    if (!client) {
      return;
    }

    const key = this.buildSearchKey(tenantId, normalizedQuery);
    try {
      await client.setex(key, this.config.searchTtlSeconds, JSON.stringify(entry));
    } catch (error) {
      this.logger.error({ error, tenantId, key }, 'Failed to write ECO search cache.');
    }
  }

  async readOccupation(
    tenantId: string,
    ecoId: string,
    locale: string,
    country: string
  ): Promise<OccupationCacheEntry<OccupationDetailResponse> | null> {
    const client = this.ensureClient();
    if (!client) {
      return null;
    }

    const key = this.buildOccupationKey(tenantId, ecoId, locale, country);
    try {
      const raw = await client.get(key);
      return raw ? (JSON.parse(raw) as OccupationCacheEntry<OccupationDetailResponse>) : null;
    } catch (error) {
      this.logger.error({ error, tenantId, ecoId, locale, country, key }, 'Failed to read ECO occupation cache.');
      return null;
    }
  }

  async writeOccupation(
    tenantId: string,
    ecoId: string,
    locale: string,
    country: string,
    entry: OccupationCacheEntry<OccupationDetailResponse>
  ): Promise<void> {
    const client = this.ensureClient();
    if (!client) {
      return;
    }

    const key = this.buildOccupationKey(tenantId, ecoId, locale, country);
    try {
      await client.setex(key, this.config.occupationTtlSeconds, JSON.stringify(entry));
    } catch (error) {
      this.logger.error({ error, tenantId, ecoId, locale, country, key }, 'Failed to write ECO occupation cache.');
    }
  }

  async invalidateOccupation(tenantId: string, ecoId: string, locale: string, country: string): Promise<void> {
    const client = this.ensureClient();
    if (!client) {
      return;
    }

    const key = this.buildOccupationKey(tenantId, ecoId, locale, country);
    try {
      await client.del(key);
    } catch (error) {
      this.logger.warn({ error, tenantId, ecoId, locale, country, key }, 'Failed to invalidate ECO occupation cache.');
    }
  }

  async healthCheck(): Promise<{ status: 'healthy' | 'degraded' | 'disabled' | 'unavailable'; latencyMs?: number; message?: string }> {
    if (this.config.disable) {
      return { status: 'disabled', message: 'ECO cache disabled.' };
    }

    const client = this.ensureClient();
    if (!client) {
      return { status: 'unavailable', message: 'Redis client unavailable.' };
    }

    const start = Date.now();
    try {
      const result = await client.ping();
      const latencyMs = Date.now() - start;
      if (typeof result === 'string' && result.toUpperCase() === 'PONG') {
        return { status: 'healthy', latencyMs };
      }
      return { status: 'degraded', latencyMs, message: 'Unexpected ping response.' };
    } catch (error) {
      this.logger.error({ error }, 'ECO Redis health check failed.');
      return { status: 'degraded', message: error instanceof Error ? error.message : 'Unknown error' };
    }
  }

  async close(): Promise<void> {
    if (!this.client) {
      return;
    }

    try {
      await this.client.quit();
    } catch (error) {
      this.logger.warn({ error }, 'Failed to close ECO Redis client.');
    } finally {
      this.client = null;
    }
  }
}
