import { randomUUID } from 'crypto';

import type { FastifyPluginAsync, FastifyRequest } from 'fastify';
import fp from 'fastify-plugin';
import pino, { type Logger } from 'pino';

import { getConfig } from './config';
import type { RequestContext, TraceContext } from './types';

const REQUEST_START = Symbol('requestStart');
const COST_EVENTS = Symbol('costEvents');

export interface CostMetricEntry {
  tenant_id?: string | null;
  api_name: string;
  cost_cents: number;
  service?: string;
  provider?: string;
  cost_category?: string;
  request_id?: string;
  trace_id?: string;
  span_id?: string;
  source?: string;
  metadata?: Record<string, unknown>;
  occurred_at?: string;
}

type CostMetricInput = Omit<CostMetricEntry, 'request_id' | 'trace_id' | 'span_id'> & Partial<Pick<CostMetricEntry, 'request_id' | 'trace_id' | 'span_id'>>;

type CostAwareRequest = FastifyRequest & {
  [COST_EVENTS]?: CostMetricEntry[];
  logCostMetric?: (entry: CostMetricInput) => void;
};

type ChildLoggerBindings = Record<string, unknown>;

let rootLogger: Logger | null = null;
let costLogger: Logger | null = null;

function buildRootLogger(): Logger {
  const config = getConfig();
  if (!rootLogger) {
    rootLogger = pino({
      level: config.runtime.logLevel,
      base: {
        service: config.runtime.serviceName
      },
      timestamp: () => `,"timestamp":"${new Date().toISOString()}"`
    });
  }

  return rootLogger;
}

export function getLogger(bindings?: ChildLoggerBindings): Logger {
  const logger = buildRootLogger();
  return bindings ? logger.child(bindings) : logger;
}

function getCostLogger(): Logger {
  if (!costLogger) {
    const base = buildRootLogger();
    costLogger = base.child({
      logName: 'ops.cost_logs',
      stream: 'cost_metrics'
    });
  }

  return costLogger;
}

export function emitCostMetric(entry: CostMetricEntry): void {
  if (entry.cost_cents <= 0) {
    return;
  }

  const logger = getCostLogger();
  const occurredAt = entry.occurred_at ?? new Date().toISOString();
  logger.info({
    logType: 'cost_metric',
    tenant_id: entry.tenant_id ?? null,
    api_name: entry.api_name,
    cost_cents: Number(entry.cost_cents.toFixed(4)),
    cost_usd: Number((entry.cost_cents / 100).toFixed(6)),
    service: entry.service,
    provider: entry.provider,
    cost_category: entry.cost_category,
    request_id: entry.request_id,
    trace_id: entry.trace_id,
    span_id: entry.span_id,
    source: entry.source,
    metadata: entry.metadata,
    occurred_at: occurredAt
  });
}

function attachCostTracker(request: CostAwareRequest, requestId: string, traceId?: string, spanId?: string, service?: string): void {
  request[COST_EVENTS] = [];
  request.logCostMetric = (entry) => {
    const tenantHeader = request.headers['x-tenant-id'] as string | undefined;
    const fallbackTenant = typeof tenantHeader === 'string' && tenantHeader.length > 0 ? tenantHeader : null;
    const enrichedEntry: CostMetricEntry = {
      ...entry,
      tenant_id: entry.tenant_id ?? fallbackTenant,
      request_id: entry.request_id ?? requestId,
      trace_id: entry.trace_id ?? traceId,
      span_id: entry.span_id ?? spanId,
      service: entry.service ?? service
    };
    request[COST_EVENTS]?.push(enrichedEntry);
    emitCostMetric(enrichedEntry);
  };
}

function flushCostTracker(request: CostAwareRequest): void {
  const stored = request[COST_EVENTS];
  if (!stored || stored.length === 0) {
    return;
  }

  const logger = getCostLogger();
  const totalsByCategory = stored.reduce<Record<string, number>>((acc, entry) => {
    const key = entry.cost_category ?? 'uncategorized';
    acc[key] = (acc[key] ?? 0) + entry.cost_cents;
    return acc;
  }, {});

  logger.info({
    logType: 'cost_summary',
    request_id: stored[0]?.request_id,
    tenant_id: stored[0]?.tenant_id ?? null,
    trace_id: stored[0]?.trace_id,
    span_id: stored[0]?.span_id,
    service: stored[0]?.service,
    totals_by_category: totalsByCategory,
    total_cost_cents: stored.reduce((sum, entry) => sum + entry.cost_cents, 0),
    occurred_at: new Date().toISOString()
  });

  request[COST_EVENTS] = [];
}

function parseTraceContext(headerValue?: string): TraceContext | undefined {
  if (!headerValue) {
    return undefined;
  }

  const [traceAndSpan, options] = headerValue.split(';');
  const [traceId, spanId] = traceAndSpan.split('/');
  const sampled = options?.includes('o=1') ?? false;

  return {
    traceId,
    spanId,
    sampled,
    raw: headerValue
  };
}

function headerValueToString(value: unknown): string | undefined {
  if (typeof value === 'string') {
    return value;
  }

  if (Array.isArray(value)) {
    return typeof value[0] === 'string' ? value[0] : undefined;
  }

  return undefined;
}

function extractGatewayMetadata(headers: Record<string, unknown>, includeAll: boolean): Record<string, unknown> {
  const metadata: Record<string, unknown> = {};
  const mappings: Record<string, string> = {
    gatewayId: 'x-apigateway-gateway-id',
    apiId: 'x-apigateway-api-id',
    apiConfig: 'x-apigateway-api-config',
    routeId: 'x-apigateway-route-id',
    projectId: 'x-apigateway-project-id',
    backendService: 'x-apigateway-backend-service',
    stage: 'x-apigateway-stage',
    clientId: 'x-apigateway-client-id',
    quotaBucket: 'x-apigateway-quota-bucket',
    quotaConsumed: 'x-apigateway-quota-consumed'
  };

  for (const [key, headerKey] of Object.entries(mappings)) {
    const value = headerValueToString(headers[headerKey]);
    if (value) {
      metadata[key] = value;
    }
  }

  if (includeAll) {
    const mappedHeaderKeys = new Set(Object.values(mappings));

    for (const [headerKey, value] of Object.entries(headers)) {
      if (headerKey.startsWith('x-apigateway-') && !mappedHeaderKeys.has(headerKey)) {
        const normalized = headerValueToString(value);
        if (normalized) {
          metadata[headerKey] = normalized;
        }
      }
    }
  }

  return metadata;
}

export const requestLoggingPlugin: FastifyPluginAsync = fp(async (fastify) => {
  const config = getConfig();
  const enableLogging = config.runtime.enableRequestLogging;
  const traceHeaderName = config.monitoring.traceHeader.toLowerCase();
  const requestIdHeaderName = config.monitoring.requestIdHeader.toLowerCase();
  const traceProjectId = config.monitoring.traceProjectId;

  fastify.addHook('onRequest', async (request, reply) => {
    const headers = request.headers as Record<string, unknown>;
    const incomingRequestId = headers[requestIdHeaderName];
    const requestId = typeof incomingRequestId === 'string' && incomingRequestId.length > 0 ? incomingRequestId : randomUUID();
    const tenantHeader = request.headers['x-tenant-id'];
    const tenantId = typeof tenantHeader === 'string' && tenantHeader.length > 0 ? tenantHeader : null;
    const traceHeader = headers[traceHeaderName];
    const traceContext = parseTraceContext(typeof traceHeader === 'string' ? traceHeader : undefined);
    const gatewayMetadata = extractGatewayMetadata(headers, config.monitoring.logClientMetadata);
    const fullTrace = traceContext?.traceId && traceProjectId ? `projects/${traceProjectId}/traces/${traceContext.traceId}` : undefined;

    const requestContext: RequestContext = {
      requestId,
      trace: traceContext,
      gateway: gatewayMetadata
    };

    if (requestContext.trace) {
      requestContext.trace.projectId = traceProjectId;
      requestContext.trace.traceResource = fullTrace;
    }

    request.requestContext = requestContext;
    (request as unknown as Record<symbol, bigint>)[REQUEST_START] = process.hrtime.bigint();

    const baseBindings: ChildLoggerBindings = {
      request_id: requestId,
      tenant_id: tenantId,
      trace_id: traceContext?.traceId,
      span_id: traceContext?.spanId
    };

    if (gatewayMetadata.clientId) {
      baseBindings.client_id = gatewayMetadata.clientId;
    }

    if (gatewayMetadata.quotaConsumed) {
      baseBindings.quota_consumed = gatewayMetadata.quotaConsumed;
    }

    if (gatewayMetadata.quotaBucket) {
      baseBindings.quota_bucket = gatewayMetadata.quotaBucket;
    }

    if (fullTrace) {
      baseBindings['logging.googleapis.com/trace'] = fullTrace;
    }

    if (traceContext?.spanId) {
      baseBindings['logging.googleapis.com/spanId'] = traceContext.spanId;
    }

    if (traceContext?.sampled !== undefined) {
      baseBindings['logging.googleapis.com/trace_sampled'] = traceContext.sampled;
    }

    const childBindings: ChildLoggerBindings = { ...baseBindings };

    if (Object.keys(gatewayMetadata).length > 0) {
      childBindings.gateway = gatewayMetadata;
    }

    const childLogger = request.log.child(childBindings); Object.assign(request, { log: childLogger });

    attachCostTracker(
      request as CostAwareRequest,
      requestId,
      traceContext?.traceId,
      traceContext?.spanId,
      config.runtime.serviceName
    );

    if (enableLogging) {
      request.log.info(
        {
          path: request.url,
          method: request.method,
          tenant_id: tenantId,
          trace_id: traceContext?.traceId,
          client_id: gatewayMetadata.clientId,
          route_id: gatewayMetadata.routeId,
          backend_service: gatewayMetadata.backendService,
          quota_bucket: gatewayMetadata.quotaBucket
        },
        'request:start'
      );
    }

    reply.header(config.monitoring.requestIdHeader, requestId);

    if (traceContext?.raw) {
      reply.header(config.monitoring.traceHeader, traceContext.raw);
    }
  });

  fastify.addHook('onResponse', async (request, reply) => {
    if (!enableLogging) {
      return;
    }

    const start = (request as unknown as Record<symbol, bigint>)[REQUEST_START];
    const durationMs = start ? Number(process.hrtime.bigint() - start) / 1_000_000 : undefined;

    const tenantId = request.requestContext?.tenant?.id ?? request.headers['x-tenant-id'];
    const auth = request.requestContext?.auth;
    const gatewayMetadata = (request.requestContext?.gateway ?? {}) as Record<string, unknown>;

    request.log.info(
      {
        status_code: reply.statusCode,
        duration_ms: durationMs,
        tenant_id: tenantId,
        token_type: auth?.tokenType,
        issuer: auth?.issuer,
        audience: auth?.audience,
        client_id: auth?.clientId ?? (gatewayMetadata.clientId as string | undefined),
        quota_consumed: gatewayMetadata.quotaConsumed,
        quota_bucket: gatewayMetadata.quotaBucket
      },
      'request:complete'
    );

    flushCostTracker(request as CostAwareRequest);
  });
});

export function withRequestLogger(bindings: ChildLoggerBindings): Logger {
  const base: ChildLoggerBindings = {};

  const requestId = (bindings.request_id ?? bindings.requestId) as string | undefined;
  if (requestId) {
    base.request_id = requestId;
  }

  const tenantId = (bindings.tenant_id ?? bindings.tenantId) as string | undefined;
  if (tenantId) {
    base.tenant_id = tenantId;
  }

  const traceId = (bindings.trace_id ?? bindings.traceId) as string | undefined;
  if (traceId) {
    base.trace_id = traceId;
  }

  const traceResource = bindings['logging.googleapis.com/trace'] as string | undefined;
  if (traceResource) {
    base['logging.googleapis.com/trace'] = traceResource;
  }

  const spanBinding = (bindings.span_id ?? bindings.spanId) as string | undefined;
  if (spanBinding) {
    base.span_id = spanBinding;
  }

  const spanId = bindings['logging.googleapis.com/spanId'] as string | undefined;
  if (spanId) {
    base['logging.googleapis.com/spanId'] = spanId;
  }

  const requestLogger = Object.keys(base).length > 0 ? getLogger(base) : getLogger();
  return requestLogger.child(bindings);
}
