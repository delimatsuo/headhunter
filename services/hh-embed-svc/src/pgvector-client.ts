import { Pool, type PoolClient } from 'pg';
import { registerType, toSql } from 'pgvector/pg';
import type { Logger } from 'pino';

import type { PgVectorSettings } from './config';
import type { EmbeddingRecord, EmbeddingSearchResult, EmbeddingVector } from './types';

const VECTOR_TYPE_NAME = 'vector';

export interface QuerySimilarOptions {
  tenantId: string;
  embedding: EmbeddingVector;
  limit: number;
  similarityThreshold: number;
  filter?: Record<string, unknown>;
}

export interface UpsertEmbeddingResult {
  id: string;
  tenantId: string;
  entityId: string;
  modelVersion: string;
  chunkType: string;
  createdAt: string;
  updatedAt: string;
}

export interface PgVectorHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  totalEmbeddings: number;
  poolSize: number;
  message?: string;
}

export class PgVectorClient {
  private readonly pool: Pool;
  private initialized = false;
  private schemaSetupDone = false;
  private readonly schema: string;
  private readonly table: string;
  private readonly tenantCache = new Map<string, number>();
  private readonly dimensions: number;
  private readonly hnswEfSearch?: number;

  constructor(private readonly config: PgVectorSettings, private readonly logger: Logger) {
    this.schema = config.schema;
    this.table = config.table;
    this.dimensions = config.dimensions;
    this.hnswEfSearch = config.hnswEfSearch;

    this.pool = new Pool({
      host: config.host,
      port: config.port,
      database: config.database,
      user: config.user,
      password: config.password,
      ssl: config.ssl,
      max: config.poolMax,
      idleTimeoutMillis: config.idleTimeoutMillis,
      connectionTimeoutMillis: config.connectionTimeoutMillis,
      statement_timeout: config.statementTimeoutMillis
    });

    this.pool.on('connect', (client) => registerType(client));
  }

  async initialize(): Promise<void> {
    if (this.initialized) {
      return;
    }

    // Non-blocking initialization: just mark as initialized
    // Actual database connection and schema setup happens on first use
    this.initialized = true;
    this.logger.info('PgVectorClient initialized (connection will be established on first use)');
  }

  private async setupDatabaseIfNeeded(client: PoolClient): Promise<void> {
    // This is called on first actual database access
    if (this.config.enableAutoMigrate) {
      await this.ensureExtensions(client);
      await this.ensureSchema(client);
      await this.ensureTables(client);
    } else {
      await this.verifyExtensions(client);
      await this.verifySchema(client);
    }
  }

  async close(): Promise<void> {
    await this.pool.end();
    this.initialized = false;
    this.schemaSetupDone = false;
    this.tenantCache.clear();
  }

  async upsertEmbedding(record: EmbeddingRecord): Promise<UpsertEmbeddingResult> {
    await this.initialize();

    const now = new Date().toISOString();

    return this.withClient(async (client) => {
      await this.ensureTenant(client, record.tenantId);

      const query = {
        text: `
          INSERT INTO ${this.schema}.${this.table} 
            (tenant_id, entity_id, embedding, embedding_text, metadata, model_version, chunk_type, created_at, updated_at)
          VALUES ($1, $2, $3, $4, $5, $6, $7, timezone('utc', now()), timezone('utc', now()))
          ON CONFLICT (tenant_id, entity_id, chunk_type)
          DO UPDATE SET
            embedding = EXCLUDED.embedding,
            embedding_text = COALESCE(EXCLUDED.embedding_text, ${this.schema}.${this.table}.embedding_text),
            metadata = COALESCE(EXCLUDED.metadata, ${this.schema}.${this.table}.metadata),
            model_version = EXCLUDED.model_version,
            updated_at = timezone('utc', now())
          RETURNING id, tenant_id, entity_id, model_version, chunk_type, created_at, updated_at;
        `,
        values: [
          record.tenantId,
          record.entityId,
          toSql(record.embedding),
          record.embeddingText ?? null,
          record.metadata ?? null,
          record.modelVersion,
          record.chunkType ?? 'default'
        ]
      };

      const result = await client.query(query);
      const row = result.rows[0];

      return {
        id: row.id,
        tenantId: row.tenant_id,
        entityId: row.entity_id,
        modelVersion: row.model_version,
        chunkType: row.chunk_type,
        createdAt: row.created_at instanceof Date ? row.created_at.toISOString() : now,
        updatedAt: row.updated_at instanceof Date ? row.updated_at.toISOString() : now
      } satisfies UpsertEmbeddingResult;
    });
  }

  async querySimilar(options: QuerySimilarOptions): Promise<EmbeddingSearchResult[]> {
    await this.initialize();

    return this.withClient(async (client) => {
      if (typeof this.hnswEfSearch === 'number' && Number.isFinite(this.hnswEfSearch) && this.hnswEfSearch > 0) {
        await client.query('SET hnsw.ef_search = $1', [Math.round(this.hnswEfSearch)]);
      }

      await this.ensureTenant(client, options.tenantId);

      const cosineDistanceThreshold = Math.max(0, 1 - options.similarityThreshold);

      const values: Array<unknown> = [
        options.tenantId,
        toSql(options.embedding),
        cosineDistanceThreshold,
        options.limit
      ];

      const filters: string[] = ['tenant_id = $1', '(embedding <=> $2) <= $3'];

      if (options.filter && Object.keys(options.filter).length > 0) {
        values.push(JSON.stringify(options.filter));
        filters.push(`metadata @> $${values.length}::jsonb`);
      }

      const query = {
        text: `
          SELECT 
            id,
            entity_id,
            metadata,
            model_version,
            chunk_type,
            updated_at,
            1 - (embedding <=> $2) AS similarity
          FROM ${this.schema}.${this.table}
          WHERE ${filters.join('\n            AND ')}
          ORDER BY embedding <=> $2 ASC
          LIMIT $4;
        `,
        values
      };

      const result = await client.query(query);
      return result.rows.map((row) => ({
        entityId: row.entity_id,
        similarity: Number(row.similarity),
        metadata: row.metadata ?? undefined,
        modelVersion: row.model_version,
        chunkType: row.chunk_type,
        embeddingId: row.id,
        updatedAt: row.updated_at instanceof Date ? row.updated_at.toISOString() : new Date().toISOString()
      }));
    });
  }

  async healthCheck(): Promise<PgVectorHealth> {
    try {
      await this.initialize();

      const total = await this.withClient(async (client) => {
        const result = await client.query(
          `SELECT COUNT(*) AS total FROM ${this.schema}.${this.table}`
        );
        return Number(result.rows[0]?.total ?? 0);
      });

      return {
        status: 'healthy',
        totalEmbeddings: total,
        poolSize: this.pool.totalCount
      } satisfies PgVectorHealth;
    } catch (error) {
      this.logger.error({ error }, 'PgVector health check failed.');
      return {
        status: 'unhealthy',
        totalEmbeddings: 0,
        poolSize: this.pool.totalCount,
        message: error instanceof Error ? error.message : 'Unknown error'
      } satisfies PgVectorHealth;
    }
  }

  private async ensureExtensions(client: PoolClient): Promise<void> {
    await client.query('CREATE EXTENSION IF NOT EXISTS "pgcrypto"');
    await client.query('CREATE EXTENSION IF NOT EXISTS "vector"');
  }

  private async ensureSchema(client: PoolClient): Promise<void> {
    await client.query(`CREATE SCHEMA IF NOT EXISTS ${this.schema}`);
  }

  private async ensureTables(client: PoolClient): Promise<void> {
    await client.query(`
      CREATE TABLE IF NOT EXISTS ${this.schema}.${this.table} (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        embedding ${VECTOR_TYPE_NAME}(${this.dimensions}) NOT NULL,
        embedding_text TEXT,
        metadata JSONB,
        model_version TEXT NOT NULL,
        chunk_type TEXT NOT NULL DEFAULT 'default',
        created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
        UNIQUE(tenant_id, entity_id, chunk_type)
      );
    `);

    await client.query(`
      CREATE TABLE IF NOT EXISTS ${this.schema}.tenants (
        tenant_id TEXT PRIMARY KEY,
        last_seen_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
      );
    `);

    await client.query(`
      CREATE INDEX IF NOT EXISTS ${this.table}_tenant_idx 
        ON ${this.schema}.${this.table} (tenant_id, entity_id);
    `);

    await client.query(`
      DROP INDEX IF EXISTS ${this.schema}.${this.table}_embedding_cosine_idx;
    `);

    await client.query(`
      CREATE INDEX IF NOT EXISTS ${this.table}_embedding_hnsw_idx 
        ON ${this.schema}.${this.table} USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    `);
  }

  private async verifyExtensions(client: PoolClient): Promise<void> {
    const requiredExtensions = ['vector', 'pgcrypto'];

    for (const extension of requiredExtensions) {
      const result = await client.query(`SELECT 1 FROM pg_extension WHERE extname = $1`, [extension]);
      if (result.rowCount === 0) {
        throw new Error(
          `${extension} extension is not installed. Enable ENABLE_AUTO_MIGRATE or run the managed migrations.`
        );
      }
    }
  }

  private async verifySchema(client: PoolClient): Promise<void> {
    const schemaExists = await client.query(
      `SELECT schema_name FROM information_schema.schemata WHERE schema_name = $1`,
      [this.schema]
    );

    if (schemaExists.rowCount === 0) {
      throw new Error(
        `Schema ${this.schema} is missing. Run migrations or set ENABLE_AUTO_MIGRATE=true for bootstrap.`
      );
    }

    const embeddingsTableExists = await client.query(
      `SELECT table_name FROM information_schema.tables WHERE table_schema = $1 AND table_name = $2`,
      [this.schema, this.table]
    );

    if (embeddingsTableExists.rowCount === 0) {
      throw new Error(
        `Table ${this.schema}.${this.table} is missing. Run migrations or set ENABLE_AUTO_MIGRATE=true for bootstrap.`
      );
    }

    const embeddingColumn = await client.query(
      `SELECT atttypmod FROM pg_attribute WHERE attrelid = $1::regclass AND attname = 'embedding'`,
      [`${this.schema}.${this.table}`]
    );

    if (embeddingColumn.rowCount === 0) {
      throw new Error(
        `Column embedding is missing on ${this.schema}.${this.table}. Run migrations or enable auto migration.`
      );
    }

    const atttypmod = Number(embeddingColumn.rows[0]?.atttypmod ?? 0);

    // pgvector 0.7.0+ stores dimensions directly in atttypmod
    // Older versions use atttypmod - 4
    const dimensionDirect = atttypmod;
    const dimensionLegacy = atttypmod - 4;

    const isNewFormat = dimensionDirect === this.dimensions;
    const isLegacyFormat = dimensionLegacy === this.dimensions;
    const actualDimension = isNewFormat ? dimensionDirect : dimensionLegacy;

    this.logger.info({
      atttypmod,
      actualDimension,
      expectedDimension: this.dimensions,
      format: isNewFormat ? 'pgvector-0.7.0+' : (isLegacyFormat ? 'pgvector-legacy' : 'unknown'),
      table: `${this.schema}.${this.table}`
    }, 'Database dimension check');

    if (!Number.isFinite(atttypmod) || (!isNewFormat && !isLegacyFormat)) {
      throw new Error(
        `Embedding dimensionality mismatch detected in ${this.schema}.${this.table}. Expected vector(${this.dimensions}), found atttypmod=${atttypmod}, dimension=${actualDimension}.`
      );
    }

    const tenantsTableExists = await client.query(
      `SELECT table_name FROM information_schema.tables WHERE table_schema = $1 AND table_name = 'tenants'`,
      [this.schema]
    );

    if (tenantsTableExists.rowCount === 0) {
      throw new Error(`Table ${this.schema}.tenants is missing. Run migrations or enable auto migration.`);
    }

    const indexCheck = await client.query(
      `SELECT indexdef FROM pg_indexes WHERE schemaname = $1 AND tablename = $2 AND indexname = $3`,
      [this.schema, this.table, `${this.table}_embedding_hnsw_idx`]
    );

    const indexDefinition = indexCheck.rows[0]?.indexdef as string | undefined;
    if (!indexDefinition || !indexDefinition.includes('USING hnsw')) {
      throw new Error(
        `Expected HNSW index ${this.table}_embedding_hnsw_idx on ${this.schema}.${this.table}. Run migrations or enable auto migration.`
      );
    }
  }

  private async ensureTenant(client: PoolClient, tenantId: string): Promise<void> {
    const cachedAt = this.tenantCache.get(tenantId);
    if (cachedAt && Date.now() - cachedAt < this.config.tenantCacheTtlMs) {
      return;
    }

    await client.query(
      `INSERT INTO ${this.schema}.tenants (tenant_id, last_seen_at)
       VALUES ($1, timezone('utc', now()))
       ON CONFLICT (tenant_id)
       DO UPDATE SET last_seen_at = EXCLUDED.last_seen_at;`,
      [tenantId]
    );

    this.tenantCache.set(tenantId, Date.now());
  }

  private async withClient<T>(handler: (client: PoolClient) => Promise<T>): Promise<T> {
    const client = await this.pool.connect();
    try {
      // Perform schema setup on first connection
      if (!this.schemaSetupDone) {
        await this.setupDatabaseIfNeeded(client);
        this.schemaSetupDone = true;
        this.logger.info('Database schema setup completed');
      }
      return await handler(client);
    } finally {
      client.release();
    }
  }
}
