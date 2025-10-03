import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';
import { badRequestError } from '@hh/common';

import type { RerankServiceConfig } from './config.js';
import { RerankRedisClient } from './redis-client.js';
import { rerankSchema } from './schemas.js';
import type { RerankRequest, RerankResponse } from './types.js';
import { TogetherClient } from './together-client.js';
import { RerankService } from './rerank-service.js';

interface RegisterRoutesOptions {
  service: RerankService;
  config: RerankServiceConfig;
  redisClient: RerankRedisClient;
  togetherClient: TogetherClient;
}

export async function registerRoutes(
  app: FastifyInstance,
  { service, config, redisClient, togetherClient }: RegisterRoutesOptions
): Promise<void> {

  app.get('/healthz', async (_request: FastifyRequest, reply: FastifyReply) => {
    reply.code(200);
    return { status: 'ok' } as const;
  });

  // Detailed health endpoint (basic /health is registered in index.ts before listen())
  app.get('/health/detailed', async (_request: FastifyRequest, reply: FastifyReply) => {
    const [redisHealth, togetherHealth] = await Promise.all([redisClient.healthCheck(), togetherClient.healthCheck()]);

    const degraded: Record<string, unknown> = {};
    if (!['healthy', 'disabled'].includes(redisHealth.status)) {
      degraded.redis = redisHealth;
    }
    if (!['healthy', 'disabled'].includes(togetherHealth.status)) {
      degraded.together = togetherHealth;
    }

    if (Object.keys(degraded).length > 0) {
      reply.code(503);
      return {
        status: 'degraded',
        components: {
          redis: redisHealth,
          together: togetherHealth
        }
      } satisfies Record<string, unknown>;
    }

    return {
      status: 'ok',
      redis: redisHealth,
      together: togetherHealth
    } satisfies Record<string, unknown>;
  });

  app.post(
    '/v1/search/rerank',
    {
      schema: rerankSchema
    },
    async (request: FastifyRequest<{ Body: RerankRequest }>) => {
      if (!request.tenant) {
        throw badRequestError('Tenant context is required.');
      }

      const cacheStart = Date.now();
      const disableCache = config.redis.disable || request.body.disableCache === true;
      const normalizedCandidates = request.body.candidates.slice(0, config.runtime.maxCandidates);
      const descriptor = service.buildCacheDescriptor({ ...request.body, candidates: normalizedCandidates });
      const cacheKey = redisClient.buildKey(request.tenant.id, descriptor);

      if (!disableCache) {
        const cached = await redisClient.get<RerankResponse>(cacheKey);
        if (cached) {
          const cacheHitResponse: RerankResponse = {
            ...cached,
            cacheHit: true,
            timings: {
              ...cached.timings,
              cacheMs: Date.now() - cacheStart
            }
          };
          return cacheHitResponse;
        }
      }

      const context = {
        tenant: request.tenant,
        user: request.user,
        requestId: request.requestContext.requestId
      };

      const response = await service.rerank({ context, request: request.body });
      response.timings.cacheMs = Date.now() - cacheStart;

      if (!disableCache && !response.usedFallback && response.results.length > 0) {
        await redisClient.set(cacheKey, response);
      }

      return response;
    }
  );
}
