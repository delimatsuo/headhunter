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
  jobStore: EnrichmentJobStore;
  service: EnrichmentService;
  worker: EnrichmentWorker;
}

export async function registerRoutes(app: FastifyInstance, options: RegisterRoutesOptions): Promise<void> {
  const logger = getLogger({ module: 'enrich-routes' });

  // Detailed health endpoint (basic /health is registered in index.ts before listen())
  app.get('/health/detailed', async (_request, reply) => {
    try {
      const redis = await options.jobStore.getRedis();
      await redis.ping();
      return { status: 'ok' };
    } catch (error) {
      logger.error({ error }, 'Health check failed.');
      reply.status(503);
      return { status: 'unhealthy' };
    }
  });

  app.post(
    '/v1/enrich/profile',
    { schema: enrichProfileSchema },
    async (request: FastifyRequest<{ Body: EnrichProfileRequest }>, reply: FastifyReply) => {
      if (!request.tenant) {
        throw badRequestError('Tenant context is required.');
      }

      const asyncMode = request.body.async !== false;
      const { job, created } = await options.service.submitJob(
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
        const completed = await options.service.waitForCompletion(job.jobId, options.config.queue.jobTimeoutMs);
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
    async (request: FastifyRequest<{ Params: { jobId: string } }>) => {
      const job = await options.service.getStatus(request.params.jobId);
      if (!job) {
        return { job: null };
      }
      return { job };
    }
  );

  app.addHook('onClose', async () => {
    await options.worker.stop();
  });
}
