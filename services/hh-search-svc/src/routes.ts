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
  service: SearchService | null;
  config: SearchServiceConfig;
  redisClient: SearchRedisClient | null;
  pgClient: PgVectorClient | null;
  embedClient: EmbedClient | null;
  state: { isReady: boolean };
}

export async function registerRoutes(
  app: FastifyInstance,
  dependencies: RegisterRoutesOptions
): Promise<void> {

  const readinessHandler = async (_request: FastifyRequest, reply: FastifyReply) => {
    // If not ready, dependencies are still null - return initializing
    if (!dependencies.state.isReady) {
      reply.status(503);
      return {
        status: 'initializing',
        service: 'hh-search-svc'
      };
    }

    if (!dependencies.pgClient || !dependencies.redisClient || !dependencies.embedClient) {
      reply.status(503);
      return {
        status: 'initializing',
        service: 'hh-search-svc'
      };
    }

    const [pgHealth, redisHealth, embedHealth] = await Promise.all([
      dependencies.pgClient.healthCheck(),
      dependencies.redisClient.healthCheck(),
      dependencies.embedClient.healthCheck()
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
  };

  app.get('/healthz', readinessHandler);
  app.get('/readyz', readinessHandler);
  app.get('/health', readinessHandler);
  app.get('/health/detailed', readinessHandler);

  app.post(
    '/v1/search/hybrid',
    {
      schema: hybridSearchSchema
    },
    async (request: FastifyRequest<{ Body: HybridSearchRequest }>, reply: FastifyReply) => {
      if (!request.tenant) {
        throw badRequestError('Tenant context is required.');
      }

      if (!dependencies.service || !dependencies.redisClient) {
        reply.status(503);
        return { error: 'Service initializing' };
      }

      const cacheToken = dependencies.service.computeCacheToken(request.body);
      const cacheKey = dependencies.redisClient.buildHybridKey(request.tenant.id, cacheToken);

      const cacheStart = Date.now();
      let cached: HybridSearchResponse | null = null;
      if (!dependencies.config.redis.disable) {
        cached = await dependencies.redisClient.get<HybridSearchResponse>(cacheKey);
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

      const response = await dependencies.service.hybridSearch(context, request.body);

      response.timings.cacheMs = Date.now() - cacheStart;

      if (!dependencies.config.redis.disable && response.results.length > 0) {
        await dependencies.redisClient.set(cacheKey, response);
      }

      return response;
    }
  );
}
