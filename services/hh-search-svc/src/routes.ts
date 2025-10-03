import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';
import { badRequestError } from '@hh/common';

import type { SearchServiceConfig } from './config';
import type { EmbedClient } from './embed-client';
import type { PgVectorClient } from './pgvector-client';
import { SearchRedisClient } from './redis-client';
import { hybridSearchSchema } from './schemas';
import type { HybridSearchRequest, HybridSearchResponse } from './types';
import { SearchService } from './search-service';

interface RegisterRoutesOptions {
  service: SearchService;
  config: SearchServiceConfig;
  redisClient: SearchRedisClient;
  pgClient: PgVectorClient;
  embedClient: EmbedClient;
}

export async function registerRoutes(
  app: FastifyInstance,
  { service, config, redisClient, pgClient, embedClient }: RegisterRoutesOptions
): Promise<void> {

  // Detailed health endpoint (basic /health is registered in index.ts before listen())
  app.get('/health/detailed', async (_request: FastifyRequest, reply: FastifyReply) => {
    const [pgHealth, redisHealth, embedHealth] = await Promise.all([
      pgClient.healthCheck(),
      redisClient.healthCheck(),
      embedClient.healthCheck()
    ]);

    const degraded: string[] = [];
    if (pgHealth.status !== 'healthy') {
      degraded.push('pgvector');
    }
    if (!['healthy', 'disabled'].includes(redisHealth.status)) {
      degraded.push('redis');
    }
    if (embedHealth.status !== 'healthy') {
      degraded.push('embeddings');
    }

    if (degraded.length > 0) {
      reply.code(503);
      return {
        status: 'degraded',
        components: {
          pgvector: pgHealth,
          redis: redisHealth,
          embeddings: embedHealth
        }
      } satisfies Record<string, unknown>;
    }

    return {
      status: 'ok',
      pgvector: pgHealth,
      redis: redisHealth,
      embeddings: embedHealth
    } satisfies Record<string, unknown>;
  });

  app.post(
    '/v1/search/hybrid',
    {
      schema: hybridSearchSchema
    },
    async (request: FastifyRequest<{ Body: HybridSearchRequest }>) => {
      if (!request.tenant) {
        throw badRequestError('Tenant context is required.');
      }

      const cacheToken = service.computeCacheToken(request.body);
      const cacheKey = redisClient.buildHybridKey(request.tenant.id, cacheToken);

      const cacheStart = Date.now();
      let cached: HybridSearchResponse | null = null;
      if (!config.redis.disable) {
        cached = await redisClient.get<HybridSearchResponse>(cacheKey);
      }

      if (cached) {
        const cacheHitResponse: HybridSearchResponse = {
          ...cached,
          cacheHit: true,
          timings: {
            ...cached.timings,
            cacheMs: Date.now() - cacheStart
          }
        };
        return cacheHitResponse;
      }

      const context = {
        tenant: request.tenant,
        user: request.user,
        requestId: request.requestContext.requestId
      };

      const response = await service.hybridSearch(context, request.body);

      response.timings.cacheMs = Date.now() - cacheStart;

      if (!config.redis.disable && response.results.length > 0) {
        await redisClient.set(cacheKey, response);
      }

      return response;
    }
  );
}
