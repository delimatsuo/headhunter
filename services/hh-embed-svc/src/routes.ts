import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';
import { badRequestError } from '@hh/common';

import type { EmbeddingsServiceConfig } from './config';
import { EmbeddingsService } from './embeddings-service';
import type { PgVectorClient } from './pgvector-client';
import { generateEmbeddingSchema, queryEmbeddingsSchema, upsertEmbeddingSchema } from './schemas';
import type {
  EmbeddingProviderName,
  GenerateEmbeddingRequest,
  QueryEmbeddingRequest,
  UpsertEmbeddingRequest
} from './types';

interface RegisterRoutesOptions {
  service: EmbeddingsService | null;
  config: EmbeddingsServiceConfig;
  pgClient: PgVectorClient | null;
  state: { isReady: boolean };
}

export async function registerRoutes(app: FastifyInstance, dependencies: RegisterRoutesOptions): Promise<void> {
  // Health endpoint (responds even during initialization)
  app.get('/health', async (_request, reply: FastifyReply) => {
    console.log('[ROUTE] /health endpoint called!');
    console.log('[ROUTE] Request URL:', _request.url);
    console.log('[ROUTE] Request method:', _request.method);
    console.log('[ROUTE] isReady:', dependencies.state.isReady);
    console.log('[ROUTE] pgClient exists:', !!dependencies.pgClient);

    if (!dependencies.state.isReady || !dependencies.pgClient) {
      console.log('[ROUTE] Returning 503 - initializing');
      reply.status(503);
      return { status: 'initializing', service: 'hh-embed-svc' };
    }

    console.log('[ROUTE] Checking pgClient health...');
    const health = await dependencies.pgClient.healthCheck();
    if (health.status !== 'healthy') {
      console.log('[ROUTE] Database not healthy, returning 503');
      reply.status(503);
      return {
        status: health.status,
        message: health.message ?? 'Database connection degraded.',
        poolSize: health.poolSize
      };
    }

    console.log('[ROUTE] Returning 200 OK');
    return { status: 'ok', service: 'hh-embed-svc' };
  });

  app.post(
    '/v1/embeddings/generate',
    {
      schema: generateEmbeddingSchema
    },
    async (request: FastifyRequest<{ Body: GenerateEmbeddingRequest }>, reply: FastifyReply) => {
      if (!dependencies.service) {
        reply.status(503);
        return { error: 'Service initializing, please retry' };
      }

      if (!request.tenant) {
        throw badRequestError('Tenant context is required.');
      }

      const body = request.body;
      const requestId = request.requestContext.requestId;

      return dependencies.service.generateEmbedding({
        tenant: request.tenant,
        user: request.user,
        requestId,
        text: body.text,
        metadata: body.metadata,
        provider: body.provider as EmbeddingProviderName | undefined,
        dimensions: body.dimensions
      });
    }
  );

  app.post(
    '/v1/embeddings/upsert',
    {
      schema: upsertEmbeddingSchema
    },
    async (request: FastifyRequest<{ Body: UpsertEmbeddingRequest }>, reply: FastifyReply) => {
      if (!dependencies.service) {
        reply.status(503);
        return { error: 'Service initializing, please retry' };
      }

      if (!request.tenant) {
        throw badRequestError('Tenant context is required.');
      }

      const body = request.body;
      const requestId = request.requestContext.requestId;

      return dependencies.service.upsertEmbedding({
        tenant: request.tenant,
        user: request.user,
        requestId,
        entityId: body.entityId,
        text: body.text,
        embedding: body.embedding,
        metadata: body.metadata,
        modelVersion: body.modelVersion,
        chunkType: body.chunkType,
        provider: body.provider as EmbeddingProviderName | undefined
      });
    }
  );

  app.post(
    '/v1/embeddings/query',
    {
      schema: queryEmbeddingsSchema
    },
    async (request: FastifyRequest<{ Body: QueryEmbeddingRequest }>, reply: FastifyReply) => {
      if (!dependencies.service) {
        reply.status(503);
        return { error: 'Service initializing, please retry' };
      }

      if (!request.tenant) {
        throw badRequestError('Tenant context is required.');
      }

      const body = request.body ?? {};
      const requestId = request.requestContext.requestId;

      return dependencies.service.queryEmbeddings({
        tenant: request.tenant,
        user: request.user,
        requestId,
        query: body.query,
        embedding: body.embedding,
        limit: body.limit,
        similarityThreshold: body.similarityThreshold,
        filter: body.filter,
        provider: body.provider as EmbeddingProviderName | undefined
      });
    }
  );
}
