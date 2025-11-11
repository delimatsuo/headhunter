import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';
import { badRequestError } from '@hh/common';

import type { SearchServiceConfig } from './config';
import type { EmbedClient } from './embed-client';
import type { PgVectorClient } from './pgvector-client';
import { SearchRedisClient } from './redis-client';
import type { RerankClient } from './rerank-client';
import type { PerformanceTracker } from './performance-tracker';
import { hybridSearchSchema, candidateSearchSchema } from './schemas';
import type { HybridSearchRequest, HybridSearchResponse, HybridSearchFilters } from './types';
import { SearchService } from './search-service';

interface RegisterRoutesOptions {
  service: SearchService | null;
  config: SearchServiceConfig;
  redisClient: SearchRedisClient | null;
  pgClient: PgVectorClient | null;
  embedClient: EmbedClient | null;
  rerankClient: RerankClient | null;
  performanceTracker: PerformanceTracker;
  state: { isReady: boolean };
}

interface CandidateSearchRequest {
  query: string;
  limit?: number;
  includeMetadata?: boolean;
  filters?: HybridSearchFilters;
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

    if (dependencies.config.rerank.enabled && !dependencies.rerankClient) {
      reply.status(503);
      return {
        status: 'initializing',
        service: 'hh-search-svc'
      };
    }

    const healthChecks = [
      dependencies.pgClient.healthCheck(),
      dependencies.redisClient.healthCheck(),
      dependencies.embedClient.healthCheck()
    ] as Promise<unknown>[];

    if (dependencies.config.rerank.enabled && dependencies.rerankClient) {
      healthChecks.push(dependencies.rerankClient.healthCheck());
    }

    const results = await Promise.all(healthChecks);
    const pgHealth = results[0] as Awaited<ReturnType<typeof dependencies.pgClient.healthCheck>>;
    const redisHealth = results[1] as Awaited<ReturnType<typeof dependencies.redisClient.healthCheck>>;
    const embedHealth = results[2] as Awaited<ReturnType<typeof dependencies.embedClient.healthCheck>>;
    const rerankHealth =
      dependencies.config.rerank.enabled && dependencies.rerankClient
        ? (results[3] as Awaited<ReturnType<typeof dependencies.rerankClient.healthCheck>>)
        : undefined;

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
    if (dependencies.config.rerank.enabled && rerankHealth && !['healthy', 'disabled'].includes(rerankHealth.status)) {
      degraded.push('rerank');
    }

    if (degraded.length > 0) {
      reply.code(503);
      return {
        status: 'degraded',
        components: {
          pgvector: pgHealth,
          redis: redisHealth,
          embeddings: embedHealth,
          rerank: rerankHealth ?? { status: 'unavailable', message: 'Rerank health unavailable' }
        },
        metrics: dependencies.performanceTracker.getSnapshot()
      } satisfies Record<string, unknown>;
    }

    return {
      status: 'ok',
      pgvector: pgHealth,
      redis: redisHealth,
      embeddings: embedHealth,
      rerank: rerankHealth ?? { status: 'disabled' },
      metrics: dependencies.performanceTracker.getSnapshot()
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

        dependencies.performanceTracker.record({
          totalMs: cached.timings.totalMs,
          embeddingMs: cached.timings.embeddingMs,
          retrievalMs: cached.timings.retrievalMs,
          rerankMs: cached.timings.rerankMs,
          cacheHit: true,
          rerankApplied: Boolean((cached.metadata as { rerank?: unknown } | undefined)?.rerank)
        });
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

  /**
   * Simplified candidate search endpoint
   * Wraps the hybrid search functionality with a user-friendly API
   */
  app.post(
    '/v1/search/candidates',
    {
      schema: candidateSearchSchema
    },
    async (request: FastifyRequest<{ Body: CandidateSearchRequest }>, reply: FastifyReply) => {
      if (!request.tenant) {
        throw badRequestError('Tenant context is required.');
      }

      if (!dependencies.service || !dependencies.redisClient) {
        reply.status(503);
        return { error: 'Service initializing' };
      }

      // Transform simple request to HybridSearchRequest format
      const hybridRequest: HybridSearchRequest = {
        query: request.body.query,
        limit: request.body.limit ?? 10,
        filters: request.body.filters,
        includeDebug: false
      };

      // Use the same caching logic as hybrid search
      const cacheToken = dependencies.service.computeCacheToken(hybridRequest);
      const cacheKey = dependencies.redisClient.buildHybridKey(request.tenant.id, cacheToken);

      const cacheStart = Date.now();
      let cached: HybridSearchResponse | null = null;
      if (!dependencies.config.redis.disable) {
        cached = await dependencies.redisClient.get<HybridSearchResponse>(cacheKey);
      }

      // If cached, transform and return
      if (cached) {
        const candidates = cached.results.map(result => ({
          id: result.candidateId,
          entityId: result.candidateId,
          score: result.score,
          similarity: result.vectorScore,
          fullName: result.fullName,
          title: result.title,
          headline: result.headline,
          location: result.location,
          industries: result.industries,
          yearsExperience: result.yearsExperience,
          skills: request.body.includeMetadata
            ? result.skills
            : result.skills?.map(s => s.name),
          metadata: request.body.includeMetadata ? result.metadata : undefined
        }));

        dependencies.performanceTracker.record({
          totalMs: cached.timings.totalMs,
          embeddingMs: cached.timings.embeddingMs,
          retrievalMs: cached.timings.retrievalMs,
          rerankMs: cached.timings.rerankMs,
          cacheHit: true,
          rerankApplied: Boolean((cached.metadata as { rerank?: unknown } | undefined)?.rerank)
        });

        return {
          candidates,
          total: cached.total,
          requestId: cached.requestId,
          cacheHit: true,
          timings: {
            totalMs: Date.now() - cacheStart,
            embeddingMs: cached.timings.embeddingMs,
            retrievalMs: cached.timings.retrievalMs,
            rankingMs: cached.timings.rerankMs ?? 0
          }
        };
      }

      // Execute search
      const context = {
        tenant: request.tenant,
        user: request.user,
        requestId: request.requestContext.requestId
      };

      const response = await dependencies.service.hybridSearch(context, hybridRequest);

      // Transform HybridSearchResponse to simpler candidate format
      const candidates = response.results.map(result => ({
        id: result.candidateId,
        entityId: result.candidateId,
        score: result.score,
        similarity: result.vectorScore,
        fullName: result.fullName,
        title: result.title,
        headline: result.headline,
        location: result.location,
        industries: result.industries,
        yearsExperience: result.yearsExperience,
        skills: request.body.includeMetadata
          ? result.skills
          : result.skills?.map(s => s.name),
        metadata: request.body.includeMetadata ? result.metadata : undefined
      }));

      // Cache the hybrid response for future requests
      if (!dependencies.config.redis.disable && response.results.length > 0) {
        await dependencies.redisClient.set(cacheKey, response);
      }

      return {
        candidates,
        total: response.total,
        requestId: response.requestId,
        cacheHit: false,
        timings: {
          totalMs: response.timings.totalMs,
          embeddingMs: response.timings.embeddingMs,
          retrievalMs: response.timings.retrievalMs,
          rankingMs: response.timings.rerankMs ?? 0
        }
      };
    }
  );
}
