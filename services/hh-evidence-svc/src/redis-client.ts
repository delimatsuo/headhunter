import Redis, { Cluster, type ClusterNode, type ClusterOptions, type RedisOptions } from 'ioredis';
import type { Logger } from 'pino';

import type { EvidenceCacheEntry } from './types';
import type { EvidenceRedisConfig } from './config';

export class EvidenceRedisClient {
  private client: Redis | Cluster | null = null;

  constructor(private readonly config: EvidenceRedisConfig, private readonly logger: Logger) {
    if (config.disable) {
      this.logger.warn('Evidence caching disabled via configuration flag.');
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
      this.logger.error({ error }, 'Redis error from evidence client.');
    });

    this.client.on('reconnecting', () => {
      this.logger.warn('Redis evidence client reconnecting.');
    });

    return this.client;
  }

  private computeKey(tenantId: string, candidateId: string): string {
    return `${this.config.keyPrefix}:${tenantId}:${candidateId}`;
  }

  async read(tenantId: string, candidateId: string): Promise<EvidenceCacheEntry | null> {
    const client = this.ensureClient();
    if (!client) {
      return null;
    }

    const key = this.computeKey(tenantId, candidateId);
    try {
      const raw = await client.get(key);
      if (!raw) {
        return null;
      }
      return JSON.parse(raw) as EvidenceCacheEntry;
    } catch (error) {
      this.logger.error({ error, tenantId, candidateId }, 'Failed to read candidate evidence cache.');
      return null;
    }
  }

  async write(
    tenantId: string,
    candidateId: string,
    entry: EvidenceCacheEntry,
    ttlSeconds?: number
  ): Promise<void> {
    const client = this.ensureClient();
    if (!client) {
      return;
    }

    const key = this.computeKey(tenantId, candidateId);
    const payload = JSON.stringify(entry);
    const ttl = ttlSeconds ?? this.config.ttlSeconds;

    try {
      if (ttl > 0) {
        await client.setex(key, ttl, payload);
      } else {
        await client.set(key, payload);
      }
    } catch (error) {
      this.logger.error({ error, tenantId, candidateId }, 'Failed to write candidate evidence cache.');
    }
  }

  async stage(
    tenantId: string,
    candidateId: string,
    entry: EvidenceCacheEntry
  ): Promise<void> {
    const ttl = this.config.ttlSeconds + this.config.staleWhileRevalidateSeconds;
    await this.write(tenantId, candidateId, entry, ttl);
  }

  async invalidate(tenantId: string, candidateId: string): Promise<void> {
    const client = this.ensureClient();
    if (!client) {
      return;
    }

    const key = this.computeKey(tenantId, candidateId);
    try {
      await client.del(key);
    } catch (error) {
      this.logger.warn({ error, tenantId, candidateId }, 'Failed to invalidate candidate cache entry.');
    }
  }

  async healthCheck(): Promise<{ status: 'healthy' | 'degraded' | 'disabled' | 'unavailable'; latencyMs?: number; message?: string }> {
    if (this.config.disable) {
      return { status: 'disabled', message: 'Evidence cache disabled.' };
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
      this.logger.error({ error }, 'Redis health check failed.');
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
      this.logger.warn({ error }, 'Failed to close Redis evidence client.');
    } finally {
      this.client = null;
    }
  }
}
