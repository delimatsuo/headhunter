import { getConfig as getBaseConfig, type ServiceConfig } from '@hh/common';

export interface EcoRedisConfig {
  host: string;
  port: number;
  password?: string;
  tls: boolean;
  tlsRejectUnauthorized: boolean;
  caCert?: string;
  searchKeyPrefix: string;
  occupationKeyPrefix: string;
  searchTtlSeconds: number;
  occupationTtlSeconds: number;
  disable: boolean;
}

export interface EcoFirestoreConfig {
  occupationCollection: string;
  aliasCollection: string;
  templateCollection: string;
  crosswalkCollection: string;
  orgIdField: string;
  localeField: string;
}

export interface EcoSearchRuntimeConfig {
  limit: number;
  fuzzyThreshold: number;
  aliasBoost: number;
  minScore: number;
  normalizeAccents: boolean;
  defaultLocale: string;
  defaultCountry: string;
}

export interface EcoServiceConfig {
  base: ServiceConfig;
  redis: EcoRedisConfig;
  firestore: EcoFirestoreConfig;
  search: EcoSearchRuntimeConfig;
}

let cachedConfig: EcoServiceConfig | null = null;

function parseNumber(value: string | undefined, fallback: number): number {
  if (value === undefined) {
    return fallback;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

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

export function getEcoServiceConfig(): EcoServiceConfig {
  if (cachedConfig) {
    return cachedConfig;
  }

  const base = getBaseConfig();

  const redis: EcoRedisConfig = {
    host: process.env.ECO_REDIS_HOST ?? base.redis.host,
    port: parseNumber(process.env.ECO_REDIS_PORT, base.redis.port),
    password: process.env.ECO_REDIS_PASSWORD ?? base.redis.password,
    tls: parseBoolean(process.env.ECO_REDIS_TLS ?? process.env.REDIS_TLS, false),
    tlsRejectUnauthorized: parseBoolean(process.env.ECO_REDIS_TLS_REJECT_UNAUTHORIZED ?? process.env.REDIS_TLS_REJECT_UNAUTHORIZED, true),
    caCert: process.env.ECO_REDIS_TLS_CA ?? process.env.REDIS_TLS_CA,
    searchKeyPrefix: process.env.ECO_REDIS_SEARCH_PREFIX ?? 'hh:eco:search',
    occupationKeyPrefix: process.env.ECO_REDIS_OCC_PREFIX ?? 'hh:eco:occupation',
    searchTtlSeconds: Math.max(30, parseNumber(process.env.ECO_SEARCH_TTL_SECONDS, 120)),
    occupationTtlSeconds: Math.max(60, parseNumber(process.env.ECO_OCCUPATION_TTL_SECONDS, 3600)),
    disable: parseBoolean(process.env.ECO_CACHE_DISABLED, false)
  } satisfies EcoRedisConfig;

  const firestore: EcoFirestoreConfig = {
    occupationCollection: process.env.ECO_OCCUPATION_COLLECTION ?? 'eco_occupation',
    aliasCollection: process.env.ECO_ALIAS_COLLECTION ?? 'eco_alias',
    templateCollection: process.env.ECO_TEMPLATE_COLLECTION ?? 'eco_template',
    crosswalkCollection: process.env.ECO_CROSSWALK_COLLECTION ?? 'occupation_crosswalk',
    orgIdField: process.env.ECO_ORG_FIELD ?? 'org_id',
    localeField: process.env.ECO_LOCALE_FIELD ?? 'locale'
  } satisfies EcoFirestoreConfig;

  const search: EcoSearchRuntimeConfig = {
    limit: Math.max(1, Math.min(50, parseNumber(process.env.ECO_SEARCH_LIMIT, 10))),
    fuzzyThreshold: Math.min(1, Math.max(0.2, parseNumber(process.env.ECO_SEARCH_THRESHOLD, 0.45))),
    aliasBoost: Math.max(0.1, parseNumber(process.env.ECO_ALIAS_BOOST, 1.15)),
    minScore: Math.max(0, parseNumber(process.env.ECO_MIN_SCORE, 0.35)),
    normalizeAccents: parseBoolean(process.env.ECO_NORMALIZE_ACCENTS, true),
    defaultLocale: process.env.ECO_DEFAULT_LOCALE ?? 'pt-BR',
    defaultCountry: process.env.ECO_DEFAULT_COUNTRY ?? 'BR'
  } satisfies EcoSearchRuntimeConfig;

  cachedConfig = { base, redis, firestore, search } satisfies EcoServiceConfig;
  return cachedConfig;
}

export function resetEcoConfig(): void {
  cachedConfig = null;
}
