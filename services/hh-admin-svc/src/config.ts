import { getConfig as getBaseConfig, type ServiceConfig } from '@hh/common';

export interface AdminPubSubConfig {
  postingsTopic: string;
  profilesTopic: string;
  orderingEnabled: boolean;
  orderingKeyTemplate?: string;
  timeoutMs: number;
  retryLimit: number;
  healthCheckEnabled: boolean;
}

export interface AdminJobsConfig {
  postingsJob: string;
  profilesJob: string;
  executionTimeoutSeconds: number;
  pollIntervalMs: number;
  retryLimit: number;
  healthCheckEnabled: boolean;
}

export interface AdminSchedulerConfig {
  projectId: string;
  location: string;
  serviceAccountEmail: string;
  targetBaseUrl?: string;
}

export interface AdminMonitoringConfig {
  enabled: boolean;
  projectId: string;
  sqlInstance?: string;
  sqlDatabase?: string;
  sqlTable?: string;
  firestoreCollection?: string;
  alertThresholdDays: number;
  maxLookbackDays: number;
  optionalForHealth: boolean;
}

export interface AdminIamConfig {
  globalRole: string;
  refreshRole: string;
  monitorRole: string;
  auditLogMetric: string;
}

export interface AdminRefreshDefaults {
  timeoutSeconds: number;
  defaultPriority: string;
  allowForce: boolean;
}

export interface AdminServiceConfig {
  base: ServiceConfig;
  pubsub: AdminPubSubConfig;
  jobs: AdminJobsConfig;
  scheduler: AdminSchedulerConfig;
  monitoring: AdminMonitoringConfig;
  iam: AdminIamConfig;
  refresh: AdminRefreshDefaults;
}

let cachedConfig: AdminServiceConfig | null = null;

function parseNumber(value: string | undefined, fallback: number, min?: number): number {
  if (value === undefined) {
    return fallback;
  }

  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }

  if (min !== undefined && parsed < min) {
    return min;
  }

  return parsed;
}

function parseBoolean(value: string | undefined, fallback: boolean): boolean {
  if (value === undefined) {
    return fallback;
  }

  const normalized = value.trim().toLowerCase();
  if (['true', '1', 'yes', 'on', 'y'].includes(normalized)) {
    return true;
  }

  if (['false', '0', 'no', 'off', 'n'].includes(normalized)) {
    return false;
  }

  return fallback;
}

function requireEnv(name: string, fallback?: string): string {
  const value = process.env[name] ?? fallback;
  if (!value || value.trim().length === 0) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export function getAdminServiceConfig(): AdminServiceConfig {
  if (cachedConfig) {
    return cachedConfig;
  }

  const base = getBaseConfig();

  const pubsub: AdminPubSubConfig = {
    postingsTopic: requireEnv('ADMIN_POSTINGS_TOPIC'),
    profilesTopic: requireEnv('ADMIN_PROFILES_TOPIC'),
    orderingEnabled: parseBoolean(process.env.ADMIN_PUBSUB_ORDERING_ENABLED, false),
    orderingKeyTemplate: process.env.ADMIN_PUBSUB_ORDERING_KEY_TEMPLATE,
    timeoutMs: parseNumber(process.env.ADMIN_PUBSUB_TIMEOUT_MS, 5000, 1000),
    retryLimit: parseNumber(process.env.ADMIN_PUBSUB_RETRY_LIMIT, 5, 0),
    healthCheckEnabled: parseBoolean(process.env.ADMIN_PUBSUB_HEALTH_ENABLED, true)
  } satisfies AdminPubSubConfig;

  const jobs: AdminJobsConfig = {
    postingsJob: requireEnv('ADMIN_POSTINGS_JOB'),
    profilesJob: requireEnv('ADMIN_PROFILES_JOB'),
    executionTimeoutSeconds: parseNumber(process.env.ADMIN_JOBS_EXECUTION_TIMEOUT_SECONDS, 1800, 60),
    pollIntervalMs: parseNumber(process.env.ADMIN_JOBS_POLL_INTERVAL_MS, 5000, 500),
    retryLimit: parseNumber(process.env.ADMIN_JOBS_RETRY_LIMIT, 3, 0),
    healthCheckEnabled: parseBoolean(process.env.ADMIN_JOBS_HEALTH_ENABLED, true)
  } satisfies AdminJobsConfig;

  const scheduler: AdminSchedulerConfig = {
    projectId: requireEnv('ADMIN_SCHEDULER_PROJECT', base.firestore.projectId),
    location: requireEnv('ADMIN_SCHEDULER_LOCATION', 'us-central1'),
    serviceAccountEmail: requireEnv('ADMIN_SCHEDULER_SERVICE_ACCOUNT'),
    targetBaseUrl: process.env.ADMIN_SCHEDULER_TARGET_BASE_URL
  } satisfies AdminSchedulerConfig;

  const monitoring: AdminMonitoringConfig = {
    enabled: parseBoolean(process.env.ADMIN_MONITORING_ENABLED, true),
    projectId: requireEnv('ADMIN_MONITORING_PROJECT', base.firestore.projectId),
    sqlInstance: process.env.ADMIN_MONITORING_SQL_INSTANCE,
    sqlDatabase: process.env.ADMIN_MONITORING_SQL_DATABASE,
    sqlTable: process.env.ADMIN_MONITORING_SQL_TABLE,
    firestoreCollection: process.env.ADMIN_MONITORING_FIRESTORE_COLLECTION,
    alertThresholdDays: parseNumber(process.env.ADMIN_ALERT_THRESHOLD_DAYS, 10, 1),
    maxLookbackDays: parseNumber(process.env.ADMIN_MONITORING_MAX_LOOKBACK_DAYS, 14, 1),
    optionalForHealth: parseBoolean(process.env.ADMIN_MONITORING_OPTIONAL_FOR_HEALTH, false)
  } satisfies AdminMonitoringConfig;

  const iam: AdminIamConfig = {
    globalRole: requireEnv('ADMIN_IAM_GLOBAL_ROLE', 'admin.global'),
    refreshRole: requireEnv('ADMIN_IAM_REFRESH_ROLE', 'admin.refresh.write'),
    monitorRole: requireEnv('ADMIN_IAM_MONITOR_ROLE', 'admin.monitor.read'),
    auditLogMetric: requireEnv('ADMIN_IAM_AUDIT_LOG_METRIC', 'admin.audit')
  } satisfies AdminIamConfig;

  const refresh: AdminRefreshDefaults = {
    timeoutSeconds: parseNumber(process.env.ADMIN_REFRESH_TIMEOUT_SECONDS, 120, 30),
    defaultPriority: process.env.ADMIN_REFRESH_DEFAULT_PRIORITY ?? 'normal',
    allowForce: parseBoolean(process.env.ADMIN_REFRESH_ALLOW_FORCE, true)
  } satisfies AdminRefreshDefaults;

  cachedConfig = {
    base,
    pubsub,
    jobs,
    scheduler,
    monitoring,
    iam,
    refresh
  } satisfies AdminServiceConfig;

  return cachedConfig;
}

export function resetAdminConfigForTesting(): void {
  cachedConfig = null;
}
