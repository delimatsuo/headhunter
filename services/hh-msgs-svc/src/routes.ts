import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';

import { badRequestError, getLogger, notFoundError } from '@hh/common';

import type { MsgsServiceConfig } from './config';
import { MsgsCloudSqlClient } from './cloudsql-client';
import { MsgsRedisClient } from './redis-client';
import { marketDemandSchema, msgsHealthSchema, roleTemplateSchema, skillExpandSchema } from './schemas';
import type {
  MarketDemandQuerystring,
  RoleTemplateRequestBody,
  SkillExpandRequestBody
} from './types';
import { MsgsService } from './msgs-service';

interface RegisterMsgsRoutesOptions {
  service: MsgsService;
  config: MsgsServiceConfig;
  redisClient: MsgsRedisClient;
  cloudSqlClient: MsgsCloudSqlClient;
}

export async function registerRoutes(
  app: FastifyInstance,
  { service, config, redisClient, cloudSqlClient }: RegisterMsgsRoutesOptions
): Promise<void> {
  const logger = getLogger({ module: 'msgs-routes' });

    // Detailed health endpoint (basic /health is registered in index.ts before listen())
  app.get(
    '/health/detailed',
    { schema: msgsHealthSchema },
    async (_request: FastifyRequest, reply: FastifyReply) => {
      const [redis, cloudSql] = await Promise.all([
        redisClient.healthCheck(),
        cloudSqlClient.healthCheck()
      ]);

      const degraded: Record<string, unknown> = {};
      const usingSeedData = config.runtime.useSeedData;

      if (!['healthy', 'disabled'].includes(redis.status)) {
        degraded.redis = redis;
      }

      if (cloudSql.status !== 'healthy' && !usingSeedData) {
        degraded.cloudSql = cloudSql;
      }

      const responsePayload: Record<string, unknown> = {
        status: 'ok',
        redis,
        cloudSql,
        mode: usingSeedData ? 'seed' : 'cloudsql'
      } satisfies Record<string, unknown>;

      if (Object.keys(degraded).length > 0) {
        responsePayload.status = 'degraded';
        responsePayload.degraded = degraded;
        reply.code(503);
        return responsePayload;
      }

      return responsePayload;
    }
  );

  app.post(
    '/v1/skills/expand',
    { schema: skillExpandSchema },
    async (
      request: FastifyRequest<{ Body: SkillExpandRequestBody }>,
      reply: FastifyReply
    ) => {
      if (!request.tenant) {
        throw badRequestError('Tenant context is required.');
      }

      const { skillId } = request.body;
      if (!skillId || skillId.trim().length === 0) {
        throw badRequestError('skillId is required.');
      }

      const response = await service.expandSkills(request.tenant.id, request.body);

      logger.info(
        {
          tenantId: request.tenant.id,
          skillId,
          cacheHit: response.cacheHit,
          requestId: request.requestContext.requestId
        },
        'Skill expansion request served.'
      );

      reply.send(response);
    }
  );

  app.post(
    '/v1/roles/template',
    { schema: roleTemplateSchema },
    async (
      request: FastifyRequest<{ Body: RoleTemplateRequestBody }>,
      reply: FastifyReply
    ) => {
      if (!request.tenant) {
        throw badRequestError('Tenant context is required.');
      }

      const response = await service.getRoleTemplate(request.tenant.id, request.body);
      if (!response) {
        throw notFoundError('Role template not found.');
      }

      logger.info(
        {
          tenantId: request.tenant.id,
          ecoId: request.body.ecoId,
          cacheHit: response.cacheHit,
          requestId: request.requestContext.requestId
        },
        'Role template request served.'
      );

      reply.send(response);
    }
  );

  app.get(
    '/v1/market/demand',
    { schema: marketDemandSchema },
    async (
      request: FastifyRequest<{ Querystring: MarketDemandQuerystring }>,
      reply: FastifyReply
    ) => {
      if (!request.tenant) {
        throw badRequestError('Tenant context is required.');
      }

      const { skillId } = request.query;
      if (!skillId || skillId.trim().length === 0) {
        throw badRequestError('skillId query parameter is required.');
      }

      const response = await service.getMarketDemand(request.tenant.id, request.query);
      if (!response) {
        throw notFoundError('Demand analytics not found.');
      }

      logger.info(
        {
          tenantId: request.tenant.id,
          skillId,
          cacheHit: response.cacheHit,
          requestId: request.requestContext.requestId
        },
        'Market demand request served.'
      );

      reply.send(response);
    }
  );
}
