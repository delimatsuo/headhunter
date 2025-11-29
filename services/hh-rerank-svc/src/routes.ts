import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';
import { badRequestError } from '@hh/common';

import type { RerankServiceConfig } from './config.js';
import { RerankRedisClient } from './redis-client.js';
import { rerankSchema } from './schemas.js';
import type { RerankRequest, RerankResponse } from './types.js';
import { TogetherClient } from './together-client.js';
import { GeminiClient } from './gemini-client.js';
import { RerankService } from './rerank-service.js';

interface RegisterRoutesOptions {
  service: RerankService | null;
  config: RerankServiceConfig;
  redisClient: RerankRedisClient | null;
  togetherClient: TogetherClient | null;
  geminiClient: GeminiClient | null;
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
        service: 'hh-rerank-svc'
      };
    }

    if (!dependencies.redisClient || !dependencies.togetherClient || !dependencies.geminiClient) {
      reply.status(503);
      return {
        status: 'initializing',
        service: 'hh-rerank-svc'
      };
    }

    const [redisHealth, togetherHealth, geminiHealth] = await Promise.all([
      dependencies.redisClient.healthCheck(),
      dependencies.togetherClient.healthCheck(),
      dependencies.geminiClient.healthCheck()
    ]);

    const degraded: Record<string, unknown> = {};
    if (!['healthy', 'disabled'].includes(redisHealth.status)) {
      degraded.redis = redisHealth;
    }
    if (!['healthy', 'disabled'].includes(togetherHealth.status)) {
      degraded.together = togetherHealth;
    }
    if (!['healthy', 'disabled'].includes(geminiHealth.status)) {
      degraded.gemini = geminiHealth;
    }

    if (Object.keys(degraded).length > 0) {
      reply.code(503);
      return {
        status: 'degraded',
        components: {
          redis: redisHealth,
          together: togetherHealth,
          gemini: geminiHealth
        }
      } satisfies Record<string, unknown>;
    }

    return {
      status: 'ok',
      redis: redisHealth,
      together: togetherHealth,
      gemini: geminiHealth
    } satisfies Record<string, unknown>;
  };

  app.get('/healthz', readinessHandler);
  app.get('/readyz', readinessHandler);
  app.get('/health', readinessHandler);
  app.get('/health/detailed', readinessHandler);

  app.post(
    '/v1/search/rerank',
    {
      schema: rerankSchema
    },
    async (request: FastifyRequest<{ Body: RerankRequest }>, reply: FastifyReply) => {
      if (!request.tenant) {
        throw badRequestError('Tenant context is required.');
      }

      if (!dependencies.service || !dependencies.redisClient) {
        reply.status(503);
        return { error: 'Service initializing' };
      }

      const cacheStart = Date.now();
      const disableCache = dependencies.config.redis.disable || request.body.disableCache === true;
      const normalizedCandidates = request.body.candidates.slice(0, dependencies.config.runtime.maxCandidates);
      const descriptor = dependencies.service.buildCacheDescriptor({ ...request.body, candidates: normalizedCandidates });
      const cacheKey = dependencies.redisClient.buildKey(request.tenant.id, descriptor);

      if (!disableCache) {
        try {
          const cached = await dependencies.redisClient.get<RerankResponse>(cacheKey);
          if (cached) {
            const timings = cached.timings || { totalMs: 0 };
            const cacheHitResponse: RerankResponse = {
              ...cached,
              cacheHit: true,
              timings: {
                ...timings,
                cacheMs: Date.now() - cacheStart,
                totalMs: Date.now() - cacheStart
              }
            };
            return cacheHitResponse;
          }
        } catch (error) {
          request.log.warn({ error }, 'Failed to retrieve or parse cached response');
          // Continue to fallback (non-cached) execution
        }
      }

      const context = {
        tenant: request.tenant,
        user: request.user,
        requestId: request.requestContext.requestId
      };

      const response = await dependencies.service.rerank({ context, request: request.body });
      response.timings.cacheMs = Date.now() - cacheStart;

      if (!disableCache && !response.usedFallback && response.results.length > 0) {
        await dependencies.redisClient.set(cacheKey, response);
      }

      return response;
    }
  );
}
