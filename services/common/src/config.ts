import { existsSync } from 'fs';
import { join } from 'path';

export interface FirestoreConfig {
  projectId: string;
  emulatorHost?: string;
}

export interface RedisConfig {
  host: string;
  port: number;
  password?: string;
}

export interface RuntimeConfig {
  serviceName: string;
  logLevel: string;
  enableRequestLogging: boolean;
  cacheTtlSeconds: number;
}

export interface TokenIssuerConfig {
  issuer: string;
  jwksUri: string;
}

export interface AuthConfig {
  serviceAccountPath?: string;
  checkRevoked: boolean;
  allowedIssuers: string[];
  issuerConfigs: TokenIssuerConfig[];
  gatewayAudiences: string[];
  gatewayProjectId?: string;
  enableGatewayTokens: boolean;
  tokenClockSkewSeconds: number;
  tokenCacheTtlSeconds: number;
  mode: 'firebase' | 'gateway' | 'hybrid';
  tokenCacheEnabled: boolean;
}

export interface RateLimitConfig {
  hybridRps: number;
  rerankRps: number;
  globalRps: number;
  tenantBurst: number;
}

export interface MonitoringConfig {
  traceHeader: string;
  propagateTrace: boolean;
  requestIdHeader: string;
  logClientMetadata: boolean;
  traceProjectId?: string;
}

export interface ServiceConfig {
  firestore: FirestoreConfig;
  redis: RedisConfig;
  auth: AuthConfig;
  runtime: RuntimeConfig;
  rateLimits: RateLimitConfig;
  monitoring: MonitoringConfig;
}

let cachedConfig: ServiceConfig | null = null;

const DEFAULTS = {
  logLevel: process.env.LOG_LEVEL ?? 'info',
  cacheTtlSeconds: Number(process.env.COMMON_CACHE_TTL ?? 300),
  serviceName: process.env.SERVICE_NAME ?? 'hh-service',
  redisHost: process.env.REDIS_HOST ?? 'localhost',
  redisPort: Number(process.env.REDIS_PORT ?? 6379),
  traceHeader: process.env.TRACE_HEADER ?? 'X-Cloud-Trace-Context',
  requestIdHeader: process.env.REQUEST_ID_HEADER ?? 'X-Request-ID'
};

function resolveAuthMode(): 'firebase' | 'gateway' | 'hybrid' {
  const value = process.env.AUTH_MODE?.trim().toLowerCase();
  if (!value) {
    return 'hybrid';
  }

  if (value === 'firebase' || value === 'gateway' || value === 'hybrid') {
    return value;
  }

  return 'hybrid';
}

function loadServiceAccountPath(): string | undefined {
  const explicitPath = process.env.GOOGLE_APPLICATION_CREDENTIALS;
  if (explicitPath) {
    return explicitPath;
  }

  const localPath = join(process.cwd(), 'service-account.json');
  if (existsSync(localPath)) {
    return localPath;
  }

  return undefined;
}

const PROJECT_ID_ENV_KEYS = ['FIREBASE_PROJECT_ID', 'GOOGLE_CLOUD_PROJECT', 'GCLOUD_PROJECT'] as const;

function shouldCheckRevoked(): boolean {
  const value = process.env.AUTH_CHECK_REVOKED;
  if (value === undefined) {
    return true;
  }

  const normalized = value.trim().toLowerCase();
  return !['false', '0', 'no'].includes(normalized);
}

function resolveProjectId(): string {
  for (const key of PROJECT_ID_ENV_KEYS) {
    const value = process.env[key];
    if (value && value.trim().length > 0) {
      return value;
    }
  }

  throw new Error(`Missing project identifier. Provide one of: ${PROJECT_ID_ENV_KEYS.join(', ')}`);
}

function resolveEmulatorHost(): string | undefined {
  return process.env.FIRESTORE_EMULATOR_HOST ?? process.env.FIREBASE_EMULATOR_HOST ?? undefined;
}

function normalizeIssuer(value: string): string {
  const trimmed = value.trim();
  if (trimmed.endsWith('/')) {
    return trimmed;
  }
  return `${trimmed}/`;
}

function parseIssuerConfigs(raw: string | undefined): TokenIssuerConfig[] {
  if (!raw) {
    return [];
  }

  const entries = raw
    .split(',')
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0);

  const configs = new Map<string, TokenIssuerConfig>();

  for (const entry of entries) {
    const [issuerPart, jwksPart] = entry.split('|').map((segment) => segment.trim());
    if (!issuerPart) {
      continue;
    }

    const issuer = normalizeIssuer(issuerPart);
    const jwksUri = jwksPart && jwksPart.length > 0 ? jwksPart : `${issuer}.well-known/jwks.json`;
    configs.set(issuer, {
      issuer,
      jwksUri
    });
  }

  return Array.from(configs.values());
}

function buildAllowedIssuers(projectId: string, issuerConfigs: TokenIssuerConfig[], includeFirebaseIssuer: boolean): string[] {
  const issuers = new Set<string>();

  if (includeFirebaseIssuer) {
    issuers.add(`https://securetoken.google.com/${projectId}`);
  }

  for (const config of issuerConfigs) {
    issuers.add(config.issuer);
  }

  return Array.from(issuers);
}

function parseGatewayAudiences(): string[] {
  const raw = process.env.GATEWAY_AUDIENCE;
  if (!raw) {
    return [];
  }

  const values = raw
    .split(',')
    .map((value) => value.trim())
    .filter((value) => value.length > 0);

  return Array.from(new Set(values));
}

function parseBoolean(value: string | undefined, defaultValue: boolean): boolean {
  if (value === undefined) {
    return defaultValue;
  }

  const normalized = value.trim().toLowerCase();
  if (['true', '1', 'yes', 'y'].includes(normalized)) {
    return true;
  }

  if (['false', '0', 'no', 'n'].includes(normalized)) {
    return false;
  }

  return defaultValue;
}

function parseNumber(value: string | undefined, defaultValue: number): number {
  if (!value) {
    return defaultValue;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : defaultValue;
}

function validateConfig(config: ServiceConfig): void {
  const { auth, monitoring } = config;

  if ((auth.mode === 'gateway' || auth.mode === 'hybrid') && !auth.enableGatewayTokens) {
    throw new Error('Gateway authentication mode requires ENABLE_GATEWAY_TOKENS to be true.');
  }

  if (auth.enableGatewayTokens) {
    if (!auth.issuerConfigs || auth.issuerConfigs.length === 0) {
      throw new Error('ALLOWED_TOKEN_ISSUERS must specify at least one issuer when gateway tokens are enabled.');
    }

    if (!auth.gatewayAudiences || auth.gatewayAudiences.length === 0) {
      throw new Error('GATEWAY_AUDIENCE must include at least one audience when gateway tokens are enabled.');
    }
  }

  if (monitoring.propagateTrace && !monitoring.traceHeader) {
    throw new Error('TRACE_HEADER must be provided when propagate trace context is enabled.');
  }
}

export function loadConfig(): ServiceConfig {
  if (cachedConfig) {
    return cachedConfig;
  }

  const projectId = resolveProjectId();
  const firestoreEmulator = resolveEmulatorHost();
  const gatewayProjectId = process.env.GATEWAY_PROJECT_ID?.trim() || undefined;
  const authMode = resolveAuthMode();
  const gatewayTokensRequested = parseBoolean(process.env.ENABLE_GATEWAY_TOKENS, authMode !== 'firebase');
  const enableGatewayTokens = authMode === 'firebase' ? false : gatewayTokensRequested;
  const tokenClockSkewSeconds = parseNumber(process.env.TOKEN_CLOCK_SKEW_SECONDS, 30);
  const tokenCacheTtlSeconds = parseNumber(process.env.TOKEN_CACHE_TTL_SECONDS, 300);
  const tokenCacheEnabled = parseBoolean(process.env.ENABLE_TOKEN_CACHE, true);
  const issuerConfigs = parseIssuerConfigs(process.env.ISSUER_CONFIGS || process.env.ALLOWED_TOKEN_ISSUERS);
  const allowedIssuers = buildAllowedIssuers(projectId, issuerConfigs, authMode !== 'gateway');
  const gatewayAudiences = parseGatewayAudiences();
  const hybridRps = parseNumber(process.env.GATEWAY_HYBRID_RPS, 30);
  const rerankRps = parseNumber(process.env.GATEWAY_RERANK_RPS, 10);
  const globalRps = parseNumber(process.env.GATEWAY_GLOBAL_RPS, 50);
  const tenantBurst = parseNumber(process.env.GATEWAY_TENANT_BURST, 10);
  const propagateTrace = parseBoolean(process.env.PROPAGATE_TRACE_CONTEXT, true);
  const logClientMetadata = parseBoolean(process.env.LOG_GATEWAY_METADATA, true);
  const traceProjectId = process.env.TRACE_PROJECT_ID?.trim() || gatewayProjectId || projectId;

  if (!process.env.FIREBASE_PROJECT_ID) {
    process.env.FIREBASE_PROJECT_ID = projectId;
  }

  cachedConfig = {
    firestore: {
      projectId,
      emulatorHost: firestoreEmulator
    },
    redis: {
      host: DEFAULTS.redisHost,
      port: DEFAULTS.redisPort,
      password: process.env.REDIS_PASSWORD
    },
    auth: {
      serviceAccountPath: loadServiceAccountPath(),
      checkRevoked: shouldCheckRevoked(),
      allowedIssuers,
      issuerConfigs,
      gatewayAudiences,
      gatewayProjectId,
      enableGatewayTokens,
      tokenClockSkewSeconds,
      tokenCacheTtlSeconds,
      mode: authMode,
      tokenCacheEnabled
    },
    runtime: {
      serviceName: DEFAULTS.serviceName,
      logLevel: DEFAULTS.logLevel,
      enableRequestLogging: process.env.ENABLE_REQUEST_LOGGING !== 'false',
      cacheTtlSeconds: DEFAULTS.cacheTtlSeconds
    },
    rateLimits: {
      hybridRps,
      rerankRps,
      globalRps,
      tenantBurst
    },
    monitoring: {
      traceHeader: DEFAULTS.traceHeader,
      propagateTrace,
      requestIdHeader: DEFAULTS.requestIdHeader,
      logClientMetadata,
      traceProjectId
    }
  };

  validateConfig(cachedConfig);

  return cachedConfig;
}

export function getConfig(): ServiceConfig {
  return cachedConfig ?? loadConfig();
}

export function resetConfigForTesting(): void {
  cachedConfig = null;
}
