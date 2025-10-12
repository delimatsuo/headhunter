import Redis, { Cluster, type ClusterNode, type ClusterOptions, type RedisOptions } from 'ioredis';
import type { Logger } from 'pino';

import type { RedisCacheConfig } from './config';

export interface RedisHealthStatus {
  status: 'healthy' | 'degraded' | 'disabled' | 'unavailable';
  latencyMs?: number;
  message?: string;
}

export class SearchRedisClient {
  private client: Redis | Cluster | null = null;

  constructor(private readonly config: RedisCacheConfig, private readonly logger: Logger) {
    if (config.disable) {
      this.logger.warn('Redis caching disabled via configuration.');
    }
  }

  private createClient(): Redis | Cluster | null {
    if (this.config.disable) {
      return null;
    }

    if (this.client) {
      return this.client;
    }

    const hosts = this.config.host.split(',').map((value) => value.trim()).filter(Boolean);
    const tlsOptions = this.config.tls
      ? (() => {
          const options: Record<string, unknown> = {
            rejectUnauthorized: this.config.tlsRejectUnauthorized
          };
          if (this.config.caCert) {
            options.ca = [this.config.caCert];
          }
          return options;
        })()
      : undefined;

    if (hosts.length > 1) {
      const nodes: ClusterNode[] = hosts.map((host) => ({ host, port: this.config.port }));
      const options: ClusterOptions = {
        redisOptions: {
          password: this.config.password,
          tls: tlsOptions
        }
      };
      this.logger.info({ tls: tlsOptions ?? null, cluster: true }, 'Initializing Redis cluster client.');
      this.client = new Cluster(nodes, options);
    } else {
      const options: RedisOptions = {
        host: hosts[0] ?? this.config.host,
        port: this.config.port,
        password: this.config.password,
        tls: tlsOptions
      };
      this.logger.info({ tls: tlsOptions ?? null, cluster: false, host: options.host, port: options.port }, 'Initializing Redis client.');
      this.client = new Redis(options);
    }

    this.client.on('error', (error) => {
      this.logger.error({ error }, 'Redis connection error.');
    });

    this.client.on('reconnecting', () => {
      this.logger.warn('Redis reconnecting.');
    });

    this.client.on('ready', () => {
      this.logger.info('Redis client connection ready.');
    });

    this.client.on('connect', () => {
      this.logger.info('Redis client connected.');
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
      this.logger.error({ error, key }, 'Failed to read from Redis.');
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
      this.logger.error({ error, key }, 'Failed to write to Redis.');
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
      this.logger.warn({ error, key }, 'Failed to delete Redis key.');
    }
  }

  buildHybridKey(tenantId: string, cacheToken: string): string {
    return `${this.config.keyPrefix}:${tenantId}:${cacheToken}`;
  }

  buildEmbeddingKey(tenantId: string, cacheToken: string): string {
    return `${this.config.keyPrefix}:embedding:${tenantId}:${cacheToken}`;
  }

  isDisabled(): boolean {
    return this.config.disable;
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
      const latency = Date.now() - start;
      if (response?.toString().toUpperCase() === 'PONG') {
        return { status: 'healthy', latencyMs: latency } satisfies RedisHealthStatus;
      }
      return { status: 'degraded', latencyMs: latency, message: 'Unexpected ping response.' } satisfies RedisHealthStatus;
    } catch (error) {
      this.logger.error({ error }, 'Redis ping failed.');
      return { status: 'degraded', message: error instanceof Error ? error.message : 'Unknown error' } satisfies RedisHealthStatus;
    }
  }

  async close(): Promise<void> {
    if (!this.client) {
      return;
    }

    try {
      if (this.client instanceof Cluster) {
        await this.client.quit();
      } else {
        await this.client.quit();
      }
    } catch (error) {
      this.logger.warn({ error }, 'Failed to close Redis connection cleanly.');
    } finally {
      this.client = null;
    }
  }
}
