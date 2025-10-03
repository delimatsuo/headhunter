import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { getConfig as getBaseConfig, type ServiceConfig } from '@hh/common';

export interface EnrichmentQueueConfig {
  queueKey: string;
  resultKeyPrefix: string;
  dedupeKeyPrefix: string;
  maxConcurrency: number;
  jobTtlSeconds: number;
  dedupeTtlSeconds: number;
  pythonExecutable: string;
  pythonScript: string;
  jobTimeoutMs: number;
  pollIntervalMs: number;
  retryLimit: number;
  retryBaseDelayMs: number;
  retryMaxDelayMs: number;
  circuitBreakerFailures: number;
  circuitBreakerCooldownMs: number;
}

export interface EmbedServiceConfig {
  enabled: boolean;
  baseUrl: string;
  timeoutMs: number;
  authToken?: string;
  idTokenAudience?: string;
  tenantHeader: string;
  retryLimit: number;
  retryBaseDelayMs: number;
  retryMaxDelayMs: number;
  circuitBreakerFailures: number;
  circuitBreakerResetMs: number;
}

export interface ModelVersioningConfig {
  modelVersion: string;
  promptVersion: string;
}

export interface EnrichServiceConfig {
  base: ServiceConfig;
  queue: EnrichmentQueueConfig;
  embed: EmbedServiceConfig;
  versioning: ModelVersioningConfig;
}

let cachedConfig: EnrichServiceConfig | null = null;

function resolvePythonScript(): string {
  const override = process.env.ENRICH_PYTHON_SCRIPT;
  if (override) {
    return resolve(override);
  }

  const defaultPath = resolve(process.cwd(), '../../scripts/run_enrich_job.py');
  if (existsSync(defaultPath)) {
    return defaultPath;
  }

  // Fallback to repo root when running from ts-node
  return resolve(process.cwd(), './scripts/run_enrich_job.py');
}

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

function resolveIdTokenAudience(explicit: string | undefined, baseUrl: string): string | undefined {
  if (explicit && explicit.trim().length > 0) {
    return explicit.trim();
  }

  if (baseUrl.startsWith('https://') && baseUrl.includes('run.googleapis.com')) {
    return baseUrl.replace(/\/$/, '');
  }

  return undefined;
}

export function getEnrichServiceConfig(): EnrichServiceConfig {
  if (cachedConfig) {
    return cachedConfig;
  }

  const base = getBaseConfig();

  const queue: EnrichmentQueueConfig = {
    queueKey: process.env.ENRICH_QUEUE_KEY ?? 'hh:enrich:queue',
    resultKeyPrefix: process.env.ENRICH_RESULT_PREFIX ?? 'hh:enrich:job:',
    dedupeKeyPrefix: process.env.ENRICH_DEDUPE_PREFIX ?? 'hh:enrich:dedupe:',
    maxConcurrency: Math.max(1, parseNumber(process.env.ENRICH_CONCURRENCY, 2)),
    jobTtlSeconds: Math.max(60, parseNumber(process.env.ENRICH_JOB_TTL_SECONDS, 86400)),
    dedupeTtlSeconds: Math.max(60, parseNumber(process.env.ENRICH_DEDUPE_TTL_SECONDS, 21600)),
    pythonExecutable: process.env.ENRICH_PYTHON_BIN ?? 'python3',
    pythonScript: resolvePythonScript(),
    jobTimeoutMs: Math.max(10_000, parseNumber(process.env.ENRICH_JOB_TIMEOUT_MS, 180_000)),
    pollIntervalMs: Math.max(250, parseNumber(process.env.ENRICH_POLL_INTERVAL_MS, 1000)),
    retryLimit: Math.max(0, parseNumber(process.env.ENRICH_JOB_RETRY_LIMIT, 2)),
    retryBaseDelayMs: Math.max(100, parseNumber(process.env.ENRICH_JOB_RETRY_BASE_DELAY_MS, 500)),
    retryMaxDelayMs: Math.max(1000, parseNumber(process.env.ENRICH_JOB_RETRY_MAX_DELAY_MS, 5000)),
    circuitBreakerFailures: Math.max(1, parseNumber(process.env.ENRICH_JOB_CIRCUIT_FAILURES, 5)),
    circuitBreakerCooldownMs: Math.max(5000, parseNumber(process.env.ENRICH_JOB_CIRCUIT_COOLDOWN_MS, 120_000))
  } satisfies EnrichmentQueueConfig;

  const embedBaseUrl = (process.env.ENRICH_EMBED_BASE_URL ?? process.env.EMBED_SERVICE_URL ?? 'http://localhost:7101').replace(/\/$/, '');
  const embed: EmbedServiceConfig = {
    enabled: parseBoolean(process.env.ENRICH_EMBED_ENABLED, true),
    baseUrl: embedBaseUrl,
    timeoutMs: Math.max(500, parseNumber(process.env.ENRICH_EMBED_TIMEOUT_MS, 5000)),
    authToken: process.env.ENRICH_EMBED_TOKEN ?? process.env.EMBED_SERVICE_BEARER_TOKEN,
    idTokenAudience: resolveIdTokenAudience(process.env.ENRICH_EMBED_AUDIENCE ?? process.env.EMBED_SERVICE_AUDIENCE, embedBaseUrl),
    tenantHeader: process.env.ENRICH_TENANT_HEADER ?? 'X-Tenant-ID',
    retryLimit: Math.max(0, parseNumber(process.env.ENRICH_EMBED_RETRY_LIMIT, 2)),
    retryBaseDelayMs: Math.max(100, parseNumber(process.env.ENRICH_EMBED_RETRY_BASE_DELAY_MS, 400)),
    retryMaxDelayMs: Math.max(1000, parseNumber(process.env.ENRICH_EMBED_RETRY_MAX_DELAY_MS, 4000)),
    circuitBreakerFailures: Math.max(1, parseNumber(process.env.ENRICH_EMBED_CB_FAILURE_THRESHOLD, 4)),
    circuitBreakerResetMs: Math.max(5000, parseNumber(process.env.ENRICH_EMBED_CB_RESET_MS, 120_000))
  } satisfies EmbedServiceConfig;

  const versioning: ModelVersioningConfig = {
    modelVersion: process.env.ENRICH_MODEL_VERSION ?? 'qwen-2.5-32b-stage1',
    promptVersion: process.env.ENRICH_PROMPT_VERSION ?? 'stage1-v1'
  } satisfies ModelVersioningConfig;

  cachedConfig = {
    base,
    queue,
    embed,
    versioning
  } satisfies EnrichServiceConfig;

  return cachedConfig;
}

export function resetEnrichConfigForTesting(): void {
  cachedConfig = null;
}
