import { Pool, type PoolClient, type PoolConfig } from 'pg';
import type { Logger } from 'pino';

import type { MsgsDatabaseConfig } from './config';

export interface SkillAdjacencyRow {
  related_skill_id: string;
  related_skill_label: string;
  score: number;
  support: number;
  recency_days: number;
  sources: string[];
}

export interface RoleTemplateRow {
  eco_id: string;
  locale: string;
  title: string;
  summary: string;
  required_skills: Array<{ skill_id: string; label: string; importance: number }>;
  preferred_skills: Array<{ skill_id: string; label: string; importance: number }>;
  yoe_min: number | null;
  yoe_max: number | null;
  version: string;
}

export interface DemandSeriesRow {
  week_start: string;
  postings_count: number;
  demand_index: number;
}

export class MsgsCloudSqlClient {
  private pool: Pool | null = null;

  constructor(private readonly config: MsgsDatabaseConfig, private readonly logger: Logger) {}

  private createPool(): Pool {
    const poolConfig: PoolConfig = {
      host: this.config.host,
      port: this.config.port,
      user: this.config.user,
      password: this.config.password,
      database: this.config.database,
      ssl: this.config.ssl ? { rejectUnauthorized: false } : undefined,
      max: this.config.maxPoolSize,
      min: this.config.minPoolSize,
      connectionTimeoutMillis: this.config.connectTimeoutMs,
      idleTimeoutMillis: this.config.idleTimeoutMs
    } satisfies PoolConfig;

    const pool = new Pool(poolConfig);

    pool.on('error', (error) => {
      this.logger.error({ error }, 'Cloud SQL pool error.');
    });

    return pool;
  }

  private ensurePool(): Pool {
    if (!this.pool) {
      this.pool = this.createPool();
    }
    return this.pool;
  }

  async withClient<T>(callback: (client: PoolClient) => Promise<T>): Promise<T> {
    const pool = this.ensurePool();
    const client = await pool.connect();
    try {
      return await callback(client);
    } finally {
      client.release();
    }
  }

  async fetchSkillAdjacency(
    tenantId: string,
    skillId: string,
    limit: number
  ): Promise<SkillAdjacencyRow[]> {
    const pool = this.ensurePool();
    const query = `
      SELECT
        related_skill_id,
        related_skill_label,
        pmi_score AS score,
        support,
        recency_days,
        sources
      FROM msgs.skill_adjacency
      WHERE tenant_id = $1
        AND skill_id = $2
      ORDER BY pmi_score DESC
      LIMIT $3
    `;

    try {
      const result = await pool.query<SkillAdjacencyRow>(query, [tenantId, skillId, limit]);
      return result.rows ?? [];
    } catch (error) {
      this.logger.error({ error, tenantId, skillId }, 'Failed to fetch skill adjacency from Cloud SQL.');
      return [];
    }
  }

  async fetchRoleTemplate(
    tenantId: string,
    ecoId: string,
    locale: string
  ): Promise<RoleTemplateRow | null> {
    const pool = this.ensurePool();
    const query = `
      SELECT
        eco_id,
        locale,
        title,
        summary,
        required_skills,
        preferred_skills,
        yoe_min,
        yoe_max,
        version
      FROM msgs.role_template
      WHERE tenant_id = $1
        AND eco_id = $2
        AND (locale = $3 OR locale = 'default')
      ORDER BY locale = $3 DESC
      LIMIT 1
    `;

    try {
      const result = await pool.query<RoleTemplateRow>(query, [tenantId, ecoId, locale]);
      return result.rows[0] ?? null;
    } catch (error) {
      this.logger.error({ error, tenantId, ecoId, locale }, 'Failed to fetch role template from Cloud SQL.');
      return null;
    }
  }

  async fetchDemandSeries(
    tenantId: string,
    skillId: string,
    region: string,
    windowWeeks: number,
    industry?: string
  ): Promise<DemandSeriesRow[]> {
    const pool = this.ensurePool();
    const limit = Math.max(windowWeeks, 1);
    const windowStart = new Date();
    windowStart.setUTCDate(windowStart.getUTCDate() - (limit - 1) * 7);
    const windowStartIso = windowStart.toISOString().slice(0, 10);
    const query = `
      SELECT
        week_start,
        postings_count,
        demand_index
      FROM msgs.skill_demand
      WHERE tenant_id = $1
        AND skill_id = $2
        AND region = $3
        AND ($4::text IS NULL OR industry = $4)
        AND week_start >= $5::date
      ORDER BY week_start DESC
      LIMIT $6
    `;

    try {
      const result = await pool.query<DemandSeriesRow>(query, [
        tenantId,
        skillId,
        region,
        industry ?? null,
        windowStartIso,
        limit
      ]);
      return result.rows ?? [];
    } catch (error) {
      this.logger.error({ error, tenantId, skillId, region, industry }, 'Failed to fetch demand series from Cloud SQL.');
      return [];
    }
  }

  async healthCheck(): Promise<{ status: 'healthy' | 'degraded'; latencyMs?: number; message?: string }> {
    const pool = this.ensurePool();
    const start = Date.now();
    try {
      await pool.query('SELECT 1');
      return { status: 'healthy', latencyMs: Date.now() - start };
    } catch (error) {
      this.logger.error({ error }, 'Cloud SQL health check failed.');
      return { status: 'degraded', message: error instanceof Error ? error.message : 'Unknown error' };
    }
  }

  async close(): Promise<void> {
    if (!this.pool) {
      return;
    }

    try {
      await this.pool.end();
    } catch (error) {
      this.logger.warn({ error }, 'Failed to close Cloud SQL pool.');
    } finally {
      this.pool = null;
    }
  }
}
