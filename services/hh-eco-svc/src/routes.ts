import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';
import { badRequestError, getLogger, notFoundError } from '@hh/common';

import type { EcoServiceConfig } from './config.js';
import { EcoFirestoreClient } from './firestore-client.js';
import { EcoRedisClient } from './redis-client.js';
import { ecoHealthSchema, occupationDetailSchema, occupationSearchSchema } from './schemas.js';
import type {
  OccupationDetailParams,
  OccupationDetailQuerystring,
  OccupationSearchQuerystring,
  OccupationSearchResponse
} from './types.js';
import { EcoService } from './eco-service.js';

interface RegisterEcoRoutesOptions {
  service: EcoService;
  config: EcoServiceConfig;
  redisClient: EcoRedisClient;
  firestoreClient: EcoFirestoreClient;
}

export async function registerRoutes(
  app: FastifyInstance,
  { service, config: _config, redisClient, firestoreClient }: RegisterEcoRoutesOptions
): Promise<void> {
  const logger = getLogger({ module: 'eco-routes' });

  // Detailed health endpoint (basic /health is registered in index.ts before listen())
  app.get(
    '/health/detailed',
    { schema: ecoHealthSchema },
    async (_request: FastifyRequest, reply: FastifyReply) => {
      const [redisHealth, firestoreHealth] = await Promise.all([
        redisClient.healthCheck(),
        firestoreClient.healthCheck()
      ]);

      const degraded: Record<string, unknown> = {};
      if (!['healthy', 'disabled'].includes(redisHealth.status)) {
        degraded.redis = redisHealth;
      }
      if (firestoreHealth.status !== 'healthy') {
        degraded.firestore = firestoreHealth;
      }

      if (Object.keys(degraded).length > 0) {
        reply.code(503);
        return {
          status: 'degraded',
          ...degraded
        } satisfies Record<string, unknown>;
      }

      return {
        status: 'ok',
        redis: redisHealth,
        firestore: firestoreHealth
      } satisfies Record<string, unknown>;
    }
  );

  app.get(
    '/v1/occupations/search',
    { schema: occupationSearchSchema },
    async (request: FastifyRequest<{ Querystring: OccupationSearchQuerystring }>) => {
      if (!request.tenant) {
        throw badRequestError('Tenant context is required.');
      }

      const { title, locale, country, limit, useCache } = request.query;
      if (!title || title.trim().length === 0) {
        throw badRequestError('Title is required.');
      }

      const parsedLimit = typeof limit === 'string' ? Number(limit) : limit;
      const bypassCache = useCache === 'false';

      const response = await service.search(
        request.tenant.id,
        {
          title,
          locale,
          country,
          limit: Number.isFinite(parsedLimit as number) ? (parsedLimit as number) : undefined
        },
        { bypassCache }
      );

      logger.info(
        {
          tenantId: request.tenant.id,
          cacheHit: response.cacheHit,
          total: response.total,
          requestId: request.requestContext.requestId
        },
        'ECO search request completed.'
      );

      return response satisfies OccupationSearchResponse;
    }
  );

  app.get(
    '/v1/occupations/:ecoId',
    { schema: occupationDetailSchema },
    async (
      request: FastifyRequest<{ Params: OccupationDetailParams; Querystring: OccupationDetailQuerystring }>
    ) => {
      if (!request.tenant) {
        throw badRequestError('Tenant context is required.');
      }

      const { ecoId } = request.params;
      const { locale, country } = request.query;

      try {
        const response = await service.detail(
          request.tenant.id,
          ecoId,
          {
            locale,
            country,
            bypassCache: false
          }
        );

        logger.info(
          {
            tenantId: request.tenant.id,
            ecoId,
            cacheHit: response.cacheHit,
            requestId: request.requestContext.requestId
          },
          'ECO detail request completed.'
        );

        return response;
      } catch (error) {
        if (error instanceof Error && error.message.includes('not found')) {
          throw notFoundError('Occupation not found.');
        }
        logger.error({ error, tenantId: request.tenant.id, ecoId }, 'Failed to resolve ECO detail.');
        throw error;
      }
    }
  );
}
