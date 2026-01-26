/**
 * PgVector Client - TypeScript wrapper for Cloud SQL pgvector operations
 * Integrates with the Python pgvector_store.py functionality for semantic search
 */

import { Pool, PoolConfig } from 'pg';
import { registerType } from 'pgvector/pg';
import * as dotenv from 'dotenv';

// Load environment variables
dotenv.config();

export interface PgVectorConfig {
  host: string;
  port: number;
  database: string;
  user: string;
  password: string;
  ssl: boolean | object;
  maxConnections: number;
  idleTimeoutMillis: number;
  connectionTimeoutMillis: number;
  schema: string;
}

export interface EmbeddingRecord {
  id?: string;
  candidate_id: string;
  embedding: number[];
  model_version: string;
  chunk_type: string;
  metadata?: Record<string, any>;
  created_at?: Date;
  updated_at?: Date;
}

export interface SearchResult {
  candidate_id: string;
  similarity: number;
  metadata: Record<string, any>;
  model_version: string;
  chunk_type: string;
}

/**
 * Candidate record returned from PostgreSQL batch lookup
 * Used to enrich search results without Firestore
 */
export interface CandidateRecord {
  id: number;
  first_name: string | null;
  last_name: string | null;
  name: string | null;
  headline: string | null;
  location: string | null;
  country: string | null;
  linkedin_url: string | null;
  intelligent_analysis: Record<string, any> | null;
  specialties: string[];
  resume_text: string | null;
  tenant_id: string | null;
  view_count: number;
  current_title: string | null;
  current_company: string | null;
}

export interface EmbeddingStats {
  total_candidates: number;
  total_embeddings: number;
  model_stats: Array<{
    model_version: string;
    chunk_type: string;
    total_embeddings: number;
    avg_dimensions: number;
    first_created: Date;
    last_updated: Date;
  }>;
  processing_stats: Array<{
    processing_status: string;
    candidate_count: number;
    avg_embeddings_per_candidate: number;
    oldest_processed: Date;
    latest_processed: Date;
  }>;
  last_updated?: string;
}

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  database_connected: boolean;
  pgvector_available: boolean;
  tables_exist: boolean;
  indexes_exist: boolean;
  connection_pool_size: number;
  total_embeddings: number;
  timestamp: string;
  error?: string;
}

export enum PgVectorError {
  CONNECTION_ERROR = 'CONNECTION_ERROR',
  QUERY_ERROR = 'QUERY_ERROR',
  TIMEOUT_ERROR = 'TIMEOUT_ERROR',
  VALIDATION_ERROR = 'VALIDATION_ERROR'
}

export class PgVectorException extends Error {
  constructor(
    public readonly type: PgVectorError,
    message: string,
    public readonly originalError?: Error
  ) {
    super(message);
    this.name = 'PgVectorException';
  }
}

/**
 * TypeScript client for Cloud SQL pgvector operations
 * Provides semantic search and embedding storage with connection pooling
 */
export class PgVectorClient {
  private pool: Pool;
  private isInitialized = false;
  private schema: string;

  constructor(config?: Partial<PgVectorConfig>) {
    const fullConfig: PgVectorConfig = {
      host: config?.host || process.env.PGVECTOR_HOST || 'localhost',
      port: config?.port || parseInt(process.env.PGVECTOR_PORT || '5432'),
      database: config?.database || process.env.PGVECTOR_DATABASE || 'headhunter',
      user: config?.user || process.env.PGVECTOR_USER || 'postgres',
      password: config?.password || process.env.PGVECTOR_PASSWORD || '',
      ssl: config?.ssl || (process.env.PGVECTOR_SSL_MODE === 'require'),
      maxConnections: config?.maxConnections || parseInt(process.env.PGVECTOR_MAX_CONNECTIONS || '20'),
      idleTimeoutMillis: config?.idleTimeoutMillis || parseInt(process.env.PGVECTOR_IDLE_TIMEOUT_MILLIS || '30000'),
      connectionTimeoutMillis: config?.connectionTimeoutMillis || 5000,
      schema: config?.schema || process.env.PGVECTOR_SCHEMA || 'sourcing'
    };

    this.schema = fullConfig.schema;
    console.log(`[PgVectorClient] Using schema: ${this.schema}`);

    this.pool = new Pool({
      host: fullConfig.host,
      port: fullConfig.port,
      database: fullConfig.database,
      user: fullConfig.user,
      password: fullConfig.password,
      ssl: fullConfig.ssl,
      max: fullConfig.maxConnections,
      idleTimeoutMillis: fullConfig.idleTimeoutMillis,
      connectionTimeoutMillis: fullConfig.connectionTimeoutMillis,
      // Retry logic
      reconnect: true,
      max_retries: 3,
      retry_delay: 1000,
    } as PoolConfig);

    // Handle pool errors
    this.pool.on('error', (err) => {
      console.error('PostgreSQL pool error:', err);
    });

    this.pool.on('connect', (client) => {
      // Register pgvector types on each connection
      registerType(client);
    });
  }

  /**
   * Initialize the client and verify database connectivity
   */
  async initialize(): Promise<void> {
    try {
      const client = await this.pool.connect();

      // Register pgvector types
      registerType(client);

      // Verify pgvector extension exists
      const extensionResult = await client.query(
        "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
      );

      if (extensionResult.rows.length === 0) {
        throw new PgVectorException(
          PgVectorError.VALIDATION_ERROR,
          'pgvector extension not found. Please run CREATE EXTENSION vector;'
        );
      }

      // Verify required tables exist in the configured schema
      // For sourcing schema, we query the underlying 'embeddings' table directly
      // For other schemas, we look for 'candidate_embeddings' table/view
      const embeddingsTable = this.schema === 'sourcing' ? 'embeddings' : 'candidate_embeddings';
      const tablesResult = await client.query(`
        SELECT tablename as name FROM pg_tables
        WHERE schemaname = $1
        AND tablename = $2
        UNION
        SELECT viewname as name FROM pg_views
        WHERE schemaname = $1
        AND viewname = $2
      `, [this.schema, embeddingsTable]);

      if (tablesResult.rows.length === 0) {
        throw new PgVectorException(
          PgVectorError.VALIDATION_ERROR,
          `Required table/view '${embeddingsTable}' not found in schema '${this.schema}'. Please run migrations.`
        );
      }
      console.log(`[PgVectorClient] Found ${embeddingsTable} in schema ${this.schema}`);

      client.release();
      this.isInitialized = true;
      console.log('PgVectorClient initialized successfully');
    } catch (error) {
      throw new PgVectorException(
        PgVectorError.CONNECTION_ERROR,
        `Failed to initialize PgVectorClient: ${(error as Error).message}`,
        error as Error
      );
    }
  }

  /**
   * Store an embedding with idempotent upsert (PRD line 143)
   */
  async storeEmbedding(
    candidateId: string,
    embedding: number[],
    modelVersion: string = 'vertex-ai-textembedding-gecko',
    chunkType: string = 'full_profile',
    metadata?: Record<string, any>
  ): Promise<string> {
    this.validateEmbedding(embedding);

    try {
      const client = await this.pool.connect();
      try {
        // Use the database function for idempotent upsert (schema-qualified)
        const result = await client.query(
          `SELECT ${this.schema}.upsert_candidate_embedding($1, $2, $3, $4, $5) AS id`,
          [
            candidateId,
            JSON.stringify(embedding), // Serialize embedding as JSON
            modelVersion,
            chunkType,
            metadata ? JSON.stringify(metadata) : null
          ]
        );

        return result.rows[0].id;
      } finally {
        client.release();
      }
    } catch (error) {
      throw new PgVectorException(
        PgVectorError.QUERY_ERROR,
        `Failed to store embedding for candidate ${candidateId}: ${(error as Error).message}`,
        error as Error
      );
    }
  }

  /**
   * Batch store embeddings for improved performance
   */
  async batchStoreEmbeddings(
    embeddings: EmbeddingRecord[],
    batchSize: number = 100
  ): Promise<string[]> {
    if (!embeddings || embeddings.length === 0) {
      return [];
    }

    // Validate all embeddings
    embeddings.forEach(record => {
      this.validateEmbedding(record.embedding);
    });

    const resultIds: string[] = [];

    try {
      const client = await this.pool.connect();
      try {
        await client.query('BEGIN');

        for (let i = 0; i < embeddings.length; i += batchSize) {
          const batch = embeddings.slice(i, i + batchSize);

          for (const record of batch) {
            const result = await client.query(
              `SELECT ${this.schema}.upsert_candidate_embedding($1, $2, $3, $4, $5) AS id`,
              [
                record.candidate_id,
                JSON.stringify(record.embedding), // Serialize embedding as JSON
                record.model_version,
                record.chunk_type,
                record.metadata ? JSON.stringify(record.metadata) : null
              ]
            );
            resultIds.push(result.rows[0].id);
          }
        }

        await client.query('COMMIT');
      } catch (error) {
        await client.query('ROLLBACK');
        throw error;
      } finally {
        client.release();
      }
    } catch (error) {
      throw new PgVectorException(
        PgVectorError.QUERY_ERROR,
        `Failed to batch store embeddings: ${(error as Error).message}`,
        error as Error
      );
    }

    return resultIds;
  }

  /**
   * Search for similar embeddings using cosine similarity
   */
  async searchSimilar(
    queryEmbedding: number[],
    similarityThreshold: number = 0.25,
    maxResults: number = 10,
    modelVersion?: string,
    chunkType: string = 'full_profile',
    filters?: { current_level?: string | string[]; countries?: string[]; specialties?: string[] }
  ): Promise<SearchResult[]> {
    this.validateEmbedding(queryEmbedding);
    console.log(`[PgVectorClient] searchSimilar: threshold=${similarityThreshold}, maxResults=${maxResults}`);

    try {
      const client = await this.pool.connect();
      try {
        // Check if we need country filtering
        const hasCountryFilter = filters?.countries && filters.countries.length > 0;

        if (!filters || (Object.keys(filters).length === 0 && !hasCountryFilter)) {
          // Use the optimized stored procedure if no filters (Legacy path)
          // Call schema-qualified similarity_search function
          const result = await client.query(
            `SELECT * FROM ${this.schema}.similarity_search($1, $2, $3, $4, $5)`,
            [
              JSON.stringify(queryEmbedding),
              similarityThreshold,
              maxResults,
              modelVersion,
              chunkType
            ]
          );
          return result.rows.map(row => ({
            candidate_id: row.candidate_id,
            similarity: parseFloat(row.similarity),
            metadata: row.metadata || {},
            model_version: row.model_version,
            chunk_type: row.chunk_type
          }));
        } else {
          // Dynamic SQL for filtering (Agentic Sourcing path)
          // standard cosine similarity: 1 - (embedding <=> query)
          // For sourcing schema, query underlying tables directly (embeddings + candidates)
          // For other schemas, query candidate_embeddings view
          const isSourcingSchema = this.schema === 'sourcing';

          let sql: string;
          if (isSourcingSchema) {
            // Query sourcing.embeddings table directly (no view permission issues)
            sql = `
             SELECT e.candidate_id::text as candidate_id,
                    1 - (e.embedding <=> $1) as similarity,
                    jsonb_build_object('model_version', e.model_version, 'source', 'sourcing') as metadata,
                    e.model_version, 'default' as chunk_type
             FROM sourcing.embeddings e
             JOIN sourcing.candidates c ON c.id = e.candidate_id
           `;
          } else {
            sql = `
             SELECT ce.candidate_id,
                    1 - (ce.embedding <=> $1) as similarity,
                    ce.metadata, ce.model_version, ce.chunk_type
             FROM ${this.schema}.candidate_embeddings ce
           `;
          }

          // Build params array based on schema (sourcing schema doesn't use chunkType)
          let params: any[];
          if (isSourcingSchema) {
            params = [
              JSON.stringify(queryEmbedding),
              modelVersion || 'text-embedding-004', // Must match model used by sourcing_embeddings.py
              similarityThreshold
            ];
          } else {
            params = [
              JSON.stringify(queryEmbedding),
              modelVersion || 'vertex-ai-textembedding-004',
              chunkType,
              similarityThreshold
            ];
          }

          // Add JOIN for country filtering if needed (only for non-sourcing schemas)
          if (hasCountryFilter && !isSourcingSchema) {
            sql += ` LEFT JOIN ${this.schema}.candidate_profiles cp ON ce.candidate_id = cp.candidate_id`;
          }

          // Build WHERE clause based on schema
          if (isSourcingSchema) {
            sql += `
             WHERE e.model_version = $2
               AND c.deleted_at IS NULL
               AND c.consent_status != 'opted_out'
               AND 1 - (e.embedding <=> $1) > $3
           `;
          } else {
            sql += `
             WHERE ce.model_version = $2
               AND ce.chunk_type = $3
               AND 1 - (ce.embedding <=> $1) > $4
           `;
          }

          // Apply Country Filtering (include specified countries OR NULL)
          // This ensures we show candidates in the target country plus those with unknown location
          if (hasCountryFilter) {
            if (isSourcingSchema) {
              sql += ` AND (c.country = ANY($${params.length + 1}::text[]) OR c.country IS NULL)`;
            } else {
              sql += ` AND (cp.country = ANY($${params.length + 1}::text[]) OR cp.country IS NULL)`;
            }
            params.push(filters!.countries);
          }

          // Apply Specialty Filtering (for engineering role searches)
          // Filter by PRIMARY specialty (first element of array) for precision
          // This ensures backend searches return backend engineers, not former-backend-now-frontend
          const hasSpecialtyFilter = filters?.specialties && filters.specialties.length > 0;
          if (hasSpecialtyFilter && isSourcingSchema) {
            // Match candidates whose PRIMARY specialty (first array element) is in target list
            // PostgreSQL arrays are 1-indexed, so specialties[1] is the primary specialty
            // Also include candidates without specialty data (let Gemini evaluate them)
            sql += ` AND (c.specialties[1] = ANY($${params.length + 1}::text[]) OR c.specialties = '{}' OR c.specialties IS NULL)`;
            params.push(filters!.specialties);
          }

          // Apply Strict Level Filtering (not applicable for sourcing schema currently)
          if (filters?.current_level && !isSourcingSchema) {
            const levels = Array.isArray(filters.current_level)
              ? filters.current_level
              : [filters.current_level];

            // Postgres JSONB containment or text match
            // Simplest: Check if metadata->>'current_level' is in the array
            sql += ` AND ce.metadata->>'current_level' = ANY($${params.length + 1})`;
            params.push(levels);
          }

          sql += ` ORDER BY similarity DESC LIMIT $${params.length + 1}`;
          params.push(maxResults);

          const result = await client.query(sql, params);

          return result.rows.map(row => ({
            candidate_id: row.candidate_id,
            similarity: parseFloat(row.similarity),
            metadata: row.metadata || {},
            model_version: row.model_version,
            chunk_type: row.chunk_type
          }));
        }

      } finally {
        client.release();
      }
    } catch (error) {
      throw new PgVectorException(
        PgVectorError.QUERY_ERROR,
        `Failed to search similar embeddings: ${(error as Error).message}`,
        error as Error
      );
    }
  }

  /**
   * Get embeddings for a specific candidate
   */
  async getCandidateEmbeddings(
    candidateId: string,
    modelVersion?: string
  ): Promise<EmbeddingRecord[]> {
    try {
      const client = await this.pool.connect();
      try {
        // For sourcing schema, query underlying embeddings table directly
        const isSourcingSchema = this.schema === 'sourcing';
        let query: string;

        if (isSourcingSchema) {
          query = `
            SELECT id::text, candidate_id::text as candidate_id,
                   embedding, model_version, 'default' as chunk_type,
                   jsonb_build_object('model_version', model_version) as metadata,
                   created_at, created_at as updated_at
            FROM sourcing.embeddings
            WHERE candidate_id::text = $1
          `;
        } else {
          query = `
            SELECT id, candidate_id,
                   embedding, model_version, chunk_type,
                   metadata, created_at, updated_at
            FROM ${this.schema}.candidate_embeddings
            WHERE candidate_id = $1
          `;
        }
        const params: any[] = [candidateId];

        if (modelVersion) {
          query += ' AND model_version = $2';
          params.push(modelVersion);
        }

        query += ' ORDER BY created_at DESC';

        const result = await client.query(query, params);

        return result.rows.map(row => ({
          id: row.id,
          candidate_id: row.candidate_id,
          embedding: row.embedding,
          model_version: row.model_version,
          chunk_type: row.chunk_type,
          metadata: row.metadata || {},
          created_at: row.created_at,
          updated_at: row.updated_at
        }));
      } finally {
        client.release();
      }
    } catch (error) {
      throw new PgVectorException(
        PgVectorError.QUERY_ERROR,
        `Failed to get embeddings for candidate ${candidateId}: ${(error as Error).message}`,
        error as Error
      );
    }
  }

  /**
   * Delete all embeddings for a candidate
   */
  async deleteCandidateEmbeddings(candidateId: string): Promise<number> {
    try {
      const client = await this.pool.connect();
      try {
        await client.query('BEGIN');

        // Delete from both tables in the configured schema
        const embeddingResult = await client.query(
          `DELETE FROM ${this.schema}.candidate_embeddings WHERE candidate_id = $1`,
          [candidateId]
        );

        await client.query(
          `DELETE FROM ${this.schema}.embedding_metadata WHERE candidate_id = $1`,
          [candidateId]
        );

        await client.query('COMMIT');

        return embeddingResult.rowCount || 0;
      } catch (error) {
        await client.query('ROLLBACK');
        throw error;
      } finally {
        client.release();
      }
    } catch (error) {
      throw new PgVectorException(
        PgVectorError.QUERY_ERROR,
        `Failed to delete embeddings for candidate ${candidateId}: ${(error as Error).message}`,
        error as Error
      );
    }
  }

  /**
   * Get statistics about stored embeddings
   */
  async getEmbeddingStats(): Promise<EmbeddingStats> {
    try {
      const client = await this.pool.connect();
      try {
        // Avoid using the expensive embedding_stats view which converts vectors to text
        // For sourcing schema, query underlying embeddings table
        const isSourcingSchema = this.schema === 'sourcing';
        const embeddingsTable = isSourcingSchema ? 'embeddings' : 'candidate_embeddings';

        const totalStats = await client.query(`
          SELECT
            COUNT(DISTINCT candidate_id) as total_candidates,
            COUNT(*) as total_embeddings,
            MAX(created_at) as last_updated
          FROM ${this.schema}.${embeddingsTable}
        `);

        const modelStatsQuery = isSourcingSchema
          ? `SELECT model_version, 'default' as chunk_type, COUNT(*) as total_embeddings,
                    MIN(created_at) as first_created, MAX(created_at) as last_updated
             FROM ${this.schema}.${embeddingsTable}
             GROUP BY model_version`
          : `SELECT model_version, chunk_type, COUNT(*) as total_embeddings,
                    MIN(created_at) as first_created, MAX(updated_at) as last_updated
             FROM ${this.schema}.${embeddingsTable}
             GROUP BY model_version, chunk_type`;
        const modelStats = await client.query(modelStatsQuery);

        // processing_stats may not exist in sourcing schema
        let processingStats: any = { rows: [] };
        try {
          processingStats = await client.query(`SELECT * FROM ${this.schema}.processing_stats`);
        } catch (e) {
          // Table doesn't exist in sourcing schema, use empty result
        }

        return {
          total_candidates: parseInt(totalStats.rows[0]?.total_candidates || '0'),
          total_embeddings: parseInt(totalStats.rows[0]?.total_embeddings || '0'),
          last_updated: totalStats.rows[0]?.last_updated?.toISOString(),
          model_stats: modelStats.rows.map(row => ({
            model_version: row.model_version,
            chunk_type: row.chunk_type,
            total_embeddings: parseInt(row.total_embeddings),
            avg_dimensions: 768, // Hardcoded to avoid expensive calculation
            first_created: row.first_created,
            last_updated: row.last_updated
          })),
          processing_stats: processingStats.rows.map((row: any) => ({
            processing_status: row.processing_status,
            candidate_count: parseInt(row.candidate_count),
            avg_embeddings_per_candidate: parseFloat(row.avg_embeddings_per_candidate),
            oldest_processed: row.oldest_processed,
            latest_processed: row.latest_processed
          }))
        };
      } finally {
        client.release();
      }
    } catch (error) {
      throw new PgVectorException(
        PgVectorError.QUERY_ERROR,
        `Failed to get embedding stats: ${(error as Error).message}`,
        error as Error
      );
    }
  }

  /**
   * Get total candidate count from the sourcing schema (unified database)
   * Throws on error so caller can fallback to alternative count source
   */
  async getTotalCandidateCount(): Promise<number> {
    const client = await this.pool.connect();
    try {
      // Query underlying table directly - views have permission issues
      const result = await client.query(`
        SELECT COUNT(*) as total
        FROM sourcing.candidates
        WHERE deleted_at IS NULL AND consent_status != 'opted_out'
      `);
      const count = parseInt(result.rows[0]?.total || '0');
      console.log(`[PgVectorClient] sourcing.candidates count: ${count}`);
      return count;
    } finally {
      client.release();
    }
  }

  /**
   * Batch lookup candidates by their IDs from PostgreSQL
   * Used to enrich search results without N+1 Firestore queries
   */
  async getCandidatesByIds(ids: number[]): Promise<Map<number, CandidateRecord>> {
    if (!ids || ids.length === 0) {
      return new Map();
    }

    const client = await this.pool.connect();
    try {
      // Query sourcing.candidates table directly
      const result = await client.query(`
        SELECT
          c.id,
          c.first_name,
          c.last_name,
          COALESCE(NULLIF(TRIM(CONCAT(c.first_name, ' ', c.last_name)), ''), 'Unknown') as name,
          c.headline,
          c.location,
          c.country,
          c.linkedin_url,
          c.intelligent_analysis,
          c.specialties,
          c.summary as resume_text
        FROM sourcing.candidates c
        WHERE c.id = ANY($1)
          AND c.deleted_at IS NULL
          AND COALESCE(c.consent_status, '') != 'opted_out'
      `, [ids]);

      const candidatesMap = new Map<number, CandidateRecord>();
      for (const row of result.rows) {
        candidatesMap.set(row.id, {
          id: row.id,
          first_name: row.first_name,
          last_name: row.last_name,
          name: row.name,
          headline: row.headline,
          location: row.location,
          country: row.country,
          linkedin_url: row.linkedin_url,
          intelligent_analysis: row.intelligent_analysis,
          specialties: row.specialties || [],
          resume_text: row.resume_text,
          tenant_id: null, // Not applicable for sourcing schema
          view_count: 0,   // Would need separate query
          current_title: row.intelligent_analysis?.career_trajectory_analysis?.current_level || row.headline,
          current_company: row.intelligent_analysis?.personal_details?.current_company || null
        });
      }

      console.log(`[PgVectorClient] getCandidatesByIds: requested ${ids.length}, found ${candidatesMap.size}`);
      return candidatesMap;
    } finally {
      client.release();
    }
  }

  /**
   * Search candidates by name or email in PostgreSQL
   * Returns matching candidates with high artificial similarity
   */
  async searchCandidatesByName(query: string, limit: number = 20): Promise<CandidateRecord[]> {
    if (!query || query.trim().length === 0) {
      return [];
    }

    const normalizedQuery = query.trim().toLowerCase();
    const client = await this.pool.connect();

    try {
      const results: CandidateRecord[] = [];

      // Check if query looks like an email
      if (normalizedQuery.includes('@')) {
        // Exact email match (not stored in current schema, skip)
        // TODO: Add email column to sourcing.candidates if needed
      }

      // Name search - partial match on first_name + last_name
      const nameResult = await client.query(`
        SELECT
          c.id,
          c.first_name,
          c.last_name,
          COALESCE(NULLIF(TRIM(CONCAT(c.first_name, ' ', c.last_name)), ''), 'Unknown') as name,
          c.headline,
          c.location,
          c.country,
          c.linkedin_url,
          c.intelligent_analysis,
          c.specialties,
          c.summary as resume_text
        FROM sourcing.candidates c
        WHERE (
          LOWER(CONCAT(c.first_name, ' ', c.last_name)) LIKE $1
          OR LOWER(c.first_name) LIKE $1
          OR LOWER(c.last_name) LIKE $1
        )
        AND c.deleted_at IS NULL
        AND COALESCE(c.consent_status, '') != 'opted_out'
        AND COALESCE(NULLIF(TRIM(CONCAT(c.first_name, ' ', c.last_name)), ''), 'Unknown') NOT IN ('Unknown', 'Processing...')
        LIMIT $2
      `, [`%${normalizedQuery}%`, limit]);

      for (const row of nameResult.rows) {
        results.push({
          id: row.id,
          first_name: row.first_name,
          last_name: row.last_name,
          name: row.name,
          headline: row.headline,
          location: row.location,
          country: row.country,
          linkedin_url: row.linkedin_url,
          intelligent_analysis: row.intelligent_analysis,
          specialties: row.specialties || [],
          resume_text: row.resume_text,
          tenant_id: null,
          view_count: 0,
          current_title: row.intelligent_analysis?.career_trajectory_analysis?.current_level || row.headline,
          current_company: row.intelligent_analysis?.personal_details?.current_company || null
        });
      }

      console.log(`[PgVectorClient] searchCandidatesByName('${query}'): found ${results.length} matches`);
      return results;
    } finally {
      client.release();
    }
  }

  /**
   * Perform health check on database connection and pgvector functionality
   */
  async healthCheck(): Promise<HealthStatus> {
    const health: HealthStatus = {
      status: 'unhealthy',
      database_connected: false,
      pgvector_available: false,
      tables_exist: false,
      indexes_exist: false,
      connection_pool_size: 0,
      total_embeddings: 0,
      timestamp: new Date().toISOString()
    };

    try {
      const client = await this.pool.connect();
      try {
        // Check basic connection
        await client.query('SELECT 1');
        health.database_connected = true;

        // Check pgvector extension
        const extension = await client.query(
          "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
        );
        health.pgvector_available = extension.rows.length > 0;

        // Check required tables/views in the configured schema
        // For sourcing schema, check 'embeddings' table; for others check 'candidate_embeddings'
        const embeddingsTable = this.schema === 'sourcing' ? 'embeddings' : 'candidate_embeddings';
        const tables = await client.query(`
          SELECT COUNT(*) as count FROM (
            SELECT tablename FROM pg_tables
            WHERE schemaname = $1 AND tablename = $2
            UNION
            SELECT viewname FROM pg_views
            WHERE schemaname = $1 AND viewname = $2
          ) t
        `, [this.schema, embeddingsTable]);
        health.tables_exist = tables.rows[0].count >= 1;

        // Check vector indexes in the configured schema
        // For sourcing schema, check the underlying 'embeddings' table if using views
        const indexes = await client.query(`
          SELECT COUNT(*) as count FROM pg_indexes
          WHERE schemaname = $1
          AND (tablename = 'candidate_embeddings' OR tablename = 'embeddings')
          AND (indexname LIKE '%vector%' OR indexname LIKE '%hnsw%')
        `, [this.schema]);
        health.indexes_exist = indexes.rows[0].count > 0;

        // Get total embeddings count from the configured schema
        const embeddingsTableName = this.schema === 'sourcing' ? 'embeddings' : 'candidate_embeddings';
        const embeddingsCount = await client.query(`
          SELECT COUNT(*) as count FROM ${this.schema}.${embeddingsTableName}
        `);
        health.total_embeddings = parseInt(embeddingsCount.rows[0].count);

        health.connection_pool_size = this.pool.totalCount;

        if (health.database_connected && health.pgvector_available && health.tables_exist) {
          health.status = 'healthy';
        } else {
          health.status = 'degraded';
        }
      } finally {
        client.release();
      }
    } catch (error) {
      health.error = (error as Error).message;
    }

    return health;
  }

  /**
   * Close the connection pool
   */
  async close(): Promise<void> {
    await this.pool.end();
    this.isInitialized = false;
  }

  /**
   * Validate embedding vector dimensions
   */
  private validateEmbedding(embedding: number[]): void {
    if (!embedding || !Array.isArray(embedding)) {
      throw new PgVectorException(
        PgVectorError.VALIDATION_ERROR,
        'Embedding must be a non-empty array'
      );
    }

    if (embedding.length !== 768) {
      throw new PgVectorException(
        PgVectorError.VALIDATION_ERROR,
        `Embedding must be 768-dimensional, got ${embedding.length}`
      );
    }

    if (!embedding.every(x => typeof x === 'number' && !isNaN(x))) {
      throw new PgVectorException(
        PgVectorError.VALIDATION_ERROR,
        'All embedding values must be valid numbers'
      );
    }
  }
}

// Singleton instance for Cloud Functions
let pgVectorInstance: PgVectorClient | null = null;

/**
 * Get or create singleton PgVectorClient instance
 */
export async function getPgVectorClient(config?: Partial<PgVectorConfig>): Promise<PgVectorClient> {
  if (!pgVectorInstance) {
    pgVectorInstance = new PgVectorClient(config);
    await pgVectorInstance.initialize();
  }
  return pgVectorInstance;
}

/**
 * Close the singleton instance (for testing or cleanup)
 */
export async function closePgVectorClient(): Promise<void> {
  if (pgVectorInstance) {
    await pgVectorInstance.close();
    pgVectorInstance = null;
  }
}