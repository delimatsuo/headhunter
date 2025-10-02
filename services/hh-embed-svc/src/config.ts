import { getConfig as getBaseConfig, type ServiceConfig } from '@hh/common';

import type { EmbeddingProviderName } from './types';

export interface PgVectorSettings {
  host: string;
  port: number;
  database: string;
  user: string;
  password: string;
  ssl: boolean;
  poolMax: number;
  poolMin: number;
  idleTimeoutMillis: number;
  connectionTimeoutMillis: number;
  statementTimeoutMillis: number;
  schema: string;
  table: string;
  tenantCacheTtlMs: number;
  dimensions: number;
  hnswEfSearch?: number;
  enableAutoMigrate: boolean;
}

export interface VertexAiSettings {
  projectId: string;
  location: string;
  model: string;
}

export interface TogetherSettings {
  apiKey?: string;
  model?: string;
}

export interface EmbeddingRuntimeSettings {
  provider: EmbeddingProviderName;
  dimensions: number;
  queryLimit: number;
  similarityThreshold: number;
  upsertBatchSize: number;
}

export interface EmbeddingProviderSettings {
  vertex: VertexAiSettings;
  together: TogetherSettings;
  localDimensions: number;
}

export interface EmbeddingsServiceConfig {
  base: ServiceConfig;
  pgvector: PgVectorSettings;
  runtime: EmbeddingRuntimeSettings;
  providers: EmbeddingProviderSettings;
}

let cachedConfig: EmbeddingsServiceConfig | null = null;

function parseNumber(value: string | undefined, defaultValue: number): number {
  if (value === undefined) {
    return defaultValue;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : defaultValue;
}

function parseBoolean(value: string | undefined, defaultValue: boolean): boolean {
  if (value === undefined) {
    return defaultValue;
  }

  const normalized = value.trim().toLowerCase();
  if (['true', '1', 'yes', 'y', 'on'].includes(normalized)) {
    return true;
  }

  if (['false', '0', 'no', 'n', 'off'].includes(normalized)) {
    return false;
  }

  return defaultValue;
}

function resolveProviderName(): EmbeddingProviderName {
  const value = (process.env.EMBEDDING_PROVIDER ?? 'vertex-ai').toLowerCase();
  if (value === 'vertex' || value === 'vertex-ai') {
    return 'vertex-ai';
  }
  if (value === 'together') {
    return 'together';
  }
  return 'local';
}

export function getEmbeddingsServiceConfig(): EmbeddingsServiceConfig {
  if (cachedConfig) {
    return cachedConfig;
  }

  const base = getBaseConfig();
  const runtime: EmbeddingRuntimeSettings = {
    provider: resolveProviderName(),
    dimensions: parseNumber(process.env.EMBEDDING_DIMENSIONS, 768),
    queryLimit: parseNumber(process.env.EMBEDDING_QUERY_LIMIT, 20),
    similarityThreshold: Number.parseFloat(process.env.EMBEDDING_SIMILARITY_THRESHOLD ?? '0.75'),
    upsertBatchSize: parseNumber(process.env.EMBEDDING_UPSERT_BATCH_SIZE, 50)
  };

  if (Number.isNaN(runtime.similarityThreshold) || runtime.similarityThreshold <= 0 || runtime.similarityThreshold > 1) {
    runtime.similarityThreshold = 0.75;
  }

  const hnswEfSearchRaw = process.env.PGVECTOR_HNSW_EF_SEARCH;
  const parsedEfSearch = hnswEfSearchRaw !== undefined ? Number(hnswEfSearchRaw) : undefined;
  const hnswEfSearch =
    parsedEfSearch !== undefined && Number.isFinite(parsedEfSearch) && parsedEfSearch > 0
      ? parsedEfSearch
      : undefined;

  const pgvector: PgVectorSettings = {
    host: process.env.PGVECTOR_HOST ?? '127.0.0.1',
    port: parseNumber(process.env.PGVECTOR_PORT, 5432),
    database: process.env.PGVECTOR_DATABASE ?? 'headhunter',
    user: process.env.PGVECTOR_USER ?? 'postgres',
    password: process.env.PGVECTOR_PASSWORD ?? '',
    ssl: parseBoolean(process.env.PGVECTOR_SSL, false),
    poolMax: parseNumber(process.env.PGVECTOR_POOL_MAX, 10),
    poolMin: parseNumber(process.env.PGVECTOR_POOL_MIN, 0),
    idleTimeoutMillis: parseNumber(process.env.PGVECTOR_IDLE_TIMEOUT_MS, 30_000),
    connectionTimeoutMillis: parseNumber(process.env.PGVECTOR_CONNECTION_TIMEOUT_MS, 5_000),
    statementTimeoutMillis: parseNumber(process.env.PGVECTOR_STATEMENT_TIMEOUT_MS, 30_000),
    schema: process.env.PGVECTOR_SCHEMA ?? 'search',
    table: process.env.PGVECTOR_TABLE ?? 'candidate_embeddings',
    tenantCacheTtlMs: parseNumber(process.env.PGVECTOR_TENANT_CACHE_TTL_MS, 60_000),
    dimensions: runtime.dimensions,
    hnswEfSearch,
    enableAutoMigrate: parseBoolean(process.env.ENABLE_AUTO_MIGRATE, false)
  };

  const providers: EmbeddingProviderSettings = {
    vertex: {
      projectId: process.env.GCP_PROJECT_ID ?? process.env.GOOGLE_CLOUD_PROJECT ?? 'local-project',
      location: process.env.GCP_LOCATION ?? 'us-central1',
      model: process.env.VERTEX_AI_MODEL ?? 'text-embedding-004'
    },
    together: {
      apiKey: process.env.TOGETHER_API_KEY,
      model: process.env.TOGETHER_EMBEDDING_MODEL ?? 'togethercomputer/m2-bert-80M-8k-retrieval'
    },
    localDimensions: parseNumber(process.env.LOCAL_EMBEDDING_DIM, runtime.dimensions)
  };

  cachedConfig = {
    base,
    pgvector,
    runtime,
    providers
  };

  return cachedConfig;
}

export function resetEmbeddingsServiceConfig(): void {
  cachedConfig = null;
}
