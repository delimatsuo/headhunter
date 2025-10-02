import { Pool, type PoolClient, type QueryResult } from 'pg';
import { registerType, toSql } from 'pgvector/pg';
import type { Logger } from 'pino';

import type { PgVectorConfig } from './config';
import type { HybridSearchFilters, PgHybridSearchRow } from './types';

const VECTOR_TYPE_NAME = 'vector';

export interface PgHybridSearchQuery {
  tenantId: string;
  embedding: number[];
  textQuery: string;
  limit: number;
  offset: number;
  minSimilarity: number;
  vectorWeight: number;
  textWeight: number;
  warmupMultiplier: number;
  filters?: HybridSearchFilters;
}

export interface PgVectorHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  totalCandidates: number;
  poolSize: number;
  message?: string;
}

export class PgVectorClient {
  private readonly pool: Pool;
  private initialized = false;

  constructor(private readonly config: PgVectorConfig, private readonly logger: Logger) {
    this.pool = new Pool({
      host: config.host,
      port: config.port,
      database: config.database,
      user: config.user,
      password: config.password,
      ssl: config.ssl,
      max: config.poolMax,
      min: config.poolMin,
      idleTimeoutMillis: config.idleTimeoutMs,
      connectionTimeoutMillis: config.connectionTimeoutMs,
      statement_timeout: config.statementTimeoutMs
    });

    this.pool.on('connect', (client) => registerType(client));
  }

  async initialize(): Promise<void> {
    if (this.initialized) {
      return;
    }

    await this.withClient(async (client) => {
      if (this.config.enableAutoMigrate) {
        await this.ensureInfrastructure(client);
      } else {
        await this.verifyInfrastructure(client);
      }
    });

    this.initialized = true;
  }

  async close(): Promise<void> {
    await this.pool.end();
    this.initialized = false;
  }

  async hybridSearch(query: PgHybridSearchQuery): Promise<PgHybridSearchRow[]> {
    await this.initialize();

    return this.withClient(async (client) => {
      const warmupMultiplier = Number.isFinite(query.warmupMultiplier)
        ? Math.max(1, query.warmupMultiplier)
        : 1;
      const vectorPrefetch = Math.ceil(query.limit * warmupMultiplier);
      const vectorLimit = Math.max(query.limit, Math.min(vectorPrefetch, query.limit + 50));
      const filters: string[] = [];
      const values: unknown[] = [
        query.tenantId,
        toSql(query.embedding),
        vectorLimit,
        query.textQuery,
        query.vectorWeight,
        query.textWeight,
        query.minSimilarity,
        query.limit,
        query.offset
      ];

      let parameterIndex = values.length;

      if (query.filters?.locations && query.filters.locations.length > 0) {
        const normalizedLocations = query.filters.locations
          .map((loc) => loc.trim().toLowerCase())
          .filter((loc) => loc.length > 0);
        if (normalizedLocations.length > 0) {
          values.push(normalizedLocations);
          parameterIndex += 1;
          filters.push(`LOWER(cp.location) = ANY($${parameterIndex}::text[])`);
        }
      }

      if (query.filters?.industries && query.filters.industries.length > 0) {
        values.push(query.filters.industries);
        parameterIndex += 1;
        filters.push(`cp.industries && $${parameterIndex}::text[]`);
      }

      if (query.filters?.skills && query.filters.skills.length > 0) {
        values.push(query.filters.skills);
        parameterIndex += 1;
        filters.push(`cp.skills @> $${parameterIndex}::text[]`);
      }

      if (typeof query.filters?.minExperienceYears === 'number') {
        values.push(query.filters.minExperienceYears);
        parameterIndex += 1;
        filters.push(`COALESCE(cp.years_experience, 0) >= $${parameterIndex}`);
      }

      if (typeof query.filters?.maxExperienceYears === 'number') {
        values.push(query.filters.maxExperienceYears);
        parameterIndex += 1;
        filters.push(`COALESCE(cp.years_experience, 0) <= $${parameterIndex}`);
      }

      if (query.filters?.metadata && Object.keys(query.filters.metadata).length > 0) {
        values.push(JSON.stringify(query.filters.metadata));
        parameterIndex += 1;
        filters.push(`cp.profile @> $${parameterIndex}::jsonb`);
      }

      const filterClause = filters.length > 0 ? `AND ${filters.join('\n    AND ')}` : '';

      const efSearch = this.config.hnswEfSearch;
      if (efSearch && Number.isFinite(efSearch) && efSearch > 0) {
        await client.query(`SET LOCAL hnsw.ef_search = ${Math.floor(efSearch)}`);
      }

      const sql = `
        WITH vector_candidates AS (
          SELECT
            ce.candidate_id,
            1 - (ce.embedding <=> $2) AS vector_score,
            ce.metadata,
            ce.updated_at
          FROM ${this.config.schema}.${this.config.embeddingsTable} AS ce
          WHERE ce.tenant_id = $1
          ORDER BY ce.embedding <=> $2 ASC
          LIMIT $3
        ),
        text_candidates AS (
          SELECT
            cp.candidate_id,
            ts_rank_cd(cp.search_document, plainto_tsquery('simple', COALESCE($4, ''))) AS text_score
          FROM ${this.config.schema}.${this.config.profilesTable} AS cp
          WHERE cp.tenant_id = $1
            AND ($4 IS NULL OR $4 = '' OR cp.search_document @@ plainto_tsquery('simple', $4))
          ORDER BY text_score DESC
          LIMIT $3
        ),
        combined AS (
          SELECT candidate_id, vector_score, metadata FROM vector_candidates
          UNION ALL
          SELECT candidate_id, NULL::double precision AS vector_score, NULL::jsonb AS metadata FROM text_candidates
        ),
        scored AS (
          SELECT
            cp.candidate_id,
            cp.full_name,
            cp.current_title,
            cp.headline,
            cp.location,
            cp.industries,
            cp.skills,
            cp.years_experience,
            cp.analysis_confidence,
            cp.profile,
            MAX(combined.vector_score) AS vector_score,
            MAX(tc.text_score) AS text_score,
            MAX(vc.updated_at) AS updated_at,
            MAX(combined.metadata) AS metadata
          FROM combined
          JOIN ${this.config.schema}.${this.config.profilesTable} AS cp
            ON cp.candidate_id = combined.candidate_id AND cp.tenant_id = $1
          LEFT JOIN vector_candidates vc ON vc.candidate_id = cp.candidate_id
          LEFT JOIN text_candidates tc ON tc.candidate_id = cp.candidate_id
          WHERE true
            ${filterClause ? `\n            ${filterClause}` : ''}
          GROUP BY
            cp.candidate_id,
            cp.full_name,
            cp.current_title,
            cp.headline,
            cp.location,
            cp.industries,
            cp.skills,
            cp.years_experience,
            cp.analysis_confidence,
            cp.profile
        )
        SELECT
          candidate_id,
          full_name,
          current_title,
          headline,
          location,
          industries,
          skills,
          years_experience,
          analysis_confidence,
          profile,
          metadata,
          COALESCE(vector_score, 0) AS vector_score,
          COALESCE(text_score, 0) AS text_score,
          (($5 * COALESCE(vector_score, 0)) + ($6 * COALESCE(text_score, 0))) AS hybrid_score,
          to_char(COALESCE(updated_at, timezone('utc', now())), 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"') AS updated_at
        FROM scored
        WHERE COALESCE(vector_score, 0) >= $7 OR COALESCE(text_score, 0) > 0
        ORDER BY hybrid_score DESC, candidate_id ASC
        LIMIT $8
        OFFSET $9;
      `;

      const result: QueryResult<PgHybridSearchRow> = await client.query({ text: sql, values });
      return result.rows;
    });
  }

  async healthCheck(): Promise<PgVectorHealth> {
    try {
      await this.initialize();

      const total = await this.withClient(async (client) => {
        const result = await client.query(
          `SELECT COUNT(*) AS total FROM ${this.config.schema}.${this.config.profilesTable}`
        );
        return Number(result.rows[0]?.total ?? 0);
      });

      return {
        status: 'healthy',
        totalCandidates: total,
        poolSize: this.pool.totalCount
      } satisfies PgVectorHealth;
    } catch (error) {
      this.logger.error({ error }, 'pgvector health check failed.');
      return {
        status: 'unhealthy',
        totalCandidates: 0,
        poolSize: this.pool.totalCount,
        message: error instanceof Error ? error.message : 'Unknown error'
      } satisfies PgVectorHealth;
    }
  }

  private async ensureInfrastructure(client: PoolClient): Promise<void> {
    await client.query('CREATE EXTENSION IF NOT EXISTS "pgcrypto"');
    await client.query('CREATE EXTENSION IF NOT EXISTS "vector"');

    await client.query(`CREATE SCHEMA IF NOT EXISTS ${this.config.schema}`);

    await client.query(`
      CREATE TABLE IF NOT EXISTS ${this.config.schema}.${this.config.embeddingsTable} (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id TEXT NOT NULL,
        candidate_id TEXT NOT NULL,
        embedding ${VECTOR_TYPE_NAME}(${this.config.dimensions}) NOT NULL,
        embedding_text TEXT,
        metadata JSONB,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
        created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
      );
    `);

    await client.query(`
      CREATE TABLE IF NOT EXISTS ${this.config.schema}.${this.config.profilesTable} (
        candidate_id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        full_name TEXT,
        current_title TEXT,
        headline TEXT,
        location TEXT,
        industries TEXT[],
        skills TEXT[],
        years_experience NUMERIC,
        analysis_confidence NUMERIC,
        profile JSONB,
        search_document tsvector NOT NULL DEFAULT to_tsvector('simple', COALESCE(current_title, '') || ' ' || COALESCE(headline, '')),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
      );
    `);

    await client.query(`
      CREATE INDEX IF NOT EXISTS ${this.config.embeddingsTable}_tenant_idx
        ON ${this.config.schema}.${this.config.embeddingsTable} (tenant_id, candidate_id);
    `);

    await client.query(`
      CREATE INDEX IF NOT EXISTS ${this.config.embeddingsTable}_embedding_hnsw_idx
        ON ${this.config.schema}.${this.config.embeddingsTable} USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    `);

    await client.query(`
      CREATE INDEX IF NOT EXISTS ${this.config.profilesTable}_tenant_idx
        ON ${this.config.schema}.${this.config.profilesTable} (tenant_id, candidate_id);
    `);

    await client.query(`
      CREATE INDEX IF NOT EXISTS ${this.config.profilesTable}_location_lower_idx
        ON ${this.config.schema}.${this.config.profilesTable} (LOWER(location));
    `);

    await client.query(`
      CREATE INDEX IF NOT EXISTS ${this.config.profilesTable}_fts_idx
        ON ${this.config.schema}.${this.config.profilesTable} USING GIN (search_document);
    `);
  }

  private async verifyInfrastructure(client: PoolClient): Promise<void> {
    const schemaExists = await client.query(
      `SELECT schema_name FROM information_schema.schemata WHERE schema_name = $1`,
      [this.config.schema]
    );

    if (schemaExists.rowCount === 0) {
      throw new Error(`Schema ${this.config.schema} is missing.`);
    }

    const tableCheck = await client.query(
      `SELECT table_name FROM information_schema.tables WHERE table_schema = $1 AND table_name = $2`,
      [this.config.schema, this.config.embeddingsTable]
    );

    if (tableCheck.rowCount === 0) {
      throw new Error(`Embeddings table ${this.config.schema}.${this.config.embeddingsTable} is missing.`);
    }

    const profilesCheck = await client.query(
      `SELECT table_name FROM information_schema.tables WHERE table_schema = $1 AND table_name = $2`,
      [this.config.schema, this.config.profilesTable]
    );

    if (profilesCheck.rowCount === 0) {
      throw new Error(`Profiles table ${this.config.schema}.${this.config.profilesTable} is missing.`);
    }
  }

  private async withClient<T>(handler: (client: PoolClient) => Promise<T>): Promise<T> {
    const client = await this.pool.connect();
    try {
      return await handler(client);
    } finally {
      client.release();
    }
  }
}
