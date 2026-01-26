import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';
import { Pool } from 'pg';
import { badRequestError } from '@hh/common';

import type { AdminServiceConfig } from './config';
import { AdminService } from './admin-service';
import { AdminIamValidator } from './iam-validator';
import { AdminJobsClient } from './jobs-client';
import { MonitoringClient } from './monitoring-client';
import { AdminPubSubClient } from './pubsub-client';
import { refreshPostingsSchema, refreshProfilesSchema, snapshotsSchema } from './schemas';
import type { RefreshContext, RefreshPostingsRequest, RefreshProfilesRequest } from './types';

interface RouteDependencies {
  config: AdminServiceConfig;
  service: AdminService;
  pubsub: AdminPubSubClient;
  jobs: AdminJobsClient;
  monitoring: MonitoringClient;
  iam: AdminIamValidator;
  state: { isReady: boolean };
  pgPool?: Pool;
}

export async function registerRoutes(app: FastifyInstance, dependencies: RouteDependencies): Promise<void> {
  app.get('/healthz', async () => ({
    status: 'ok',
    uptimeSeconds: Math.round(process.uptime()),
    timestamp: new Date().toISOString()
  }));

  const readinessHandler = async (_request: FastifyRequest, reply: FastifyReply) => {
    // If not ready, dependencies are still null - return initializing
    if (!dependencies.state.isReady) {
      reply.status(503);
      return {
        status: 'initializing',
        service: 'hh-admin-svc'
      };
    }

    const [pubsubHealthy, jobsHealthy, monitoringHealthy] = await Promise.all([
      dependencies.pubsub.healthCheck(),
      dependencies.jobs.healthCheck(),
      dependencies.monitoring.healthCheck()
    ]);

    const monitoringOptional = dependencies.config.monitoring.optionalForHealth;
    const overallHealthy = pubsubHealthy && jobsHealthy && (monitoringHealthy || monitoringOptional);

    if (!overallHealthy) {
      reply.status(503);
    }

    const status: 'ok' | 'degraded' | 'unhealthy' = overallHealthy
      ? monitoringHealthy
        ? 'ok'
        : 'degraded'
      : 'unhealthy';

    return {
      status,
      checks: {
        pubsub: pubsubHealthy,
        jobs: jobsHealthy,
        monitoring: {
          healthy: monitoringHealthy,
          optional: monitoringOptional
        }
      }
    };
  };

  app.get('/readyz', readinessHandler);
  app.get('/health', readinessHandler);

  app.post(
    '/v1/admin/refresh-postings',
    { schema: refreshPostingsSchema },
    async (request: FastifyRequest<{ Body: RefreshPostingsRequest }>, reply: FastifyReply) => {
      const context = buildContext(request);
      const tenantId = request.body.tenantId ?? context.tenant?.id;
      if (!tenantId) {
        throw badRequestError('tenantId is required for postings refresh.');
      }

      dependencies.iam.ensureRefreshAccess(context, tenantId, Boolean(request.body.force), dependencies.config.refresh.allowForce);
      const response = await dependencies.service.refreshPostings(context, request.body);
      reply.status(response.status === 'completed' ? 200 : 202);
      return response;
    }
  );

  app.post(
    '/v1/admin/refresh-profiles',
    { schema: refreshProfilesSchema },
    async (request: FastifyRequest<{ Body: RefreshProfilesRequest }>, reply: FastifyReply) => {
      const context = buildContext(request);
      dependencies.iam.ensureRefreshAccess(context, request.body.tenantId ?? context.tenant?.id, Boolean(request.body.force), dependencies.config.refresh.allowForce);
      const response = await dependencies.service.refreshProfiles(context, request.body);
      reply.status(response.status === 'completed' ? 200 : 202);
      return response;
    }
  );

  app.get(
    '/v1/admin/snapshots',
    { schema: snapshotsSchema },
    async (request: FastifyRequest<{ Querystring: { tenantId?: string } }>) => {
      const context = buildContext(request);
      dependencies.iam.ensureMonitoringAccess(context);
      return dependencies.service.getSnapshots(context, request.query.tenantId);
    }
  );

  /**
   * GET /admin/bias-metrics
   * Fetch computed bias metrics for the dashboard.
   * Returns selection rates by dimension and adverse impact alerts.
   */
  app.get('/admin/bias-metrics', {
    schema: {
      querystring: {
        type: 'object',
        properties: {
          days: { type: 'number', default: 30 },
          dimension: { type: 'string', enum: ['company_tier', 'experience_band', 'specialty', 'all'] },
          tenant_id: { type: 'string' }
        }
      },
      response: {
        200: {
          type: 'object',
          properties: {
            computed_at: { type: ['string', 'null'] },
            period: {
              type: 'object',
              properties: {
                days: { type: 'number' },
                start: { type: ['string', 'null'] },
                end: { type: ['string', 'null'] }
              }
            },
            dimensions: { type: 'object', additionalProperties: true },
            any_adverse_impact: { type: 'boolean' },
            all_warnings: { type: 'array', items: { type: 'string' } }
          }
        }
      }
    }
  }, async (request, reply) => {
    const { days = 30, dimension = 'all', tenant_id } = request.query as {
      days?: number;
      dimension?: string;
      tenant_id?: string;
    };

    if (!dependencies.pgPool) {
      return reply.status(503).send({
        error: 'Database connection not available',
        computed_at: null,
        period: { days, start: null, end: null },
        dimensions: {},
        any_adverse_impact: false,
        all_warnings: ['Database pool not initialized']
      });
    }

    try {
      // Fetch latest computed metrics from database
      const result = await dependencies.pgPool.query(
        `SELECT metrics_json, computed_at
         FROM bias_metrics
         WHERE ($1::text IS NULL OR tenant_id = $1)
         ORDER BY computed_at DESC
         LIMIT 1`,
        [tenant_id || null]
      );

      if (result.rows.length === 0) {
        // No metrics yet - return empty state
        return reply.send({
          computed_at: null,
          period: { days, start: null, end: null },
          dimensions: {},
          any_adverse_impact: false,
          all_warnings: ['No bias metrics computed yet. Run bias_metrics_worker.py to generate metrics.']
        });
      }

      const metrics = result.rows[0].metrics_json;

      // Filter to requested dimension if not 'all'
      if (dimension !== 'all' && metrics.dimensions) {
        const filteredDimensions: Record<string, unknown> = {};
        if (metrics.dimensions[dimension]) {
          filteredDimensions[dimension] = metrics.dimensions[dimension];
        }
        metrics.dimensions = filteredDimensions;
      }

      return reply.send(metrics);
    } catch (error) {
      request.log.error({ error }, 'Failed to fetch bias metrics');
      return reply.status(500).send({ error: 'Failed to fetch bias metrics' });
    }
  });

  /**
   * GET /admin/bias-metrics/history
   * Fetch historical bias metrics for trend analysis.
   */
  app.get('/admin/bias-metrics/history', {
    schema: {
      querystring: {
        type: 'object',
        properties: {
          days: { type: 'number', default: 90 },
          dimension: { type: 'string' },
          tenant_id: { type: 'string' }
        }
      }
    }
  }, async (request, reply) => {
    const { days = 90, dimension, tenant_id } = request.query as {
      days?: number;
      dimension?: string;
      tenant_id?: string;
    };

    if (!dependencies.pgPool) {
      return reply.status(503).send({
        error: 'Database connection not available',
        history: [],
        days,
        dimension
      });
    }

    try {
      const result = await dependencies.pgPool.query(
        `SELECT computed_at, metrics_json
         FROM bias_metrics
         WHERE computed_at >= NOW() - INTERVAL '1 day' * $1
           AND ($2::text IS NULL OR tenant_id = $2)
         ORDER BY computed_at ASC`,
        [days, tenant_id || null]
      );

      const history = result.rows.map(row => ({
        date: row.computed_at,
        metrics: dimension
          ? row.metrics_json.dimensions?.[dimension]
          : row.metrics_json
      }));

      return reply.send({ history, days, dimension });
    } catch (error) {
      request.log.error({ error }, 'Failed to fetch bias metrics history');
      return reply.status(500).send({ error: 'Failed to fetch metrics history' });
    }
  });

  app.addHook('onClose', async () => {
    await dependencies.monitoring.shutdown();
    if (dependencies.pgPool) {
      await dependencies.pgPool.end();
    }
  });
}

function buildContext(request: FastifyRequest): RefreshContext {
  return {
    requestId: request.requestContext?.requestId ?? request.id,
    user: request.user,
    tenant: request.tenant
  };
}
