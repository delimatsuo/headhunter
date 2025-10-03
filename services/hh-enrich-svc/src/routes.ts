import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';
import { badRequestError, getLogger } from '@hh/common';

import type { EnrichServiceConfig } from './config';
import { EnrichmentJobStore } from './job-store';
import { EnrichmentService } from './enrichment-service';
import { enrichProfileSchema, enrichmentStatusSchema } from './schemas';
import type { EnrichProfileRequest } from './types';
import { EnrichmentWorker } from './worker';

interface RegisterRoutesOptions {
  config: EnrichServiceConfig;
  jobStore: EnrichmentJobStore | null;
  service: EnrichmentService | null;
  worker: EnrichmentWorker | null;
  state: { isReady: boolean };
}

export async function registerRoutes(app: FastifyInstance, dependencies: RegisterRoutesOptions): Promise<void> {
  const logger = getLogger({ module: 'enrich-routes' });

  const readinessHandler = async (_request: FastifyRequest, reply: FastifyReply) => {
    // If not ready, dependencies are still null - return initializing
    if (!dependencies.state.isReady) {
      reply.status(503);
      return {
        status: 'initializing',
        service: 'hh-enrich-svc'
      };
    }

    if (!dependencies.jobStore) {
      reply.status(503);
      return {
        status: 'initializing',
        service: 'hh-enrich-svc'
      };
    }

    try {
      const redis = await dependencies.jobStore.getRedis();
      await redis.ping();
      return { status: 'ok' };
    } catch (error) {
      logger.error({ error }, 'Health check failed.');
      reply.status(503);
      return { status: 'unhealthy' };
    }
  };

  app.get('/healthz', readinessHandler);
  app.get('/readyz', readinessHandler);
  app.get('/health', readinessHandler);
  app.get('/health/detailed', readinessHandler);

  app.post(
    '/v1/enrich/profile',
    { schema: enrichProfileSchema },
    async (request: FastifyRequest<{ Body: EnrichProfileRequest }>, reply: FastifyReply) => {
      if (!request.tenant) {
        throw badRequestError('Tenant context is required.');
      }

      if (!dependencies.service) {
        reply.status(503);
        return { error: 'Service initializing' };
      }

      const asyncMode = request.body.async !== false;
      const { job, created } = await dependencies.service.submitJob(
        {
          tenant: request.tenant,
          user: request.user,
          requestId: request.requestContext.requestId
        },
        request.body
      );

      if (created) {
        logger.info({ jobId: job.jobId, tenantId: job.tenantId }, 'Queued enrichment job.');
      }

      if (!asyncMode) {
        const completed = await dependencies.service.waitForCompletion(job.jobId, dependencies.config.queue.jobTimeoutMs);
        reply.status(completed?.status === 'completed' ? 200 : 202);
        return { job: completed ?? job };
      }

      reply.status(202);
      return { job };
    }
  );

  app.get(
    '/v1/enrich/status/:jobId',
    { schema: enrichmentStatusSchema },
    async (request: FastifyRequest<{ Params: { jobId: string } }>, reply: FastifyReply) => {
      if (!dependencies.service) {
        reply.status(503);
        return { error: 'Service initializing' };
      }

      const job = await dependencies.service.getStatus(request.params.jobId);
      if (!job) {
        return { job: null };
      }
      return { job };
    }
  );

  app.addHook('onClose', async () => {
    if (dependencies.worker) {
      await dependencies.worker.stop();
    }
  });
}
