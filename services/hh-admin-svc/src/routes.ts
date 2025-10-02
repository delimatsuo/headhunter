import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';

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
}

export async function registerRoutes(app: FastifyInstance, dependencies: RouteDependencies): Promise<void> {
  app.get('/healthz', async () => ({
    status: 'ok',
    uptimeSeconds: Math.round(process.uptime()),
    timestamp: new Date().toISOString()
  }));

  const readinessHandler = async (_request: FastifyRequest, reply: FastifyReply) => {
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

  app.addHook('onClose', async () => {
    await dependencies.monitoring.shutdown();
  });
}

function buildContext(request: FastifyRequest): RefreshContext {
  return {
    requestId: request.requestContext?.requestId ?? request.id,
    user: request.user,
    tenant: request.tenant
  };
}
