import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';
import { badRequestError, getLogger, notFoundError } from '@hh/common';

import type { EvidenceServiceConfig } from './config';
import { EvidenceFirestoreClient } from './firestore-client';
import { EvidenceRedisClient } from './redis-client';
import { evidenceRouteSchema } from './schemas';
import type { EvidenceQuerystring, EvidenceRequestParams, EvidenceResponse, EvidenceSectionKey } from './types';
import { EvidenceService } from './evidence-service';

interface RegisterRoutesOptions {
  service: EvidenceService | null;
  config: EvidenceServiceConfig;
  redisClient: EvidenceRedisClient | null;
  firestoreClient: EvidenceFirestoreClient | null;
  state: { isReady: boolean };
}

export async function registerRoutes(
  app: FastifyInstance,
  dependencies: RegisterRoutesOptions
): Promise<void> {
  const logger = getLogger({ module: 'evidence-routes' });

  const readinessHandler = async (_request: FastifyRequest, reply: FastifyReply) => {
    // If not ready, dependencies are still null - return initializing
    if (!dependencies.state.isReady) {
      reply.status(503);
      return {
        status: 'initializing',
        service: 'hh-evidence-svc'
      };
    }

    if (!dependencies.redisClient || !dependencies.firestoreClient) {
      reply.status(503);
      return {
        status: 'initializing',
        service: 'hh-evidence-svc'
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
    '/v1/evidence/:candidateId',
    { schema: evidenceRouteSchema },
    async (
      request: FastifyRequest<{ Params: EvidenceRequestParams; Querystring: EvidenceQuerystring }>,
      reply: FastifyReply
    ) => {
      if (!request.tenant) {
        throw badRequestError('Tenant context is required.');
      }

      if (!dependencies.service) {
        reply.status(503);
        return { error: 'Service initializing' };
      }

      const { candidateId } = request.params;
      const rawSections = request.query.sections;
      const includeSections = rawSections
        ? rawSections
            .split(',')
            .map((value) => value.trim())
            .filter((value): value is EvidenceSectionKey => value.length > 0)
        : undefined;

      if (includeSections && includeSections.length > 0) {
        const invalid = includeSections.filter((value) => !dependencies.config.runtime.allowedSections.includes(value));
        if (invalid.length > 0) {
          throw badRequestError(`Unknown evidence sections requested: ${invalid.join(', ')}`);
        }
      }

      try {
        const response = await dependencies.service.getEvidence({
          candidateId,
          includeSections,
          tenant: request.tenant
        });

        logger.info(
          {
            tenantId: request.tenant.id,
            candidateId,
            cacheHit: response.metadata.cacheHit,
            requestId: request.requestContext.requestId,
            sections: response.metadata.sectionsAvailable
          },
          'Returning candidate evidence.'
        );

        return response satisfies EvidenceResponse;
      } catch (error) {
        if (error instanceof Error && error.message.includes('not found')) {
          throw notFoundError('Candidate evidence not found.');
        }
        logger.error(
          { error, tenantId: request.tenant.id, candidateId },
          'Failed to retrieve candidate evidence.'
        );
        throw error;
      }
    }
  );
}
