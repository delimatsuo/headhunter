import { getConfig as getBaseConfig, type ServiceConfig } from '@hh/common';

export interface RerankRedisConfig {
  host: string;
  port: number;
  password?: string;
  tls: boolean;
  keyPrefix: string;
  ttlSeconds: number;
  disable: boolean;
}

export interface TogetherAIConfig {
  apiKey: string | null;
  baseUrl: string;
  model: string;
  timeoutMs: number;
  retries: number;
  retryDelayMs: number;
  circuitBreakerThreshold: number;
  circuitBreakerCooldownMs: number;
  enable: boolean;
}

export interface RerankRuntimeConfig {
  slaTargetMs: number;
  slowLogMs: number;
  maxCandidates: number;
  minCandidates: number;
  defaultLimit: number;
  reasonLimit: number;
  maxPromptCharacters: number;
  maxHighlights: number;
  maxSkills: number;
  allowGracefulDegradation: boolean;
}

export interface RerankServiceConfig {
  base: ServiceConfig;
  redis: RerankRedisConfig;
  together: TogetherAIConfig;
  runtime: RerankRuntimeConfig;
}

let cachedConfig: RerankServiceConfig | null = null;

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
  if (['true', '1', 'yes', 'on'].includes(normalized)) {
    return true;
  }
  if (['false', '0', 'no', 'off'].includes(normalized)) {
    return false;
  }
  return defaultValue;
}

function clamp(value: number, options: { min?: number; max?: number }): number {
  const { min, max } = options;
  let result = value;
  if (typeof min === 'number') {
    result = Math.max(min, result);
  }
  if (typeof max === 'number') {
    result = Math.min(max, result);
  }
  return result;
}

function normalizeUrl(value: string | undefined, fallback: string): string {
  if (!value) {
    return fallback;
  }
  return value.endsWith('/') ? value.slice(0, -1) : value;
}

export function getRerankServiceConfig(): RerankServiceConfig {
  if (cachedConfig) {
    return cachedConfig;
  }

  const base = getBaseConfig();

  const redis: RerankRedisConfig = {
    host: process.env.REDIS_HOST ?? base.redis.host,
    port: parseNumber(process.env.REDIS_PORT, base.redis.port),
    password: process.env.REDIS_PASSWORD ?? base.redis.password,
    tls: parseBoolean(process.env.REDIS_TLS, false),
    keyPrefix: process.env.RERANK_REDIS_PREFIX ?? 'hh:rerank',
    ttlSeconds: parseNumber(
      process.env.RERANK_CACHE_TTL_SECONDS,
      Number.isFinite(base.runtime.cacheTtlSeconds) ? base.runtime.cacheTtlSeconds : 300
    ),
    disable: parseBoolean(process.env.RERANK_CACHE_DISABLE, false)
  };

  const together: TogetherAIConfig = {
    apiKey: process.env.TOGETHER_API_KEY ?? null,
    baseUrl: normalizeUrl(process.env.TOGETHER_API_BASE_URL, 'https://api.together.xyz/v1'),
    model: process.env.TOGETHER_MODEL ?? 'qwen2.5-32b-instruct',
    timeoutMs: clamp(parseNumber(process.env.TOGETHER_TIMEOUT_MS, 320), { min: 150, max: 1000 }),
    retries: clamp(parseNumber(process.env.TOGETHER_RERANK_RETRIES, 2), { min: 0, max: 5 }),
    retryDelayMs: clamp(parseNumber(process.env.TOGETHER_RERANK_RETRY_DELAY_MS, 50), { min: 0, max: 1000 }),
    circuitBreakerThreshold: clamp(parseNumber(process.env.TOGETHER_CB_FAILURES, 4), { min: 1, max: 20 }),
    circuitBreakerCooldownMs: clamp(parseNumber(process.env.TOGETHER_CB_COOLDOWN_MS, 60_000), {
      min: 5_000,
      max: 600_000
    }),
    enable: parseBoolean(process.env.TOGETHER_ENABLE, true)
  };

  if (together.enable && !together.apiKey) {
    throw new Error('TOGETHER_API_KEY is required when Together AI integration is enabled.');
  }

  const runtime: RerankRuntimeConfig = {
    slaTargetMs: clamp(parseNumber(process.env.RERANK_SLA_TARGET_MS, 350), { min: 100, max: 1000 }),
    slowLogMs: clamp(parseNumber(process.env.RERANK_SLOW_LOG_MS, 300), { min: 50, max: 2000 }),
    maxCandidates: clamp(parseNumber(process.env.RERANK_MAX_CANDIDATES, 50), { min: 1, max: 200 }),
    minCandidates: clamp(parseNumber(process.env.RERANK_MIN_CANDIDATES, 1), { min: 1, max: 50 }),
    defaultLimit: clamp(parseNumber(process.env.RERANK_DEFAULT_LIMIT, 20), { min: 1, max: 200 }),
    reasonLimit: clamp(parseNumber(process.env.RERANK_REASON_LIMIT, 3), { min: 1, max: 10 }),
    maxPromptCharacters: clamp(parseNumber(process.env.RERANK_MAX_PROMPT_CHARACTERS, 16_000), {
      min: 2_000,
      max: 32_000
    }),
    maxHighlights: clamp(parseNumber(process.env.RERANK_MAX_HIGHLIGHTS, 5), { min: 1, max: 20 }),
    maxSkills: clamp(parseNumber(process.env.RERANK_MAX_SKILLS, 8), { min: 1, max: 30 }),
    allowGracefulDegradation: parseBoolean(process.env.RERANK_ENABLE_FALLBACK, true)
  };

  cachedConfig = {
    base,
    redis,
    together,
    runtime
  };

  return cachedConfig;
}

export function resetRerankServiceConfig(): void {
  cachedConfig = null;
}
