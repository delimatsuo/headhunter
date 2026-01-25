import { Pool, type PoolClient, type QueryResult } from 'pg';
import { registerType, toSql } from 'pgvector/pg';
import type { Logger } from 'pino';

import type { PgVectorConfig } from './config';
import type { HybridSearchFilters, PgHybridSearchRow } from './types';

const VECTOR_TYPE_NAME = 'vector';
export const PG_FTS_DICTIONARY = 'portuguese';

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
  // RRF configuration
  rrfK: number;           // RRF k parameter (default 60)
  perMethodLimit: number; // Candidates per method before fusion (default 100)
  enableRrf: boolean;     // Use RRF vs weighted sum
}

export interface PgVectorHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  totalCandidates: number;
  poolSize: number;
  idleConnections: number;
  waitingRequests: number;
  poolUtilization: number;  // (poolSize - idleConnections) / poolSize
  poolMax: number;
  poolMin: number;
  message?: string;
}

export class PgVectorClient {
  private readonly pool: Pool;
  private initialized = false;
  private initializationPromise: Promise<void> | null = null;

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

    if (this.initializationPromise) {
      return this.initializationPromise;
    }

    this.initializationPromise = (async () => {
      try {
        await this.withClient(async (client) => {
          if (this.config.enableAutoMigrate) {
            await this.ensureInfrastructure(client);
          } else {
            await this.verifyInfrastructure(client);
          }
        });

        await this.warmupPool();
        this.initialized = true;
      } finally {
        this.initializationPromise = null;
      }
    })();

    return this.initializationPromise;
  }

  async close(): Promise<void> {
    await this.pool.end();
    this.initialized = false;
  }

  async hybridSearch(query: PgHybridSearchQuery): Promise<PgHybridSearchRow[]> {
    await this.initialize();

    return this.withClient(async (client) => {
      // Capture pool metrics for observability
      const poolMetrics = {
        poolSize: this.pool.totalCount,
        idle: this.pool.idleCount ?? 0,
        waiting: this.pool.waitingCount ?? 0
      };

      // FTS diagnostic logging - log query parameters
      this.logger.info({
        textQuery: query.textQuery,
        textQueryEmpty: !query.textQuery || query.textQuery.trim() === '',
        limit: query.limit
      }, 'FTS debug: query parameters');

      // FTS diagnostic query - check FTS match potential
      if (query.textQuery && query.textQuery.trim()) {
        const ftsCheckSql = `
          SELECT
            COUNT(*) as total_candidates,
            COUNT(CASE WHEN search_document IS NOT NULL THEN 1 END) as has_fts,
            COUNT(CASE WHEN search_document @@ plainto_tsquery('${PG_FTS_DICTIONARY}', $2) THEN 1 END) as matches_query,
            plainto_tsquery('${PG_FTS_DICTIONARY}', $2)::text as parsed_query
          FROM ${this.config.schema}.${this.config.profilesTable}
          WHERE tenant_id = $1
        `;
        const ftsCheck = await client.query(ftsCheckSql, [query.tenantId, query.textQuery]);
        this.logger.info({
          ftsCheck: ftsCheck.rows[0],
          dictionary: PG_FTS_DICTIONARY
        }, 'FTS debug: search_document analysis');
      }

      // RRF configuration - use perMethodLimit for both vector and text CTEs
      const perMethodLimit = Number.isFinite(query.perMethodLimit)
        ? Math.max(10, query.perMethodLimit)
        : 100;

      // Log RRF configuration for debugging
      this.logger.info({
        rrfK: query.rrfK,
        perMethodLimit,
        enableRrf: query.enableRrf,
        limit: query.limit
      }, 'RRF config: hybrid search parameters');

      // Track whether we have a text query for later warning
      const hasTextQuery = query.textQuery && query.textQuery.trim().length > 0;
      this.logger.debug({
        hasTextQuery,
        textQueryLength: query.textQuery?.length ?? 0
      }, 'RRF query type');

      const filters: string[] = [];
      const values: unknown[] = [
        query.tenantId,
        toSql(query.embedding),
        perMethodLimit,       // $3 - used for both vector_candidates and text_candidates LIMIT
        query.textQuery,
        query.vectorWeight,
        query.textWeight,
        query.minSimilarity,
        query.limit,
        query.offset,
        query.rrfK            // $10 - RRF k parameter for scoring calculation
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

      if (query.filters?.countries && query.filters.countries.length > 0) {
        const normalizedCountries = query.filters.countries
          .map((c) => c.trim())
          .filter((c) => c.length > 0);
        if (normalizedCountries.length > 0) {
          values.push(normalizedCountries);
          parameterIndex += 1;
          // Include candidates in specified countries OR with unknown location (NULL)
          // This avoids excluding potentially relevant candidates just because we don't have their location
          filters.push(`(cp.country = ANY($${parameterIndex}::text[]) OR cp.country IS NULL)`);
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

      // Set index-specific runtime parameters
      if (this.config.indexType === 'diskann') {
        const searchListSize = this.config.diskannSearchListSize;
        if (searchListSize > 0) {
          await client.query(`SET LOCAL diskann.query_search_list_size = ${Math.floor(searchListSize)}`);
        }
        this.logger.debug({ indexType: 'diskann', searchListSize }, 'Using StreamingDiskANN index');
      } else {
        const efSearch = this.config.hnswEfSearch;
        if (efSearch && Number.isFinite(efSearch) && efSearch > 0) {
          await client.query(`SET LOCAL hnsw.ef_search = ${Math.floor(efSearch)}`);
          this.logger.debug({ indexType: 'hnsw', efSearch }, 'Using HNSW index');
        }
      }

      // Choose SQL based on enableRrf flag (RRF vs weighted sum for A/B testing)
      const sql = query.enableRrf
        ? this.buildRrfSql(filterClause)
        : this.buildWeightedSumSql(filterClause);

      const result: QueryResult<PgHybridSearchRow> = await client.query({ text: sql, values });

      // RRF result summary logging
      const vectorOnlyCount = result.rows.filter(r => (r.vector_score ?? 0) > 0 && (r.text_score ?? 0) === 0).length;
      const textOnlyCount = result.rows.filter(r => (r.vector_score ?? 0) === 0 && (r.text_score ?? 0) > 0).length;
      const bothCount = result.rows.filter(r => (r.vector_score ?? 0) > 0 && (r.text_score ?? 0) > 0).length;
      const noScoreCount = result.rows.filter(r => (r.vector_score ?? 0) === 0 && (r.text_score ?? 0) === 0).length;

      const rrfScores = result.rows.map(r => r.hybrid_score ?? 0).filter(s => s > 0);
      const avgRrfScore = rrfScores.length > 0 ? rrfScores.reduce((a, b) => a + b, 0) / rrfScores.length : 0;
      const maxRrfScore = rrfScores.length > 0 ? Math.max(...rrfScores) : 0;
      const minRrfScore = rrfScores.length > 0 ? Math.min(...rrfScores) : 0;

      this.logger.info({
        totalResults: result.rows.length,
        vectorOnly: vectorOnlyCount,
        textOnly: textOnlyCount,
        both: bothCount,
        noScore: noScoreCount,
        rrfStats: {
          avg: avgRrfScore.toFixed(6),
          max: maxRrfScore.toFixed(6),
          min: minRrfScore.toFixed(6)
        },
        textQuery: query.textQuery?.slice(0, 50),
        rrfK: query.rrfK,
        enableRrf: query.enableRrf,
        poolMetrics
      }, 'RRF hybrid search summary');

      // Warn if FTS expected but not contributing
      if (hasTextQuery && textOnlyCount === 0 && bothCount === 0) {
        this.logger.warn({
          textQuery: query.textQuery?.slice(0, 100),
          totalResults: result.rows.length,
          vectorOnly: vectorOnlyCount
        }, 'RRF warning: FTS returned no matches despite having a text query. Check search_document population.');
      }

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

      const poolSize = this.pool.totalCount;
      const idleConnections = this.pool.idleCount ?? 0;
      const waitingRequests = this.pool.waitingCount ?? 0;
      const poolUtilization = poolSize > 0 ? (poolSize - idleConnections) / poolSize : 0;

      // Log warning if pool is under pressure
      if (waitingRequests > 5) {
        this.logger.warn(
          { waitingRequests, poolSize, poolMax: this.config.poolMax },
          'Pool saturation warning: requests waiting for connections'
        );
      }

      return {
        status: waitingRequests > 10 ? 'degraded' : 'healthy',
        totalCandidates: total,
        poolSize,
        idleConnections,
        waitingRequests,
        poolUtilization: Math.round(poolUtilization * 100) / 100,
        poolMax: this.config.poolMax,
        poolMin: this.config.poolMin
      } satisfies PgVectorHealth;
    } catch (error) {
      this.logger.error({ error }, 'pgvector health check failed.');
      return {
        status: 'unhealthy',
        totalCandidates: 0,
        poolSize: this.pool.totalCount,
        idleConnections: this.pool.idleCount ?? 0,
        waitingRequests: this.pool.waitingCount ?? 0,
        poolUtilization: 0,
        poolMax: this.config.poolMax,
        poolMin: this.config.poolMin,
        message: error instanceof Error ? error.message : 'Unknown error'
      } satisfies PgVectorHealth;
    }
  }

  async rawQuery(sql: string): Promise<QueryResult> {
    await this.initialize();
    return this.withClient(async (client) => {
      return await client.query(sql);
    });
  }

  private async ensureInfrastructure(client: PoolClient): Promise<void> {
    await client.query('CREATE EXTENSION IF NOT EXISTS "pgcrypto"');
    await client.query('CREATE EXTENSION IF NOT EXISTS "vector"');

    await client.query(`CREATE SCHEMA IF NOT EXISTS ${this.config.schema}`);

    await client.query(`
      CREATE TABLE IF NOT EXISTS ${this.config.schema}.${this.config.embeddingsTable} (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        embedding ${VECTOR_TYPE_NAME}(${this.config.dimensions}) NOT NULL,
        embedding_text TEXT,
        metadata JSONB,
        model_version TEXT,
        chunk_type TEXT NOT NULL DEFAULT 'default',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
        created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
        UNIQUE(tenant_id, entity_id, chunk_type)
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
        legal_basis TEXT,
        consent_record TEXT,
        transfer_mechanism TEXT,
        search_document tsvector NOT NULL DEFAULT to_tsvector('${PG_FTS_DICTIONARY}', COALESCE(current_title, '') || ' ' || COALESCE(headline, '')),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
      );
    `);

    await client.query(`
      ALTER TABLE ${this.config.schema}.${this.config.profilesTable}
        ADD COLUMN IF NOT EXISTS legal_basis TEXT;
    `);

    await client.query(`
      ALTER TABLE ${this.config.schema}.${this.config.profilesTable}
        ADD COLUMN IF NOT EXISTS consent_record TEXT;
    `);

    await client.query(`
      ALTER TABLE ${this.config.schema}.${this.config.profilesTable}
        ADD COLUMN IF NOT EXISTS transfer_mechanism TEXT;
    `);

    await client.query(`
      ALTER TABLE ${this.config.schema}.${this.config.profilesTable}
        ALTER COLUMN search_document
        SET DEFAULT to_tsvector('${PG_FTS_DICTIONARY}', COALESCE(current_title, '') || ' ' || COALESCE(headline, ''));
    `);

    await client.query(`
      CREATE INDEX IF NOT EXISTS ${this.config.embeddingsTable}_tenant_idx
        ON ${this.config.schema}.${this.config.embeddingsTable} (tenant_id, entity_id);
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

    // Migrate existing rows: populate search_document with title, headline, skills, and industries
    this.logger.info('Checking if search_document migration is needed...');
    const needsMigration = await client.query(`
      SELECT COUNT(*) as count
      FROM ${this.config.schema}.${this.config.profilesTable}
      WHERE search_document IS NULL
         OR length(search_document::text) < 10
    `);

    const migrationCount = Number(needsMigration.rows[0]?.count ?? 0);
    if (migrationCount > 0) {
      this.logger.info({ count: migrationCount }, 'Migrating search_document for existing candidates...');
      await client.query(`
        UPDATE ${this.config.schema}.${this.config.profilesTable}
        SET search_document = to_tsvector('${PG_FTS_DICTIONARY}',
          COALESCE(current_title, '') || ' ' ||
          COALESCE(headline, '') || ' ' ||
          COALESCE(array_to_string(skills, ' '), '') || ' ' ||
          COALESCE(array_to_string(industries, ' '), '')
        )
        WHERE search_document IS NULL
           OR length(search_document::text) < 10
      `);
      this.logger.info({ count: migrationCount }, 'Search_document migration completed');
    } else {
      this.logger.info('No search_document migration needed');
    }

    // Create or replace trigger to auto-update search_document on INSERT/UPDATE
    await client.query(`
      CREATE OR REPLACE FUNCTION update_candidate_search_document()
      RETURNS TRIGGER AS $$
      BEGIN
        NEW.search_document := to_tsvector('${PG_FTS_DICTIONARY}',
          COALESCE(NEW.current_title, '') || ' ' ||
          COALESCE(NEW.headline, '') || ' ' ||
          COALESCE(array_to_string(NEW.skills, ' '), '') || ' ' ||
          COALESCE(array_to_string(NEW.industries, ' '), '')
        );
        RETURN NEW;
      END;
      $$ LANGUAGE plpgsql;
    `);

    await client.query(`
      DROP TRIGGER IF EXISTS candidates_search_document_trigger
        ON ${this.config.schema}.${this.config.profilesTable};
    `);

    await client.query(`
      CREATE TRIGGER candidates_search_document_trigger
        BEFORE INSERT OR UPDATE OF current_title, headline, skills, industries
        ON ${this.config.schema}.${this.config.profilesTable}
        FOR EACH ROW
        EXECUTE FUNCTION update_candidate_search_document();
    `);

    this.logger.info('FTS trigger created for automatic search_document updates');
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

    const complianceColumns = await client.query(
      `
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = $1
          AND table_name = $2
          AND column_name = ANY($3::text[])
      `,
      [this.config.schema, this.config.profilesTable, ['legal_basis', 'consent_record', 'transfer_mechanism']]
    );

    if (complianceColumns.rowCount !== 3) {
      throw new Error(`Profiles table ${this.config.schema}.${this.config.profilesTable} must include legal_basis, consent_record, and transfer_mechanism columns.`);
    }

    // Check for Portuguese FTS configuration - either via DEFAULT or TRIGGER
    const searchDocDefault = await client.query(
      `
        SELECT pg_get_expr(ad.adbin, ad.adrelid) AS default_value
        FROM pg_attrdef ad
        JOIN pg_attribute att
          ON att.attrelid = ad.adrelid AND att.attnum = ad.adnum
        WHERE ad.adrelid = $1::regclass
          AND att.attname = 'search_document'
      `,
      [`${this.config.schema}.${this.config.profilesTable}`]
    );

    const defaultExpression = searchDocDefault.rows[0]?.default_value as string | undefined;
    const hasPortugueseDefault = defaultExpression && defaultExpression.toLowerCase().includes(PG_FTS_DICTIONARY.toLowerCase());

    // If no default or default doesn't use Portuguese, check for trigger
    if (!hasPortugueseDefault) {
      const triggerCheck = await client.query(
        `
          SELECT tgname, pg_get_triggerdef(oid) AS trigger_def
          FROM pg_trigger
          WHERE tgrelid = $1::regclass
        `,
        [`${this.config.schema}.${this.config.profilesTable}`]
      );

      // Check if ANY trigger uses Portuguese dictionary
      const hasPortugueseTrigger = triggerCheck.rows.some(
        row => row.trigger_def && row.trigger_def.toLowerCase().includes(PG_FTS_DICTIONARY.toLowerCase())
      );

      const triggerCount = triggerCheck.rowCount ?? 0;

      if (!hasPortugueseTrigger && triggerCount > 0) {
        // Triggers exist but none use Portuguese - log for debugging
        console.warn(
          `Warning: Found ${triggerCount} trigger(s) but none use '${PG_FTS_DICTIONARY}'. ` +
          `Triggers: ${triggerCheck.rows.map((r: any) => r.tgname).join(', ')}`
        );
      }

      if (!hasPortugueseTrigger && triggerCount === 0) {
        // No triggers at all - accept if in production (assume schema is managed externally)
        console.warn(
          `Warning: No DEFAULT or TRIGGER found for search_document with '${PG_FTS_DICTIONARY}'. ` +
          `Assuming schema is externally managed.`
        );
      }
    }
  }

  private async warmupPool(): Promise<void> {
    // Warm up to poolMin to ensure connections are ready
    const warmupTarget = Math.min(this.config.poolMin, this.config.poolMax);
    if (warmupTarget <= 0) {
      this.logger.debug('Pool warmup skipped - poolMin is 0');
      return;
    }

    const started = Date.now();
    const connections: PoolClient[] = [];

    try {
      // Acquire connections in parallel for faster warmup
      const warmupPromises = Array.from({ length: warmupTarget }, async () => {
        try {
          return await this.pool.connect();
        } catch (error) {
          this.logger.warn({ error }, 'Failed to acquire warmup connection.');
          return null;
        }
      });

      const results = await Promise.all(warmupPromises);
      results.forEach(client => {
        if (client) connections.push(client);
      });
    } finally {
      // Release all connections back to pool
      connections.forEach(client => client.release());
    }

    this.logger.info(
      {
        warmedConnections: connections.length,
        targetConnections: warmupTarget,
        durationMs: Date.now() - started
      },
      'pgvector pool warmup completed.'
    );
  }

  private async withClient<T>(handler: (client: PoolClient) => Promise<T>): Promise<T> {
    const client = await this.pool.connect();
    try {
      return await handler(client);
    } finally {
      client.release();
    }
  }

  /**
   * Build RRF (Reciprocal Rank Fusion) scoring SQL.
   * RRF score = 1/(k + vector_rank) + 1/(k + text_rank)
   * This eliminates the need for score normalization between different scales.
   */
  private buildRrfSql(filterClause: string): string {
    return `
      WITH vector_candidates AS (
        SELECT
          ce.entity_id AS candidate_id,
          1 - (ce.embedding <=> $2) AS vector_score,
          ROW_NUMBER() OVER (ORDER BY ce.embedding <=> $2 ASC) AS vector_rank,
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
          ts_rank_cd(cp.search_document, plainto_tsquery('${PG_FTS_DICTIONARY}', $4)) AS text_score,
          ROW_NUMBER() OVER (ORDER BY ts_rank_cd(cp.search_document, plainto_tsquery('${PG_FTS_DICTIONARY}', $4)) DESC) AS text_rank
        FROM ${this.config.schema}.${this.config.profilesTable} AS cp
        WHERE cp.tenant_id = $1
          AND $4 IS NOT NULL
          AND $4 != ''
          AND cp.search_document @@ plainto_tsquery('${PG_FTS_DICTIONARY}', $4)
        ORDER BY text_score DESC
        LIMIT $3
      ),
      rrf_scored AS (
        SELECT
          COALESCE(vc.candidate_id, tc.candidate_id) AS candidate_id,
          vc.vector_score,
          vc.vector_rank,
          tc.text_score,
          tc.text_rank,
          COALESCE(1.0 / ($10 + vc.vector_rank), 0) AS rrf_vector,
          COALESCE(1.0 / ($10 + tc.text_rank), 0) AS rrf_text,
          COALESCE(1.0 / ($10 + vc.vector_rank), 0) + COALESCE(1.0 / ($10 + tc.text_rank), 0) AS rrf_score,
          vc.metadata,
          vc.updated_at
        FROM vector_candidates vc
        FULL OUTER JOIN text_candidates tc ON vc.candidate_id = tc.candidate_id
      )
      SELECT
        rs.candidate_id,
        cp.full_name,
        cp.current_title,
        cp.headline,
        cp.location,
        cp.country,
        cp.industries,
        cp.skills,
        cp.years_experience,
        cp.analysis_confidence,
        cp.profile,
        cp.legal_basis,
        cp.consent_record,
        cp.transfer_mechanism,
        rs.metadata,
        COALESCE(rs.vector_score, 0) AS vector_score,
        COALESCE(rs.text_score, 0) AS text_score,
        rs.rrf_score,
        rs.vector_rank,
        rs.text_rank,
        -- Keep hybrid_score for backward compatibility (will be same as rrf_score)
        rs.rrf_score AS hybrid_score,
        to_char(COALESCE(rs.updated_at, timezone('utc', now())), 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"') AS updated_at
      FROM rrf_scored rs
      JOIN ${this.config.schema}.${this.config.profilesTable} AS cp
        ON cp.candidate_id = rs.candidate_id AND cp.tenant_id = $1
      WHERE COALESCE(rs.vector_score, 0) >= $7 OR COALESCE(rs.text_score, 0) > 0
      ${filterClause}
      ORDER BY rs.rrf_score DESC, rs.candidate_id ASC
      LIMIT $8
      OFFSET $9;
    `;
  }

  /**
   * Build weighted sum scoring SQL (legacy approach for A/B testing).
   * hybrid_score = (vectorWeight * vector_score) + (textWeight * text_score)
   */
  private buildWeightedSumSql(filterClause: string): string {
    return `
      WITH vector_candidates AS (
        SELECT
          ce.entity_id AS candidate_id,
          1 - (ce.embedding <=> $2) AS vector_score,
          ROW_NUMBER() OVER (ORDER BY ce.embedding <=> $2 ASC) AS vector_rank,
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
          ts_rank_cd(cp.search_document, plainto_tsquery('${PG_FTS_DICTIONARY}', $4)) AS text_score,
          ROW_NUMBER() OVER (ORDER BY ts_rank_cd(cp.search_document, plainto_tsquery('${PG_FTS_DICTIONARY}', $4)) DESC) AS text_rank
        FROM ${this.config.schema}.${this.config.profilesTable} AS cp
        WHERE cp.tenant_id = $1
          AND $4 IS NOT NULL
          AND $4 != ''
          AND cp.search_document @@ plainto_tsquery('${PG_FTS_DICTIONARY}', $4)
        ORDER BY text_score DESC
        LIMIT $3
      ),
      combined AS (
        SELECT
          COALESCE(vc.candidate_id, tc.candidate_id) AS candidate_id,
          vc.vector_score,
          vc.vector_rank,
          vc.metadata,
          vc.updated_at,
          tc.text_score,
          tc.text_rank
        FROM vector_candidates vc
        FULL OUTER JOIN text_candidates tc ON vc.candidate_id = tc.candidate_id
      ),
      scored AS (
        SELECT
          cp.candidate_id,
          cp.full_name,
          cp.current_title,
          cp.headline,
          cp.location,
          cp.country,
          cp.industries,
          cp.skills,
          cp.years_experience,
          cp.analysis_confidence,
          cp.profile,
          cp.legal_basis,
          cp.consent_record,
          cp.transfer_mechanism,
          c.vector_score,
          c.vector_rank,
          COALESCE(c.text_score, 0) AS text_score,
          c.text_rank,
          c.updated_at,
          c.metadata
        FROM combined c
        JOIN ${this.config.schema}.${this.config.profilesTable} AS cp
          ON cp.candidate_id = c.candidate_id AND cp.tenant_id = $1
        WHERE true
          ${filterClause ? `\n          ${filterClause}` : ''}
      )
      SELECT
        candidate_id,
        full_name,
        current_title,
        headline,
        location,
        country,
        industries,
        skills,
        years_experience,
        analysis_confidence,
        profile,
        legal_basis,
        consent_record,
        transfer_mechanism,
        metadata,
        COALESCE(vector_score, 0) AS vector_score,
        COALESCE(text_score, 0) AS text_score,
        vector_rank,
        text_rank,
        (($5 * COALESCE(vector_score, 0)) + ($6 * COALESCE(text_score, 0))) AS hybrid_score,
        to_char(COALESCE(updated_at, timezone('utc', now())), 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"') AS updated_at
      FROM scored
      WHERE COALESCE(vector_score, 0) >= $7 OR COALESCE(text_score, 0) > 0
      ORDER BY hybrid_score DESC, candidate_id ASC
      LIMIT $8
      OFFSET $9;
    `;
  }
}