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
      connectionTimeoutMillis: config?.connectionTimeoutMillis || 5000
    };

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

      // Verify required tables exist
      const tablesResult = await client.query(`
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN ('candidate_embeddings', 'embedding_metadata')
      `);

      if (tablesResult.rows.length < 2) {
        throw new PgVectorException(
          PgVectorError.VALIDATION_ERROR,
          'Required tables not found. Please run pgvector_schema.sql'
        );
      }

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
        // Use the database function for idempotent upsert
        const result = await client.query(
          'SELECT upsert_candidate_embedding($1, $2, $3, $4, $5) AS id',
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
              'SELECT upsert_candidate_embedding($1, $2, $3, $4, $5) AS id',
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
    similarityThreshold: number = 0.7,
    maxResults: number = 10,
    modelVersion?: string,
    chunkType: string = 'full_profile',
    filters?: { current_level?: string | string[] }
  ): Promise<SearchResult[]> {
    this.validateEmbedding(queryEmbedding);

    try {
      const client = await this.pool.connect();
      try {
        if (!filters || Object.keys(filters).length === 0) {
          // Use the optimized stored procedure if no filters (Legacy path)
          const result = await client.query(
            'SELECT * FROM similarity_search($1, $2, $3, $4, $5)',
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
          let sql = `
             SELECT candidate_id, 1 - (embedding <=> $1) as similarity, 
                    metadata, model_version, chunk_type
             FROM candidate_embeddings
             WHERE model_version = $2 
               AND chunk_type = $3
               AND 1 - (embedding <=> $1) > $4
           `;

          const params: any[] = [
            JSON.stringify(queryEmbedding),
            modelVersion || 'vertex-ai-textembedding-004',
            chunkType,
            similarityThreshold
          ];

          // Apply Strict Level Filtering
          if (filters.current_level) {
            const levels = Array.isArray(filters.current_level)
              ? filters.current_level
              : [filters.current_level];

            // Postgres JSONB containment or text match
            // Simplest: Check if metadata->>'current_level' is in the array
            sql += ` AND metadata->>'current_level' = ANY($${params.length + 1})`;
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
        let query = `
          SELECT id, candidate_id, embedding, model_version, chunk_type, 
                 metadata, created_at, updated_at
          FROM candidate_embeddings 
          WHERE candidate_id = $1
        `;
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

        // Delete from both tables
        const embeddingResult = await client.query(
          'DELETE FROM candidate_embeddings WHERE candidate_id = $1',
          [candidateId]
        );

        await client.query(
          'DELETE FROM embedding_metadata WHERE candidate_id = $1',
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
        const totalStats = await client.query(`
          SELECT 
            COUNT(DISTINCT candidate_id) as total_candidates,
            COUNT(*) as total_embeddings,
            MAX(updated_at) as last_updated
          FROM candidate_embeddings
        `);

        const modelStats = await client.query(`
          SELECT 
            model_version,
            chunk_type,
            COUNT(*) as total_embeddings,
            MIN(created_at) as first_created,
            MAX(updated_at) as last_updated
          FROM candidate_embeddings
          GROUP BY model_version, chunk_type
        `);

        const processingStats = await client.query('SELECT * FROM processing_stats');

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
          processing_stats: processingStats.rows.map(row => ({
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

        // Check required tables
        const tables = await client.query(`
          SELECT COUNT(*) as count FROM information_schema.tables 
          WHERE table_schema = 'public' 
          AND table_name IN ('candidate_embeddings', 'embedding_metadata')
        `);
        health.tables_exist = tables.rows[0].count == 2;

        // Check vector indexes
        const indexes = await client.query(`
          SELECT COUNT(*) as count FROM pg_indexes 
          WHERE tablename = 'candidate_embeddings'
          AND indexname LIKE '%vector%'
        `);
        health.indexes_exist = indexes.rows[0].count > 0;

        // Get total embeddings count
        const embeddingsCount = await client.query(`
          SELECT COUNT(*) as count FROM candidate_embeddings
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