import { getConfig as getBaseConfig, type ServiceConfig } from '@hh/common';

// Security: Allowed schema and table names to prevent SQL injection via env misconfiguration
const ALLOWED_SCHEMAS = ['search', 'public', 'test', 'sourcing'] as const;
const ALLOWED_TABLE_NAME_PATTERN = /^[a-z_][a-z0-9_]{0,62}$/;

function validateSchemaName(schema: string): string {
  if (!ALLOWED_SCHEMAS.includes(schema as (typeof ALLOWED_SCHEMAS)[number])) {
    throw new Error(
      `Invalid schema name: "${schema}". Allowed schemas: ${ALLOWED_SCHEMAS.join(', ')}`
    );
  }
  return schema;
}

function validateTableName(tableName: string, context: string): string {
  if (!ALLOWED_TABLE_NAME_PATTERN.test(tableName)) {
    throw new Error(
      `Invalid ${context} table name: "${tableName}". Must match pattern: ${ALLOWED_TABLE_NAME_PATTERN}`
    );
  }
  return tableName;
}

export interface EmbedServiceConfig {
  baseUrl: string;
  timeoutMs: number;
  authToken?: string;
  idTokenAudience?: string;
  retries: number;
  retryDelayMs: number;
  circuitBreakerFailures: number;
  circuitBreakerCooldownMs: number;
  healthTenantId?: string;
}

export interface PgVectorConfig {
  host: string;
  port: number;
  database: string;
  user: string;
  password: string;
  ssl: boolean;
  schema: string;
  embeddingsTable: string;
  profilesTable: string;
  dimensions: number;
  poolMax: number;
  poolMin: number;
  idleTimeoutMs: number;
  connectionTimeoutMs: number;
  statementTimeoutMs: number;
  hnswEfSearch?: number;
  enableAutoMigrate: boolean;
}

export interface RedisCacheConfig {
  host: string;
  port: number;
  password?: string;
  tls: boolean;
  tlsRejectUnauthorized: boolean;
  caCert?: string;
  keyPrefix: string;
  ttlSeconds: number;
  disable: boolean;
}

export interface SearchRuntimeConfig {
  vectorWeight: number;
  textWeight: number;
  minSimilarity: number;
  maxResults: number;
  ecoBoostFactor: number;
  confidenceFloor: number;
  warmupMultiplier: number;
  rerankCandidateLimit: number;
  rerankIncludeReasons: boolean;
  // RRF configuration
  rrfK: number;              // RRF k parameter, controls top-rank favoritism (default 60)
  perMethodLimit: number;    // Candidates retrieved per search method before fusion (default 100)
  enableRrf: boolean;        // Feature flag to toggle RRF vs weighted sum (default true)
  // Pipeline stage limits (PIPE-01)
  pipelineRetrievalLimit: number;  // Target retrieval count (default 500)
  pipelineScoringLimit: number;    // Top N after scoring (default 100)
  pipelineRerankLimit: number;     // Final top N after rerank (default 50)
  pipelineLogStages: boolean;      // Log stage transitions (default true)
}

export interface RerankServiceConfig {
  baseUrl: string;
  timeoutMs: number;
  retries: number;
  retryDelayMs: number;
  idTokenAudience?: string;
  authToken?: string;
  enabled: boolean;
}

export interface FirestoreFallbackConfig {
  enabled: boolean;
  concurrency: number;
}

/**
 * Signal weight environment configuration for multi-signal scoring.
 * These values provide defaults that can be overridden via request or role-type presets.
 */
export interface SignalWeightEnvConfig {
  /** Default vector similarity weight (0-1) */
  defaultVectorWeight: number;
  /** Default level/seniority match weight (0-1) */
  defaultLevelWeight: number;
  /** Default specialty match weight (0-1) */
  defaultSpecialtyWeight: number;
  /** Default tech stack match weight (0-1) */
  defaultTechStackWeight: number;
  /** Default function alignment weight (0-1) */
  defaultFunctionWeight: number;
  /** Default career trajectory weight (0-1) */
  defaultTrajectoryWeight: number;
  /** Default company pedigree weight (0-1) */
  defaultCompanyWeight: number;
  /** Weight for Gemini rerank score blending (default 0.7) */
  geminiBlendWeight: number;
}

export interface SearchServiceConfig {
  base: ServiceConfig;
  embed: EmbedServiceConfig;
  pgvector: PgVectorConfig;
  redis: RedisCacheConfig;
  rerank: RerankServiceConfig;
  search: SearchRuntimeConfig;
  firestoreFallback: FirestoreFallbackConfig;
  signalWeights: SignalWeightEnvConfig;
}

let cachedConfig: SearchServiceConfig | null = null;

function parseNumber(value: string | undefined, defaultValue: number): number {
  if (value === undefined) {
    return defaultValue;
  }

  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return defaultValue;
  }

  return parsed;
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

function parseOptionalNumber(value: string | undefined): number | undefined {
  if (value === undefined || value.trim().length === 0) {
    return undefined;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function normalizeUrl(value: string | undefined, fallback: string): string {
  if (!value) {
    return fallback;
  }

  return value.endsWith('/') ? value.slice(0, -1) : value;
}

function resolveIdTokenAudience(explicit: string | undefined, baseUrl: string): string | undefined {
  if (explicit && explicit.trim().length > 0) {
    return explicit.trim();
  }

  if (baseUrl.startsWith('https://') && baseUrl.includes('run.googleapis.com')) {
    return baseUrl;
  }

  return undefined;
}

export function getSearchServiceConfig(): SearchServiceConfig {
  if (cachedConfig) {
    return cachedConfig;
  }

  const base = getBaseConfig();

  const redis: RedisCacheConfig = {
    host: process.env.REDIS_HOST ?? base.redis.host,
    port: parseNumber(process.env.REDIS_PORT, base.redis.port),
    password: process.env.REDIS_PASSWORD ?? base.redis.password,
    tls: parseBoolean(process.env.REDIS_TLS, false),
    tlsRejectUnauthorized: parseBoolean(process.env.REDIS_TLS_REJECT_UNAUTHORIZED, true),
    caCert: process.env.REDIS_TLS_CA,
    keyPrefix: process.env.SEARCH_REDIS_PREFIX ?? 'hh:hybrid',
    ttlSeconds: parseNumber(
      process.env.SEARCH_CACHE_TTL_SECONDS,
      Number.isFinite(base.runtime.cacheTtlSeconds) ? base.runtime.cacheTtlSeconds : 180
    ),
    disable: parseBoolean(process.env.SEARCH_CACHE_PURGE, false)
  };

  const embedBaseUrl = normalizeUrl(process.env.EMBED_SERVICE_URL, 'http://localhost:8081');
  const embed: EmbedServiceConfig = {
    baseUrl: embedBaseUrl,
    timeoutMs: parseNumber(process.env.EMBED_SERVICE_TIMEOUT_MS, 15000), // Increased from 4000ms to handle cold starts
    authToken: process.env.EMBED_SERVICE_BEARER_TOKEN,
    idTokenAudience: resolveIdTokenAudience(process.env.EMBED_SERVICE_AUDIENCE, embedBaseUrl),
    retries: Math.max(0, parseNumber(process.env.EMBED_SERVICE_RETRIES, 2)),
    retryDelayMs: Math.max(0, parseNumber(process.env.EMBED_SERVICE_RETRY_DELAY_MS, 200)),
    circuitBreakerFailures: Math.max(1, parseNumber(process.env.EMBED_CB_FAILURES, 3)),
    circuitBreakerCooldownMs: Math.max(0, parseNumber(process.env.EMBED_CB_COOLDOWN_MS, 30_000)),
    healthTenantId: process.env.HEALTH_TENANT_ID ?? process.env.EMBED_HEALTH_TENANT_ID
  };

  const hnswEfSearch = parseOptionalNumber(process.env.PGVECTOR_HNSW_EF_SEARCH);

  const rerankBaseUrl = normalizeUrl(process.env.RERANK_SERVICE_URL, 'http://localhost:7103');
  const rerank: RerankServiceConfig = {
    baseUrl: rerankBaseUrl,
    timeoutMs: parseNumber(process.env.RERANK_SERVICE_TIMEOUT_MS, 15000), // Increased from 4000ms to handle cold starts
    retries: Math.max(0, parseNumber(process.env.RERANK_SERVICE_RETRIES, 2)),
    retryDelayMs: Math.max(0, parseNumber(process.env.RERANK_SERVICE_RETRY_DELAY_MS, 200)),
    idTokenAudience: resolveIdTokenAudience(process.env.RERANK_SERVICE_AUDIENCE, rerankBaseUrl),
    authToken: process.env.RERANK_SERVICE_BEARER_TOKEN,
    enabled: parseBoolean(process.env.ENABLE_RERANK, true)
  };

  const pgvector: PgVectorConfig = {
    host: process.env.PGVECTOR_HOST ?? '127.0.0.1',
    port: parseNumber(process.env.PGVECTOR_PORT, 5432),
    database: process.env.PGVECTOR_DATABASE ?? 'headhunter',
    user: process.env.PGVECTOR_USER ?? 'postgres',
    password: (process.env.PGVECTOR_PASSWORD ?? '').trim(),
    ssl: parseBoolean(process.env.PGVECTOR_SSL, false),
    schema: validateSchemaName(process.env.PGVECTOR_SCHEMA ?? 'search'),
    embeddingsTable: validateTableName(process.env.PGVECTOR_EMBEDDINGS_TABLE ?? 'candidate_embeddings', 'embeddings'),
    profilesTable: validateTableName(process.env.PGVECTOR_PROFILES_TABLE ?? 'candidate_profiles', 'profiles'),
    dimensions: Math.max(32, parseNumber(process.env.PGVECTOR_DIMENSIONS, 768)),
    poolMax: parseNumber(process.env.PGVECTOR_POOL_MAX, 10),
    poolMin: parseNumber(process.env.PGVECTOR_POOL_MIN, 0),
    idleTimeoutMs: parseNumber(process.env.PGVECTOR_IDLE_TIMEOUT_MS, 30_000),
    connectionTimeoutMs: parseNumber(process.env.PGVECTOR_CONNECTION_TIMEOUT_MS, 5_000),
    statementTimeoutMs: parseNumber(process.env.PGVECTOR_STATEMENT_TIMEOUT_MS, 30_000),
    hnswEfSearch,
    enableAutoMigrate: parseBoolean(process.env.ENABLE_AUTO_MIGRATE, false)
  };

  const search: SearchRuntimeConfig = {
    vectorWeight: parseNumber(process.env.SEARCH_HYBRID_VECTOR_WEIGHT, 0.65),
    textWeight: parseNumber(process.env.SEARCH_HYBRID_TEXT_WEIGHT, 0.35),
    minSimilarity: parseNumber(process.env.SEARCH_MIN_SIMILARITY, 0.25),
    maxResults: Math.max(1, parseNumber(process.env.SEARCH_MAX_RESULTS, 50)),
    ecoBoostFactor: parseNumber(process.env.SEARCH_ECO_BOOST_FACTOR, 1.2),
    confidenceFloor: parseNumber(process.env.SEARCH_CONFIDENCE_FLOOR, 0.2),
    warmupMultiplier: Math.max(1, parseNumber(process.env.SEARCH_WARMUP_MULTIPLIER, 3)),
    rerankCandidateLimit: Math.max(1, parseNumber(process.env.SEARCH_RERANK_CANDIDATE_LIMIT, 200)),
    rerankIncludeReasons: parseBoolean(process.env.SEARCH_RERANK_INCLUDE_REASONS, true),
    // RRF configuration
    rrfK: Math.max(1, parseNumber(process.env.SEARCH_RRF_K, 60)),
    perMethodLimit: Math.max(10, parseNumber(process.env.SEARCH_PER_METHOD_LIMIT, 100)),
    enableRrf: parseBoolean(process.env.SEARCH_ENABLE_RRF, true),
    // Pipeline stage limits (PIPE-01)
    pipelineRetrievalLimit: Math.max(100, parseNumber(process.env.PIPELINE_RETRIEVAL_LIMIT, 500)),
    pipelineScoringLimit: Math.max(50, parseNumber(process.env.PIPELINE_SCORING_LIMIT, 100)),
    pipelineRerankLimit: Math.max(10, parseNumber(process.env.PIPELINE_RERANK_LIMIT, 50)),
    pipelineLogStages: parseBoolean(process.env.PIPELINE_LOG_STAGES, true)
  };

  const firestoreFallback: FirestoreFallbackConfig = {
    enabled: parseBoolean(process.env.SEARCH_FIRESTORE_FALLBACK, false),
    concurrency: Math.max(1, parseNumber(process.env.SEARCH_FIRESTORE_CONCURRENCY, 8))
  };

  // Signal weight configuration for multi-signal scoring framework
  const signalWeights: SignalWeightEnvConfig = {
    defaultVectorWeight: parseNumber(process.env.SIGNAL_WEIGHT_VECTOR, 0.15),
    defaultLevelWeight: parseNumber(process.env.SIGNAL_WEIGHT_LEVEL, 0.15),
    defaultSpecialtyWeight: parseNumber(process.env.SIGNAL_WEIGHT_SPECIALTY, 0.15),
    defaultTechStackWeight: parseNumber(process.env.SIGNAL_WEIGHT_TECH_STACK, 0.15),
    defaultFunctionWeight: parseNumber(process.env.SIGNAL_WEIGHT_FUNCTION, 0.15),
    defaultTrajectoryWeight: parseNumber(process.env.SIGNAL_WEIGHT_TRAJECTORY, 0.10),
    defaultCompanyWeight: parseNumber(process.env.SIGNAL_WEIGHT_COMPANY, 0.15),
    geminiBlendWeight: parseNumber(process.env.GEMINI_BLEND_WEIGHT, 0.7)
  };

  cachedConfig = {
    base,
    embed,
    pgvector,
    redis,
    rerank,
    search,
    firestoreFallback,
    signalWeights
  };

  // Production security validation
  validateProductionSecurity(cachedConfig);

  return cachedConfig;
}

function validateProductionSecurity(config: SearchServiceConfig): void {
  const isProduction = process.env.NODE_ENV === 'production';

  if (isProduction) {
    const warnings: string[] = [];

    // PostgreSQL SSL check
    if (!config.pgvector.ssl) {
      warnings.push('PostgreSQL SSL is disabled. Set PGVECTOR_SSL=true for production.');
    }

    // Redis TLS check
    if (!config.redis.tls) {
      warnings.push('Redis TLS is disabled. Set REDIS_TLS=true for production.');
    }

    // Empty password check
    if (!config.pgvector.password) {
      warnings.push('PostgreSQL password is empty. Ensure PGVECTOR_PASSWORD is set.');
    }

    if (warnings.length > 0) {
      console.warn(
        '\n' +
        '⚠️  PRODUCTION SECURITY WARNINGS:\n' +
        warnings.map(w => `   - ${w}`).join('\n') +
        '\n'
      );
    }
  }
}

export function resetSearchServiceConfig(): void {
  cachedConfig = null;
}

/**
 * Returns signal weight defaults built from environment variables.
 * Used by signal-weights.ts as fallback defaults when no role-type preset is used.
 *
 * @returns SignalWeightConfig-compatible object with environment-configured weights
 */
export function getSignalWeightDefaults(): {
  vectorSimilarity: number;
  levelMatch: number;
  specialtyMatch: number;
  techStackMatch: number;
  functionMatch: number;
  trajectoryFit: number;
  companyPedigree: number;
} {
  const config = getSearchServiceConfig();
  return {
    vectorSimilarity: config.signalWeights.defaultVectorWeight,
    levelMatch: config.signalWeights.defaultLevelWeight,
    specialtyMatch: config.signalWeights.defaultSpecialtyWeight,
    techStackMatch: config.signalWeights.defaultTechStackWeight,
    functionMatch: config.signalWeights.defaultFunctionWeight,
    trajectoryFit: config.signalWeights.defaultTrajectoryWeight,
    companyPedigree: config.signalWeights.defaultCompanyWeight
  };
}
