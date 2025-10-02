import Redis, { Cluster, type ClusterNode, type ClusterOptions } from 'ioredis';
import type { Logger } from 'pino';

import type { MsgsRedisConfig } from './config';
import type {
  MarketDemandResponse,
  MsgsCacheEntry,
  RoleTemplateResponse,
  SkillExpandResponse
} from './types';

export class MsgsRedisClient {
  private client: Redis | Cluster | null = null;

  constructor(private readonly config: MsgsRedisConfig, private readonly logger: Logger) {
    if (config.disable) {
      this.logger.warn('MSGS caching disabled by configuration.');
    }
  }

  private ensureClient(): Redis | Cluster | null {
    if (this.config.disable) {
      return null;
    }

    if (this.client) {
      return this.client;
    }

    const urls = this.config.url.split(',').map((value) => value.trim()).filter(Boolean);
    const parsedUrls = urls.map((url) => {
      const normalized = url.startsWith('redis://') || url.startsWith('rediss://') ? url : `redis://${url}`;
      return new URL(normalized);
    });

    if (parsedUrls.length > 1) {
      const nodes: ClusterNode[] = parsedUrls.map((urlObj) => ({
        host: urlObj.hostname,
        port: Number(urlObj.port || '6379')
      }));

      const redisOptions: ClusterOptions['redisOptions'] = {
        tls: this.config.tls ? {} : undefined,
        keyPrefix: `${this.config.keyPrefix}:`
      };

      const usernames = Array.from(new Set(parsedUrls.map((urlObj) => urlObj.username).filter((value) => value)));
      const passwords = Array.from(new Set(parsedUrls.map((urlObj) => urlObj.password).filter((value) => value)));

      if (usernames.length > 1 || passwords.length > 1) {
        this.logger.warn('Multiple Redis credentials detected across MSGS cluster URLs. Using the first value.');
      }

      if (usernames[0]) {
        redisOptions.username = decodeURIComponent(usernames[0]);
      }

      if (passwords[0]) {
        redisOptions.password = decodeURIComponent(passwords[0]);
      }

      this.client = new Cluster(nodes, { redisOptions });
    } else {
      const url = parsedUrls[0] ?? new URL(this.config.url.startsWith('redis://') || this.config.url.startsWith('rediss://')
        ? this.config.url
        : `redis://${this.config.url}`);

      this.client = new Redis(url.toString(), {
        tls: this.config.tls ? {} : undefined,
        keyPrefix: `${this.config.keyPrefix}:`,
        username: url.username ? decodeURIComponent(url.username) : undefined,
        password: url.password ? decodeURIComponent(url.password) : undefined
      });
    }

    this.client.on('error', (error) => {
      this.logger.error({ error }, 'MSGS Redis error.');
    });

    this.client.on('reconnecting', () => {
      this.logger.warn('MSGS Redis client reconnecting.');
    });

    return this.client;
  }

  private buildSkillKey(tenantId: string, skillId: string, fingerprint: string): string {
    return `skills:${tenantId}:${skillId}:${fingerprint}`;
  }

  private buildRoleKey(tenantId: string, ecoId: string, locale: string): string {
    return `roles:${tenantId}:${ecoId}:${locale}`;
  }

  private buildDemandKey(tenantId: string, skillId: string, region: string, industry?: string): string {
    return industry
      ? `demand:${tenantId}:${skillId}:${region}:${industry}`
      : `demand:${tenantId}:${skillId}:${region}`;
  }

  async readSkillExpansion(
    tenantId: string,
    skillId: string,
    fingerprint: string
  ): Promise<MsgsCacheEntry<SkillExpandResponse> | null> {
    const client = this.ensureClient();
    if (!client) {
      return null;
    }

    const key = this.buildSkillKey(tenantId, skillId, fingerprint);
    try {
      const raw = await client.get(key);
      return raw ? (JSON.parse(raw) as MsgsCacheEntry<SkillExpandResponse>) : null;
    } catch (error) {
      this.logger.error({ error, tenantId, skillId }, 'Failed to read MSGS skill expansion cache.');
      return null;
    }
  }

  async writeSkillExpansion(
    tenantId: string,
    skillId: string,
    fingerprint: string,
    entry: MsgsCacheEntry<SkillExpandResponse>
  ): Promise<void> {
    const client = this.ensureClient();
    if (!client) {
      return;
    }

    const key = this.buildSkillKey(tenantId, skillId, fingerprint);
    try {
      await client.setex(key, this.config.skillTtlSeconds, JSON.stringify(entry));
    } catch (error) {
      this.logger.error({ error, tenantId, skillId }, 'Failed to write MSGS skill expansion cache.');
    }
  }

  async readRoleTemplate(
    tenantId: string,
    ecoId: string,
    locale: string
  ): Promise<MsgsCacheEntry<RoleTemplateResponse> | null> {
    const client = this.ensureClient();
    if (!client) {
      return null;
    }

    const key = this.buildRoleKey(tenantId, ecoId, locale);
    try {
      const raw = await client.get(key);
      return raw ? (JSON.parse(raw) as MsgsCacheEntry<RoleTemplateResponse>) : null;
    } catch (error) {
      this.logger.error({ error, tenantId, ecoId, locale }, 'Failed to read MSGS role template cache.');
      return null;
    }
  }

  async writeRoleTemplate(
    tenantId: string,
    ecoId: string,
    locale: string,
    entry: MsgsCacheEntry<RoleTemplateResponse>
  ): Promise<void> {
    const client = this.ensureClient();
    if (!client) {
      return;
    }

    const key = this.buildRoleKey(tenantId, ecoId, locale);
    try {
      await client.setex(key, this.config.roleTtlSeconds, JSON.stringify(entry));
    } catch (error) {
      this.logger.error({ error, tenantId, ecoId, locale }, 'Failed to write MSGS role template cache.');
    }
  }

  async readDemand(
    tenantId: string,
    skillId: string,
    region: string,
    industry?: string
  ): Promise<MsgsCacheEntry<MarketDemandResponse> | null> {
    const client = this.ensureClient();
    if (!client) {
      return null;
    }

    const key = this.buildDemandKey(tenantId, skillId, region, industry);
    try {
      const raw = await client.get(key);
      return raw ? (JSON.parse(raw) as MsgsCacheEntry<MarketDemandResponse>) : null;
    } catch (error) {
      this.logger.error({ error, tenantId, skillId, region, industry }, 'Failed to read MSGS demand cache.');
      return null;
    }
  }

  async writeDemand(
    tenantId: string,
    skillId: string,
    region: string,
    entry: MsgsCacheEntry<MarketDemandResponse>,
    industry?: string
  ): Promise<void> {
    const client = this.ensureClient();
    if (!client) {
      return;
    }

    const key = this.buildDemandKey(tenantId, skillId, region, industry);
    try {
      await client.setex(key, this.config.demandTtlSeconds, JSON.stringify(entry));
    } catch (error) {
      this.logger.error({ error, tenantId, skillId, region, industry }, 'Failed to write MSGS demand cache.');
    }
  }

  async invalidateSkill(tenantId: string, skillId: string, fingerprint: string): Promise<void> {
    const client = this.ensureClient();
    if (!client) {
      return;
    }

    try {
      await client.del(this.buildSkillKey(tenantId, skillId, fingerprint));
    } catch (error) {
      this.logger.warn({ error, tenantId, skillId }, 'Failed to invalidate MSGS skill cache.');
    }
  }

  async invalidateRole(tenantId: string, ecoId: string, locale: string): Promise<void> {
    const client = this.ensureClient();
    if (!client) {
      return;
    }

    try {
      await client.del(this.buildRoleKey(tenantId, ecoId, locale));
    } catch (error) {
      this.logger.warn({ error, tenantId, ecoId, locale }, 'Failed to invalidate MSGS role cache.');
    }
  }

  async invalidateDemand(tenantId: string, skillId: string, region: string, industry?: string): Promise<void> {
    const client = this.ensureClient();
    if (!client) {
      return;
    }

    try {
      await client.del(this.buildDemandKey(tenantId, skillId, region, industry));
    } catch (error) {
      this.logger.warn({ error, tenantId, skillId, region, industry }, 'Failed to invalidate MSGS demand cache.');
    }
  }

  async healthCheck(): Promise<{ status: 'healthy' | 'degraded' | 'disabled' | 'unavailable'; latencyMs?: number; message?: string }> {
    if (this.config.disable) {
      return { status: 'disabled', message: 'MSGS cache disabled.' };
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
      this.logger.error({ error }, 'MSGS Redis health check failed.');
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
      this.logger.warn({ error }, 'Failed to close MSGS Redis client.');
    } finally {
      this.client = null;
    }
  }
}
