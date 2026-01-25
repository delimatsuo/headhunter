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

        // Add Server-Timing headers for observability
        const serverTimingParts: string[] = [];
        if (cached.timings.embeddingMs !== undefined) {
          serverTimingParts.push(`embedding;dur=${cached.timings.embeddingMs};desc="Embedding generation"`);
        }
        if (cached.timings.retrievalMs !== undefined) {
          serverTimingParts.push(`retrieval;dur=${cached.timings.retrievalMs};desc="Vector+Text retrieval"`);
        }
        if (cached.timings.rerankMs !== undefined) {
          serverTimingParts.push(`rerank;dur=${cached.timings.rerankMs};desc="LLM reranking"`);
        }
        serverTimingParts.push(`total;dur=${cached.timings.totalMs};desc="Total search time"`);
        serverTimingParts.push(`cache;desc="hit"`);

        reply.header('Server-Timing', serverTimingParts.join(', '));
        reply.header('X-Response-Time', `${cached.timings.totalMs}ms`);
        reply.header('X-Cache-Status', 'hit');

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

      // Build Server-Timing header for observability
      // Format: <name>;dur=<duration>;desc="<description>"
      const serverTimingParts: string[] = [];

      if (response.timings.embeddingMs !== undefined) {
        serverTimingParts.push(`embedding;dur=${response.timings.embeddingMs};desc="Embedding generation"`);
      }
      if (response.timings.retrievalMs !== undefined) {
        serverTimingParts.push(`retrieval;dur=${response.timings.retrievalMs};desc="Vector+Text retrieval"`);
      }
      if (response.timings.rerankMs !== undefined) {
        serverTimingParts.push(`rerank;dur=${response.timings.rerankMs};desc="LLM reranking"`);
      }
      serverTimingParts.push(`total;dur=${response.timings.totalMs};desc="Total search time"`);

      // Add cache status
      serverTimingParts.push(`cache;desc="miss"`);

      // Set the headers
      reply.header('Server-Timing', serverTimingParts.join(', '));
      reply.header('X-Response-Time', `${response.timings.totalMs}ms`);
      reply.header('X-Cache-Status', 'miss');

      // Add rerank cache hit header if available
      if ((response.metadata as { rerank?: { cacheHit?: boolean } })?.rerank?.cacheHit !== undefined) {
        reply.header('X-Rerank-Cache', (response.metadata as { rerank: { cacheHit: boolean } }).rerank.cacheHit ? 'hit' : 'miss');
      }

      // Log p95 warning if latency exceeds target
      const p95Target = 500; // 500ms target from PERF-01
      if (response.timings.totalMs > p95Target) {
        app.log.warn({
          requestId: request.requestContext.requestId,
          totalMs: response.timings.totalMs,
          p95Target,
          timings: response.timings
        }, 'Search latency exceeded p95 target');
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

        // Add Server-Timing headers for observability
        const serverTimingParts: string[] = [];
        if (cached.timings.embeddingMs !== undefined) {
          serverTimingParts.push(`embedding;dur=${cached.timings.embeddingMs};desc="Embedding generation"`);
        }
        if (cached.timings.retrievalMs !== undefined) {
          serverTimingParts.push(`retrieval;dur=${cached.timings.retrievalMs};desc="Vector+Text retrieval"`);
        }
        if (cached.timings.rerankMs !== undefined) {
          serverTimingParts.push(`ranking;dur=${cached.timings.rerankMs};desc="Signal scoring"`);
        }
        serverTimingParts.push(`total;dur=${cached.timings.totalMs};desc="Total search time"`);
        serverTimingParts.push(`cache;desc="hit"`);

        reply.header('Server-Timing', serverTimingParts.join(', '));
        reply.header('X-Response-Time', `${cached.timings.totalMs}ms`);
        reply.header('X-Cache-Status', 'hit');

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

      // Build Server-Timing header for observability
      const serverTimingParts: string[] = [];
      if (response.timings.embeddingMs !== undefined) {
        serverTimingParts.push(`embedding;dur=${response.timings.embeddingMs};desc="Embedding generation"`);
      }
      if (response.timings.retrievalMs !== undefined) {
        serverTimingParts.push(`retrieval;dur=${response.timings.retrievalMs};desc="Vector+Text retrieval"`);
      }
      if (response.timings.rerankMs !== undefined) {
        serverTimingParts.push(`ranking;dur=${response.timings.rerankMs};desc="Signal scoring"`);
      }
      serverTimingParts.push(`total;dur=${response.timings.totalMs};desc="Total search time"`);
      serverTimingParts.push(`cache;desc="miss"`);

      reply.header('Server-Timing', serverTimingParts.join(', '));
      reply.header('X-Response-Time', `${response.timings.totalMs}ms`);
      reply.header('X-Cache-Status', 'miss');

      // Add rerank cache hit header if available
      if ((response.metadata as { rerank?: { cacheHit?: boolean } })?.rerank?.cacheHit !== undefined) {
        reply.header('X-Rerank-Cache', (response.metadata as { rerank: { cacheHit: boolean } }).rerank.cacheHit ? 'hit' : 'miss');
      }

      // Log p95 warning if latency exceeds target
      const p95Target = 500; // 500ms target from PERF-01
      if (response.timings.totalMs > p95Target) {
        app.log.warn({
          requestId: request.requestContext.requestId,
          totalMs: response.timings.totalMs,
          p95Target,
          timings: response.timings
        }, 'Search latency exceeded p95 target');
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

  // Admin endpoint to run FTS migration
  app.post(
    '/admin/migrate-fts',
    async (_request: FastifyRequest, reply: FastifyReply) => {
      if (!dependencies.pgClient) {
        reply.status(503);
        return { error: 'Database not ready' };
      }

      try {
        const schema = dependencies.config.pgvector.schema;
        const profilesTable = dependencies.config.pgvector.profilesTable;
        const qualifiedTable = `${schema}.${profilesTable}`;

        app.log.info({ schema, profilesTable }, 'Running FTS migration...');

        // Drop old trigger and function
        await dependencies.pgClient.rawQuery(`
          DROP TRIGGER IF EXISTS candidate_profiles_search_document_trigger ON ${qualifiedTable};
          DROP TRIGGER IF EXISTS candidates_search_document_trigger ON ${qualifiedTable};
          DROP FUNCTION IF EXISTS update_candidate_search_document();
        `);

        // Create new function with Portuguese dictionary
        await dependencies.pgClient.rawQuery(`
          CREATE OR REPLACE FUNCTION update_candidate_search_document()
          RETURNS TRIGGER AS $$
          BEGIN
              NEW.search_document := to_tsvector('portuguese',
                  COALESCE(NEW.current_title, '') || ' ' ||
                  COALESCE(NEW.headline, '') || ' ' ||
                  COALESCE(array_to_string(NEW.skills, ' '), '') || ' ' ||
                  COALESCE(array_to_string(NEW.industries, ' '), '')
              );
              RETURN NEW;
          END;
          $$ LANGUAGE plpgsql;
        `);

        // Create trigger
        await dependencies.pgClient.rawQuery(`
          CREATE TRIGGER candidate_profiles_search_document_trigger
              BEFORE INSERT OR UPDATE OF current_title, headline, skills, industries
              ON ${qualifiedTable}
              FOR EACH ROW
              EXECUTE FUNCTION update_candidate_search_document();
        `);

        // Update ALL existing candidates
        await dependencies.pgClient.rawQuery(`
          UPDATE ${qualifiedTable}
          SET search_document = to_tsvector('portuguese',
              COALESCE(current_title, '') || ' ' ||
              COALESCE(headline, '') || ' ' ||
              COALESCE(array_to_string(skills, ' '), '') || ' ' ||
              COALESCE(array_to_string(industries, ' '), '')
          );
        `);

        // Verify
        const verification = await dependencies.pgClient.rawQuery(`
          SELECT
              COUNT(*) as total_candidates,
              COUNT(search_document) as has_search_doc,
              SUM(CASE WHEN search_document IS NOT NULL AND length(search_document::text) > 10 THEN 1 ELSE 0 END) as populated_search_doc
          FROM ${qualifiedTable};
        `);

        // Test query
        const testResult = await dependencies.pgClient.rawQuery(`
          SELECT
              candidate_id,
              full_name,
              current_title,
              ts_rank_cd(search_document, plainto_tsquery('portuguese', 'javascript')) AS text_score
          FROM ${qualifiedTable}
          WHERE search_document @@ plainto_tsquery('portuguese', 'javascript')
          ORDER BY text_score DESC
          LIMIT 3;
        `);

        app.log.info({ verification, testResult }, 'FTS migration completed');

        return {
          success: true,
          schema,
          verification: verification.rows?.[0],
          testMatches: testResult.rows?.length ?? 0,
          sampleResults: testResult.rows
        };
      } catch (error) {
        app.log.error({ error }, 'FTS migration failed');
        reply.status(500);
        return { error: error instanceof Error ? error.message : 'Migration failed' };
      }
    }
  );
}
