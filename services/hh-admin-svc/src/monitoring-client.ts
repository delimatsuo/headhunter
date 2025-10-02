import { Firestore, Timestamp } from '@google-cloud/firestore';
import { MetricServiceClient } from '@google-cloud/monitoring';
import { Connector, IpAddressTypes } from '@google-cloud/cloud-sql-connector';
import { getLogger } from '@hh/common';
import { Pool } from 'pg';

import type { AdminMonitoringConfig } from './config';
import type {
  JobHealthSnapshot,
  MonitoringSnapshot,
  MonitoringSnapshotOptions,
  SnapshotSection,
  SnapshotTenantLag,
  TenantSnapshotSourceResult
} from './types';
import type { protos as monitoringProtos } from '@google-cloud/monitoring';

const logger = getLogger({ module: 'admin-monitoring-client' });

const DEFAULT_JOB_HEALTH: JobHealthSnapshot = {
  recentExecutions: 0,
  recentFailures: 0,
  successRatio: 1,
  alertState: 'ok'
};

type TimeSeries = monitoringProtos.google.monitoring.v3.ITimeSeries;
type Point = monitoringProtos.google.monitoring.v3.IPoint;

export class MonitoringClient {
  private readonly config: AdminMonitoringConfig;
  private readonly firestore?: Firestore;
  private readonly metricClient: MetricServiceClient;
  private pool?: Pool;
  private connector?: Connector;

  constructor(config: AdminMonitoringConfig, firestore?: Firestore, pool?: Pool, connector?: Connector) {
    this.config = config;
    this.firestore = config.firestoreCollection ? firestore ?? new Firestore({ projectId: config.projectId }) : undefined;
    this.metricClient = new MetricServiceClient();
    this.pool = pool;
    this.connector = connector;
  }

  async getSnapshot(options: MonitoringSnapshotOptions): Promise<MonitoringSnapshot> {
    const lookbackDays = Math.min(options.lookbackDays, this.config.maxLookbackDays);

    const [postingsSource, profilesSource, jobHealth] = await Promise.all([
      this.fetchPostingFreshness(options.tenantId, lookbackDays).catch((error) => {
        logger.warn({ error }, 'Failed to fetch posting freshness.');
        return [] as TenantSnapshotSourceResult[];
      }),
      this.fetchProfileFreshness(options.tenantId, lookbackDays).catch((error) => {
        logger.warn({ error }, 'Failed to fetch profile freshness.');
        return [] as TenantSnapshotSourceResult[];
      }),
      this.fetchJobHealth(lookbackDays).catch((error) => {
        logger.warn({ error }, 'Failed to fetch job health metrics.');
        return DEFAULT_JOB_HEALTH;
      })
    ]);

    const postings = this.buildSnapshotSection(postingsSource);
    const profiles = this.buildSnapshotSection(profilesSource);

    return {
      postings,
      profiles,
      jobHealth
    } satisfies MonitoringSnapshot;
  }

  private async fetchPostingFreshness(tenantId: string | undefined, lookbackDays: number): Promise<TenantSnapshotSourceResult[]> {
    if (!this.config.enabled || !this.config.sqlTable) {
      return [];
    }

    const pool = await this.ensurePool();
    if (!pool) {
      return [];
    }

    const params: unknown[] = [];
    const where: string[] = [];
    if (tenantId) {
      where.push('tenant_id = $1');
      params.push(tenantId);
    }

    const startTime = new Date(Date.now() - lookbackDays * 24 * 60 * 60 * 1000);
    where.push('last_ingested_at >= $' + (params.length + 1));
    params.push(startTime.toISOString());

    const query = [
      'SELECT tenant_id, MAX(last_ingested_at) AS last_updated_at',
      `FROM ${this.config.sqlTable}`,
      where.length > 0 ? `WHERE ${where.join(' AND ')}` : '',
      'GROUP BY tenant_id'
    ]
      .filter((part) => part.length > 0)
      .join(' ');

    const result = await pool.query<{ tenant_id: string; last_updated_at: Date | string | null }>(query, params as unknown[]);

    return result.rows.map((row) => ({
      tenantId: row.tenant_id,
      updatedAt: row.last_updated_at instanceof Date ? row.last_updated_at : row.last_updated_at ? new Date(row.last_updated_at) : null
    }));
  }

  private async fetchProfileFreshness(tenantId: string | undefined, lookbackDays: number): Promise<TenantSnapshotSourceResult[]> {
    if (!this.config.enabled || !this.firestore || !this.config.firestoreCollection) {
      return [];
    }

    const collection = this.firestore.collection(this.config.firestoreCollection);

    if (tenantId) {
      const snapshot = await collection
        .where('tenantId', '==', tenantId)
        .orderBy('updatedAt', 'desc')
        .limit(1)
        .get();

      return snapshot.docs.map((doc) => ({
        tenantId,
        updatedAt: this.toDate(doc.get('updatedAt'))
      }));
    }

    const since = Timestamp.fromDate(new Date(Date.now() - lookbackDays * 24 * 60 * 60 * 1000));
    const snapshot = await collection.where('updatedAt', '>=', since).select('tenantId', 'updatedAt').get();

    const byTenant = new Map<string, Date | null>();

    for (const doc of snapshot.docs) {
      const tenant = doc.get('tenantId') as string | undefined;
      if (!tenant) {
        continue;
      }

      const updatedAt = this.toDate(doc.get('updatedAt'));
      const existing = byTenant.get(tenant);
      if (!existing || (updatedAt && existing < updatedAt)) {
        byTenant.set(tenant, updatedAt ?? existing ?? null);
      }
    }

    return Array.from(byTenant.entries()).map(([tenant, updatedAt]) => ({ tenantId: tenant, updatedAt }));
  }

  private async fetchJobHealth(lookbackDays: number): Promise<JobHealthSnapshot> {
    if (!this.config.enabled) {
      return DEFAULT_JOB_HEALTH;
    }

    const projectName = this.metricClient.projectPath(this.config.projectId);
    const intervalEnd = { seconds: Math.floor(Date.now() / 1000) };
    const intervalStart = { seconds: Math.floor((Date.now() - lookbackDays * 24 * 60 * 60 * 1000) / 1000) };

    const [successSeries] = await this.metricClient.listTimeSeries({
      name: projectName,
      filter: 'metric.type="custom.googleapis.com/hh_admin/refresh_job_success"',
      interval: { startTime: intervalStart, endTime: intervalEnd },
      view: 'FULL'
    });

    const [failureSeries] = await this.metricClient.listTimeSeries({
      name: projectName,
      filter: 'metric.type="custom.googleapis.com/hh_admin/refresh_job_failure"',
      interval: { startTime: intervalStart, endTime: intervalEnd },
      view: 'FULL'
    });

    const successes = this.sumPoints(successSeries);
    const failures = this.sumPoints(failureSeries);
    const total = successes + failures;
    const successRatio = total === 0 ? 1 : successes / total;

    let alertState: JobHealthSnapshot['alertState'] = 'ok';
    if (failures > 0 && failures <= 2) {
      alertState = 'warning';
    } else if (failures > 2) {
      alertState = 'critical';
    }

    const failurePoints = (failureSeries ?? [])
      .filter((series): series is TimeSeries => Boolean(series))
      .flatMap((series) => (Array.isArray(series.points) ? series.points : []))
      .filter((point): point is Point => Boolean(point));

    failurePoints.sort((a, b) => {
      const aTs = this.coerceNumeric(a.interval?.endTime?.seconds);
      const bTs = this.coerceNumeric(b.interval?.endTime?.seconds);
      return bTs - aTs;
    });

    const lastFailurePoint = failurePoints[0];
    const lastFailureSeconds = lastFailurePoint ? this.coerceNumeric(lastFailurePoint.interval?.endTime?.seconds) : 0;
    const lastFailureAt = lastFailureSeconds > 0 ? new Date(lastFailureSeconds * 1000).toISOString() : undefined;

    return {
      recentExecutions: total,
      recentFailures: failures,
      successRatio,
      alertState,
      lastFailureAt
    } satisfies JobHealthSnapshot;
  }

  private sumPoints(series: TimeSeries[] | null | undefined): number {
    if (!series) {
      return 0;
    }

    let total = 0;
    for (const entry of series) {
      if (!entry) {
        continue;
      }
      const points = Array.isArray(entry.points) ? entry.points : [];
      for (const point of points) {
        const value = point?.value;
        if (!value) {
          continue;
        }

        if (value.int64Value !== undefined && value.int64Value !== null) {
          total += this.coerceNumeric(value.int64Value);
        } else if (value.doubleValue !== undefined && value.doubleValue !== null) {
          total += value.doubleValue;
        } else if (value.distributionValue?.count !== undefined && value.distributionValue.count !== null) {
          total += this.coerceNumeric(value.distributionValue.count);
        }
      }
    }

    return total;
  }

  private buildSnapshotSection(source: TenantSnapshotSourceResult[]): SnapshotSection {
    if (source.length === 0) {
      return {
        lastUpdatedAt: undefined,
        maxLagDays: 0,
        staleTenants: []
      } satisfies SnapshotSection;
    }

    let lastUpdated: Date | undefined;
    let maxLagDays = 0;
    const stale: SnapshotTenantLag[] = [];

    for (const entry of source) {
      if (!entry.updatedAt) {
        stale.push({ tenantId: entry.tenantId, lagDays: this.config.alertThresholdDays + 1 });
        continue;
      }

      if (!lastUpdated || lastUpdated < entry.updatedAt) {
        lastUpdated = entry.updatedAt;
      }

      const lagDays = this.calculateLagDays(entry.updatedAt);
      maxLagDays = Math.max(maxLagDays, lagDays);

      if (lagDays >= this.config.alertThresholdDays) {
        stale.push({ tenantId: entry.tenantId, lagDays, lastUpdatedAt: entry.updatedAt.toISOString() });
      }
    }

    return {
      lastUpdatedAt: lastUpdated?.toISOString(),
      maxLagDays,
      staleTenants: stale.sort((a, b) => b.lagDays - a.lagDays)
    } satisfies SnapshotSection;
  }

  private calculateLagDays(date: Date): number {
    const diffMs = Date.now() - date.getTime();
    return Math.max(0, Math.round((diffMs / (1000 * 60 * 60 * 24)) * 10) / 10);
  }

  private toDate(value: unknown): Date | null {
    if (!value) {
      return null;
    }

    if (value instanceof Date) {
      return value;
    }

    if (value instanceof Timestamp) {
      return value.toDate();
    }

    if (typeof value === 'string') {
      const parsed = new Date(value);
      return Number.isNaN(parsed.getTime()) ? null : parsed;
    }

    if (typeof value === 'object' && value !== null) {
      const seconds = (value as { seconds?: number }).seconds;
      if (typeof seconds === 'number') {
        return new Date(seconds * 1000);
      }
    }

    return null;
  }

  private async ensurePool(): Promise<Pool | null> {
    if (this.pool) {
      return this.pool;
    }

    const database = this.config.sqlDatabase ?? process.env.PGDATABASE ?? 'headhunter';
    const user = process.env.ADMIN_MONITORING_SQL_USER ?? process.env.PGUSER ?? 'postgres';
    const password = process.env.ADMIN_MONITORING_SQL_PASSWORD ?? process.env.PGPASSWORD ?? 'postgres';
    const maxClients = Number(process.env.ADMIN_MONITORING_SQL_MAX_CLIENTS ?? 5);
    const statementTimeout = Number(process.env.ADMIN_MONITORING_SQL_STATEMENT_TIMEOUT_MS ?? 30_000);

    if (this.config.sqlInstance) {
      if (!this.connector) {
        this.connector = new Connector();
      }

      const ipType = this.resolveConnectorIpType(process.env.ADMIN_MONITORING_SQL_IP_TYPE);
      const connectorOptions = await this.connector.getOptions({
        instanceConnectionName: this.config.sqlInstance,
        ipType
      });

      this.pool = new Pool({
        ...connectorOptions,
        database,
        user,
        password,
        max: maxClients,
        statement_timeout: statementTimeout
      });
    } else {
      const host = process.env.ADMIN_MONITORING_SQL_HOST ?? process.env.PGHOST ?? '127.0.0.1';
      const port = Number(process.env.ADMIN_MONITORING_SQL_PORT ?? process.env.PGPORT ?? 5432);

      this.pool = new Pool({ host, database, user, password, port, max: maxClients, statement_timeout: statementTimeout });
    }

    this.pool.on('error', (error) => {
      logger.error({ error }, 'Unexpected error from monitoring Postgres pool.');
    });

    return this.pool;
  }

  async healthCheck(): Promise<boolean> {
    if (!this.config.enabled) {
      return true;
    }

    try {
      if (this.firestore) {
        await this.firestore.listCollections();
      }
      if (this.config.sqlTable) {
        const pool = await this.ensurePool();
        await pool?.query('SELECT 1');
      }
      return true;
    } catch (error) {
      logger.warn({ error }, 'Monitoring health check failed.');
      return false;
    }
  }

  async shutdown(): Promise<void> {
    await this.pool?.end?.();
    await this.connector?.close?.();
  }

  private resolveConnectorIpType(value: string | undefined): IpAddressTypes {
    const normalized = value?.toUpperCase();
    if (normalized === 'PRIVATE') {
      return IpAddressTypes.PRIVATE;
    }
    if (normalized === 'PSC') {
      return IpAddressTypes.PSC;
    }
    return IpAddressTypes.PUBLIC;
  }

  private coerceNumeric(value: unknown): number {
    if (typeof value === 'number') {
      return Number.isFinite(value) ? value : 0;
    }
    if (typeof value === 'bigint') {
      return Number(value);
    }
    if (typeof value === 'string') {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : 0;
    }
    if (value && typeof (value as { toString(): string }).toString === 'function') {
      const parsed = Number((value as { toString(): string }).toString());
      return Number.isFinite(parsed) ? parsed : 0;
    }
    return 0;
  }
}
