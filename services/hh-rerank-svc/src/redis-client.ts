import Redis, { Cluster, type ClusterNode, type ClusterOptions, type RedisOptions } from 'ioredis';
import type { Logger } from 'pino';

import type { RerankRedisConfig } from './config.js';
import type { RerankCacheDescriptor } from './types.js';

export interface RedisHealthStatus {
  status: 'healthy' | 'degraded' | 'disabled' | 'unavailable';
  latencyMs?: number;
  message?: string;
}

export class RerankRedisClient {
  private client: Redis | Cluster | null = null;

  constructor(private readonly config: RerankRedisConfig, private readonly logger: Logger) {
    if (this.config.disable) {
      this.logger.warn('Rerank Redis caching disabled via configuration.');
    }
  }

  private createClient(): Redis | Cluster | null {
    if (this.config.disable) {
      return null;
    }

    if (this.client) {
      return this.client;
    }

    const hosts = this.config.host
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean);

    if (hosts.length > 1) {
      const nodes: ClusterNode[] = hosts.map((host) => ({ host, port: this.config.port }));
      const clusterOptions: ClusterOptions = {
        redisOptions: {
          password: this.config.password,
          tls: this.config.tls ? {} : undefined
        }
      };
      this.client = new Cluster(nodes, clusterOptions);
    } else {
      const redisOptions: RedisOptions = {
        host: hosts[0] ?? this.config.host,
        port: this.config.port,
        password: this.config.password,
        tls: this.config.tls ? {} : undefined
      };
      this.client = new Redis(redisOptions);
    }

    this.client.on('error', (error) => {
      this.logger.error({ error }, 'Redis connection error.');
    });

    this.client.on('reconnecting', () => {
      this.logger.warn('Redis reconnecting for rerank cache.');
    });

    return this.client;
  }

  async get<T>(key: string): Promise<T | null> {
    const client = this.createClient();
    if (!client) {
      return null;
    }

    try {
      const raw = await client.get(key);
      if (!raw) {
        return null;
      }
      return JSON.parse(raw) as T;
    } catch (error) {
      this.logger.error({ error, key }, 'Failed to read rerank cache entry.');
      return null;
    }
  }

  async set<T>(key: string, value: T, ttlSeconds?: number): Promise<void> {
    const client = this.createClient();
    if (!client) {
      return;
    }

    const ttl = ttlSeconds ?? this.config.ttlSeconds;

    try {
      const payload = JSON.stringify(value);
      if (ttl > 0) {
        await client.setex(key, ttl, payload);
      } else {
        await client.set(key, payload);
      }
    } catch (error) {
      this.logger.error({ error, key }, 'Failed to write rerank cache entry.');
    }
  }

  async delete(key: string): Promise<void> {
    const client = this.createClient();
    if (!client) {
      return;
    }

    try {
      await client.del(key);
    } catch (error) {
      this.logger.warn({ error, key }, 'Failed to delete rerank cache entry.');
    }
  }

  buildKey(tenantId: string, descriptor: RerankCacheDescriptor): string {
    return `${this.config.keyPrefix}:${tenantId}:${descriptor.jdHash}:${descriptor.docsetHash}`;
  }

  async healthCheck(): Promise<RedisHealthStatus> {
    if (this.config.disable) {
      return { status: 'disabled', message: 'Caching disabled via configuration.' } satisfies RedisHealthStatus;
    }

    const client = this.createClient();
    if (!client) {
      return { status: 'unavailable', message: 'Redis client not configured.' } satisfies RedisHealthStatus;
    }

    const start = Date.now();

    try {
      const response = await client.ping();
      const latencyMs = Date.now() - start;
      if (response?.toString().toUpperCase() === 'PONG') {
        return { status: 'healthy', latencyMs } satisfies RedisHealthStatus;
      }
      return { status: 'degraded', latencyMs, message: 'Unexpected Redis ping response.' } satisfies RedisHealthStatus;
    } catch (error) {
      this.logger.error({ error }, 'Redis ping failed for rerank cache.');
      return {
        status: 'degraded',
        message: error instanceof Error ? error.message : 'Unknown error'
      } satisfies RedisHealthStatus;
    }
  }

  async close(): Promise<void> {
    if (!this.client) {
      return;
    }

    try {
      await this.client.quit();
    } catch (error) {
      this.logger.warn({ error }, 'Failed to close Redis connection cleanly.');
    } finally {
      this.client = null;
    }
  }
}
