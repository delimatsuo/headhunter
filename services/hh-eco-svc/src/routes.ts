import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';
import { badRequestError, getLogger, notFoundError } from '@hh/common';

import type { EcoServiceConfig } from './config.js';
import { EcoFirestoreClient } from './firestore-client.js';
import { EcoRedisClient } from './redis-client.js';
import { occupationDetailSchema, occupationSearchSchema } from './schemas.js';
import type {
  OccupationDetailParams,
  OccupationDetailQuerystring,
  OccupationSearchQuerystring,
  OccupationSearchResponse
} from './types.js';
import { EcoService } from './eco-service.js';

interface RegisterEcoRoutesOptions {
  service: EcoService | null;
  config: EcoServiceConfig;
  redisClient: EcoRedisClient | null;
  firestoreClient: EcoFirestoreClient | null;
  state: { isReady: boolean };
}

export async function registerRoutes(
  app: FastifyInstance,
  dependencies: RegisterEcoRoutesOptions
): Promise<void> {
  const logger = getLogger({ module: 'eco-routes' });

  const readinessHandler = async (_request: FastifyRequest, reply: FastifyReply) => {
    // If not ready, dependencies are still null - return initializing
    if (!dependencies.state.isReady) {
      reply.status(503);
      return {
        status: 'initializing',
        service: 'hh-eco-svc'
      };
    }

    if (!dependencies.redisClient || !dependencies.firestoreClient) {
      reply.status(503);
      return {
        status: 'initializing',
        service: 'hh-eco-svc'
      };
    }

    const [redisHealth, firestoreHealth] = await Promise.all([
      dependencies.redisClient.healthCheck(),
      dependencies.firestoreClient.healthCheck()
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
  };

  app.get('/healthz', readinessHandler);
  app.get('/readyz', readinessHandler);
  app.get('/health', readinessHandler);
  app.get('/health/detailed', readinessHandler);

  app.get(
    '/v1/occupations/search',
    { schema: occupationSearchSchema },
    async (request: FastifyRequest<{ Querystring: OccupationSearchQuerystring }>, reply: FastifyReply) => {
      if (!request.tenant) {
        throw badRequestError('Tenant context is required.');
      }

      if (!dependencies.service) {
        reply.status(503);
        return { error: 'Service initializing' };
      }

      const { title, locale, country, limit, useCache } = request.query;
      if (!title || title.trim().length === 0) {
        throw badRequestError('Title is required.');
      }

      const parsedLimit = typeof limit === 'string' ? Number(limit) : limit;
      const bypassCache = useCache === 'false';

      const response = await dependencies.service.search(
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
      request: FastifyRequest<{ Params: OccupationDetailParams; Querystring: OccupationDetailQuerystring }>,
      reply: FastifyReply
    ) => {
      if (!request.tenant) {
        throw badRequestError('Tenant context is required.');
      }

      if (!dependencies.service) {
        reply.status(503);
        return { error: 'Service initializing' };
      }

      const { ecoId } = request.params;
      const { locale, country } = request.query;

      try {
        const response = await dependencies.service.detail(
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
