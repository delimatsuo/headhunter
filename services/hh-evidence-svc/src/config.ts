import { getConfig as getBaseConfig, type ServiceConfig } from '@hh/common';

export interface EvidenceRedisConfig {
  host: string;
  port: number;
  password?: string;
  tls: boolean;
  keyPrefix: string;
  ttlSeconds: number;
  staleWhileRevalidateSeconds: number;
  disable: boolean;
}

export interface EvidenceFirestoreConfig {
  candidatesCollection: string;
  orgIdField: string;
  evidenceField: string;
  projections: string[];
}

export interface EvidenceRuntimeConfig {
  maxResponseKb: number;
  maxSections: number;
  allowedSections: string[];
  redactRestricted: boolean;
  defaultLocale: string;
}

export interface EvidenceServiceConfig {
  base: ServiceConfig;
  redis: EvidenceRedisConfig;
  firestore: EvidenceFirestoreConfig;
  runtime: EvidenceRuntimeConfig;
}

let cachedConfig: EvidenceServiceConfig | null = null;

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

function parseList(value: string | undefined, fallback: string[]): string[] {
  if (!value) {
    return fallback;
  }
  return value
    .split(',')
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
}

export function getEvidenceServiceConfig(): EvidenceServiceConfig {
  if (cachedConfig) {
    return cachedConfig;
  }

  const base = getBaseConfig();

  const redis: EvidenceRedisConfig = {
    host: process.env.EVIDENCE_REDIS_HOST ?? base.redis.host,
    port: parseNumber(process.env.EVIDENCE_REDIS_PORT, base.redis.port),
    password: process.env.EVIDENCE_REDIS_PASSWORD ?? base.redis.password,
    tls: parseBoolean(process.env.EVIDENCE_REDIS_TLS, false),
    keyPrefix: process.env.EVIDENCE_REDIS_PREFIX ?? 'hh:evidence',
    ttlSeconds: Math.max(30, parseNumber(process.env.EVIDENCE_CACHE_TTL_SECONDS, base.runtime.cacheTtlSeconds ?? 300)),
    staleWhileRevalidateSeconds: Math.max(
      0,
      parseNumber(process.env.EVIDENCE_CACHE_SWR_SECONDS, 120)
    ),
    disable: parseBoolean(process.env.EVIDENCE_CACHE_DISABLED, false)
  } satisfies EvidenceRedisConfig;

  const firestore: EvidenceFirestoreConfig = {
    candidatesCollection: process.env.EVIDENCE_CANDIDATES_COLLECTION ?? 'candidates',
    orgIdField: process.env.EVIDENCE_ORG_FIELD ?? 'org_id',
    evidenceField: process.env.EVIDENCE_FIELD ?? 'analysis',
    projections: parseList(
      process.env.EVIDENCE_FIRESTORE_PROJECTIONS,
      ['analysis', 'org_id', 'candidate_id', 'personal', 'metadata']
    )
  } satisfies EvidenceFirestoreConfig;

  const runtime: EvidenceRuntimeConfig = {
    maxResponseKb: Math.max(64, parseNumber(process.env.EVIDENCE_MAX_RESPONSE_KB, 256)),
    maxSections: Math.max(1, parseNumber(process.env.EVIDENCE_MAX_SECTIONS, 8)),
    allowedSections: parseList(
      process.env.EVIDENCE_ALLOWED_SECTIONS,
      [
        'skills_analysis',
        'experience_analysis',
        'education_analysis',
        'cultural_assessment',
        'achievements',
        'leadership_assessment',
        'compensation_analysis',
        'mobility_analysis'
      ]
    ),
    redactRestricted: parseBoolean(process.env.EVIDENCE_REDACT_RESTRICTED, true),
    defaultLocale: process.env.EVIDENCE_DEFAULT_LOCALE ?? 'pt-BR'
  } satisfies EvidenceRuntimeConfig;

  cachedConfig = { base, redis, firestore, runtime } satisfies EvidenceServiceConfig;

  return cachedConfig;
}

export function resetEvidenceServiceConfig(): void {
  cachedConfig = null;
}
