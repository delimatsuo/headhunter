import { MetricServiceClient } from '@google-cloud/monitoring';
import type { Logger } from 'pino';

type WriteValueKey = 'doubleValue' | 'int64Value';

export type CircuitState = 'closed' | 'open' | 'half-open';

export interface MetricsExporterOptions {
  projectId: string;
  serviceName: string;
  logger: Logger;
  enabled: boolean;
}

interface WriteOptions {
  type: string;
  value: number;
  valueKey: WriteValueKey;
  labels?: Record<string, string | undefined>;
}

function sanitizeLabels(labels: Record<string, string | undefined> | undefined): Record<string, string> {
  const result: Record<string, string> = {};
  if (!labels) {
    return result;
  }

  for (const [key, value] of Object.entries(labels)) {
    if (value !== undefined && value !== '') {
      result[key] = value;
    }
  }

  return result;
}

function toBoolean(value: string | undefined, fallback: boolean): boolean {
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

export class MetricsExporter {
  private readonly logger: Logger;
  private readonly client: MetricServiceClient | null;
  private readonly projectPath: string;
  private readonly projectId: string;
  private readonly serviceName: string;
  private readonly enabled: boolean;

  constructor(options: MetricsExporterOptions) {
    this.logger = options.logger;
    this.projectId = options.projectId;
    this.serviceName = options.serviceName;
    this.enabled = options.enabled;

    if (this.enabled) {
      this.client = new MetricServiceClient();
      this.projectPath = this.client.projectPath(this.projectId);
    } else {
      this.client = null;
      this.projectPath = '';
    }
  }

  static fromEnv(projectId: string | undefined, serviceName: string, logger: Logger): MetricsExporter | null {
    if (!projectId) {
      logger.warn('Metrics exporter disabled: missing projectId.');
      return null;
    }

    const enabled = toBoolean(process.env.ENRICH_METRICS_EXPORT_ENABLED, false);
    if (!enabled) {
      logger.info('Metrics exporter disabled via ENRICH_METRICS_EXPORT_ENABLED.');
      return null;
    }

    return new MetricsExporter({ projectId, serviceName, logger, enabled: true });
  }

  recordLatencyPercentile(percentile: 'p50' | 'p95' | 'p99', valueMs: number): void {
    this.writeMetric({
      type: 'job_latency_ms',
      value: valueMs,
      valueKey: 'doubleValue',
      labels: { percentile }
    });
  }

  recordJobCompletion(tenantId: string): void {
    this.writeMetric({
      type: 'job_completed_count',
      value: 1,
      valueKey: 'int64Value',
      labels: { tenant: tenantId }
    });
  }

  recordJobFailure(tenantId: string): void {
    this.writeMetric({
      type: 'job_failed_count',
      value: 1,
      valueKey: 'int64Value',
      labels: { tenant: tenantId }
    });
  }

  recordQueueDepth(queueDepth: number): void {
    this.writeMetric({
      type: 'queue_depth',
      value: queueDepth,
      valueKey: 'int64Value'
    });
  }

  recordTenantJobCount(tenantId: string, created: boolean): void {
    if (!created) {
      return;
    }
    this.writeMetric({
      type: 'tenant_job_count',
      value: 1,
      valueKey: 'int64Value',
      labels: { tenant: tenantId }
    });
  }

  recordEmbedOutcome(options: { tenantId: string; success: boolean; skipped: boolean; durationMs: number; attempts: number; skippedReason?: string }): void {
    const value = options.success ? 1 : 0;
    this.writeMetric({
      type: 'embed_success_ratio',
      value,
      valueKey: 'doubleValue',
      labels: {
        tenant: options.tenantId,
        skipped: String(options.skipped)
      }
    });

    if (options.skipped && options.skippedReason) {
      this.writeMetric({
        type: 'embed_skipped_count',
        value: 1,
        valueKey: 'int64Value',
        labels: {
          tenant: options.tenantId,
          reason: options.skippedReason
        }
      });
    }
  }

  recordEmbedCircuitState(state: CircuitState): void {
    const value = state === 'open' ? 1 : state === 'half-open' ? 0.5 : 0;
    this.writeMetric({
      type: 'embed_circuit_state',
      value,
      valueKey: 'doubleValue',
      labels: {
        state
      }
    });
  }

  private writeMetric(options: WriteOptions): void {
    if (!this.client || !this.enabled) {
      return;
    }

    const timestamp = Date.now();
    const seconds = Math.floor(timestamp / 1000);
    const nanos = (timestamp % 1000) * 1_000_000;

    const labels = sanitizeLabels({
      service: this.serviceName,
      ...options.labels
    });

    const metric: any = {
      type: `custom.googleapis.com/hh_enrich/${options.type}`,
      labels
    };
    metric.toJSON = () => ({
      type: metric.type,
      labels: metric.labels
    });

    const resource: any = {
      type: 'global',
      labels: {
        project_id: this.projectId
      }
    };
    resource.toJSON = () => ({
      type: resource.type,
      labels: resource.labels
    });

    const pointValue =
      options.valueKey === 'doubleValue'
        ? { doubleValue: options.value }
        : { int64Value: String(Math.trunc(options.value)) };

    const point: any = {
      interval: {
        endTime: {
          seconds,
          nanos
        }
      },
      value: pointValue
    };
    point.toJSON = () => ({
      interval: point.interval,
      value: point.value
    });

    const timeSeries: any = {
      metric,
      resource,
      points: [point]
    };
    timeSeries.toJSON = () => ({
      metric: timeSeries.metric,
      resource: timeSeries.resource,
      points: timeSeries.points
    });

    const request: any = {
      name: this.projectPath,
      timeSeries: [timeSeries]
    };

    void this.client
      .createTimeSeries(request)
      .catch((error: unknown) => {
        this.logger.warn({ error, metric: options.type }, 'Failed to write custom metric.');
      });
  }
}
