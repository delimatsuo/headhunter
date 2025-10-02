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
  service: EmbeddingsService;
  config: EmbeddingsServiceConfig;
  pgClient: PgVectorClient;
}

export async function registerRoutes(app: FastifyInstance, { service, pgClient }: RegisterRoutesOptions): Promise<void> {
  // Detailed health endpoint (basic /health is registered in index.ts before listen())
  app.get('/health/detailed', async (_request, reply: FastifyReply) => {
    const health = await pgClient.healthCheck();
    if (health.status !== 'healthy') {
      reply.status(503);
      return {
        status: health.status,
        message: health.message ?? 'Database connection degraded.',
        poolSize: health.poolSize
      };
    }

    return { status: 'ok' };
  });

  app.post(
    '/v1/embeddings/generate',
    {
      schema: generateEmbeddingSchema
    },
    async (request: FastifyRequest<{ Body: GenerateEmbeddingRequest }>) => {
      if (!request.tenant) {
        throw badRequestError('Tenant context is required.');
      }

      const body = request.body;
      const requestId = request.requestContext.requestId;

      return service.generateEmbedding({
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
    async (request: FastifyRequest<{ Body: UpsertEmbeddingRequest }>) => {
      if (!request.tenant) {
        throw badRequestError('Tenant context is required.');
      }

      const body = request.body;
      const requestId = request.requestContext.requestId;

      return service.upsertEmbedding({
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
    async (request: FastifyRequest<{ Body: QueryEmbeddingRequest }>) => {
      if (!request.tenant) {
        throw badRequestError('Tenant context is required.');
      }

      const body = request.body ?? {};
      const requestId = request.requestContext.requestId;

      return service.queryEmbeddings({
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
