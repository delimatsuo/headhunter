import { getConfig as getBaseConfig, type ServiceConfig } from '@hh/common';

export interface MsgsRedisConfig {
  url: string;
  tls: boolean;
  keyPrefix: string;
  skillTtlSeconds: number;
  roleTtlSeconds: number;
  demandTtlSeconds: number;
  disable: boolean;
}

export interface MsgsDatabaseConfig {
  host: string;
  port: number;
  user: string;
  password: string;
  database: string;
  ssl: boolean;
  connectTimeoutMs: number;
  idleTimeoutMs: number;
  maxPoolSize: number;
  minPoolSize: number;
}

export interface MsgsCalculationConfig {
  pmiMinScore: number;
  pmiDecayDays: number;
  pmiMinSupport: number;
  emaSpan: number;
  emaMinPoints: number;
  emaZScoreWindow: number;
}

export interface MsgsRuntimeConfig {
  useSeedData: boolean;
  templateDefaultLocale: string;
  templateVersion: string;
}

export interface MsgsServiceConfig {
  base: ServiceConfig;
  redis: MsgsRedisConfig;
  database: MsgsDatabaseConfig;
  calculations: MsgsCalculationConfig;
  runtime: MsgsRuntimeConfig;
}

let cachedConfig: MsgsServiceConfig | null = null;

function parseBoolean(value: string | undefined, fallback: boolean): boolean {
  if (value === undefined) {
    return fallback;
  }

  const normalized = value.trim().toLowerCase();
  if (['true', '1', 'yes', 'y', 'on'].includes(normalized)) {
    return true;
  }
  if (['false', '0', 'no', 'n', 'off'].includes(normalized)) {
    return false;
  }
  return fallback;
}

function parseNumber(value: string | undefined, fallback: number, min?: number): number {
  if (value === undefined) {
    return min !== undefined ? Math.max(min, fallback) : fallback;
  }

  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return min !== undefined ? Math.max(min, fallback) : fallback;
  }

  const withMin = min !== undefined ? Math.max(min, parsed) : parsed;
  return withMin;
}

export function getMsgsServiceConfig(): MsgsServiceConfig {
  if (cachedConfig) {
    return cachedConfig;
  }

  const base = getBaseConfig();

  const redis: MsgsRedisConfig = {
    url: process.env.MSGS_REDIS_URL ?? `redis://${base.redis.host}:${base.redis.port}`,
    tls: parseBoolean(process.env.MSGS_REDIS_TLS, false),
    keyPrefix: process.env.MSGS_REDIS_KEY_PREFIX ?? 'hh:msgs',
    skillTtlSeconds: parseNumber(process.env.MSGS_CACHE_TTL_SKILLS, 3600, 60),
    roleTtlSeconds: parseNumber(process.env.MSGS_CACHE_TTL_ROLES, 7200, 60),
    demandTtlSeconds: parseNumber(process.env.MSGS_CACHE_TTL_DEMAND, 900, 30),
    disable: parseBoolean(process.env.MSGS_CACHE_DISABLED, false)
  } satisfies MsgsRedisConfig;

  const database: MsgsDatabaseConfig = {
    host: process.env.MSGS_DB_HOST ?? '127.0.0.1',
    port: parseNumber(process.env.MSGS_DB_PORT, 5432),
    user: process.env.MSGS_DB_USER ?? 'msgs_service',
    password: process.env.MSGS_DB_PASS ?? '',
    database: process.env.MSGS_DB_NAME ?? 'headhunter',
    ssl: parseBoolean(process.env.MSGS_DB_SSL, false),
    connectTimeoutMs: parseNumber(process.env.MSGS_DB_CONNECT_TIMEOUT_MS, 5000, 1000),
    idleTimeoutMs: parseNumber(process.env.MSGS_DB_IDLE_TIMEOUT_MS, 10000, 1000),
    maxPoolSize: parseNumber(process.env.MSGS_DB_POOL_MAX, 10, 1),
    minPoolSize: parseNumber(process.env.MSGS_DB_POOL_MIN, 2, 0)
  } satisfies MsgsDatabaseConfig;

  const calculations: MsgsCalculationConfig = {
    pmiMinScore: parseNumber(process.env.MSGS_PMI_MIN_SCORE, 0.1),
    pmiDecayDays: parseNumber(process.env.MSGS_PMI_DECAY_DAYS, 30, 1),
    pmiMinSupport: parseNumber(process.env.MSGS_PMI_MIN_SUPPORT, 5, 1),
    emaSpan: parseNumber(process.env.MSGS_EMA_SPAN, 6, 2),
    emaMinPoints: parseNumber(process.env.MSGS_EMA_MIN_POINTS, 4, 2),
    emaZScoreWindow: parseNumber(process.env.MSGS_EMA_ZSCORE_WINDOW, 12, 4)
  } satisfies MsgsCalculationConfig;

  const runtime: MsgsRuntimeConfig = {
    useSeedData: parseBoolean(process.env.MSGS_USE_SEED_DATA, true),
    templateDefaultLocale: process.env.MSGS_TEMPLATE_DEFAULT_LOCALE ?? 'pt-BR',
    templateVersion: process.env.MSGS_TEMPLATE_VERSION ?? '2024.1'
  } satisfies MsgsRuntimeConfig;

  cachedConfig = {
    base,
    redis,
    database,
    calculations,
    runtime
  } satisfies MsgsServiceConfig;

  return cachedConfig;
}

export function resetMsgsConfig(): void {
  cachedConfig = null;
}
