import type { FastifyPluginAsync, FastifyReply, FastifyRequest } from 'fastify';
import fp from 'fastify-plugin';

import { getConfig, type RateLimitConfig } from './config';
import { tooManyRequestsError } from './errors';
import { getLogger } from './logger';
import { getRedisClient } from './redis';

interface RouteLimitDefinition {
  bucket: string;
  limit: number;
}

interface RateLimitSnapshot {
  bucket: string;
  limit: number;
  remaining: number;
  reset: number;
}

const WINDOW_SECONDS = 1;

function resolveRoutePath(request: FastifyRequest): string {
  const withOptions = request as unknown as { routeOptions?: { url?: string } };
  const withRouterPath = request as unknown as { routerPath?: string };
  return withOptions.routeOptions?.url ?? withRouterPath.routerPath ?? request.url.split('?')[0];
}

function resolveRouteLimit(request: FastifyRequest, rateLimits: RateLimitConfig): RouteLimitDefinition | null {
  const routePath = resolveRoutePath(request);

  if (request.method === 'POST' && routePath === '/v1/search/hybrid') {
    return { bucket: 'hybrid', limit: rateLimits.hybridRps };
  }

  if (request.method === 'POST' && routePath === '/v1/search/rerank') {
    return { bucket: 'rerank', limit: rateLimits.rerankRps };
  }

  return null;
}

async function enforceLimit(
  client: any,
  tenantId: string,
  bucket: string,
  limit: number,
  burst: number,
  reply: FastifyReply
): Promise<RateLimitSnapshot | null> {
  if (limit <= 0) {
    return null;
  }

  const nowSeconds = Math.floor(Date.now() / 1000);
  const windowKey = Math.floor(nowSeconds / WINDOW_SECONDS);
  const redisKey = `ratelimit:${tenantId}:${bucket}:${windowKey}`;

  const current = await client.incr(redisKey);
  if (current === 1) {
    await client.expire(redisKey, WINDOW_SECONDS + 1);
  }

  const threshold = limit + burst;
  const reset = (windowKey + 1) * WINDOW_SECONDS;

  if (current > threshold) {
    const retryAfter = Math.max(reset - nowSeconds, 1);
    reply.header('Retry-After', retryAfter.toString());
    throw tooManyRequestsError('Tenant rate limit exceeded.');
  }

  const remaining = Math.max(limit - current, 0);
  return {
    bucket,
    limit,
    remaining,
    reset
  };
}

function applyHeaders(reply: FastifyReply, snapshot: RateLimitSnapshot | null): void {
  if (!snapshot) {
    return;
  }

  reply.header('ratelimit-limit', snapshot.limit.toString());
  reply.header('ratelimit-remaining', snapshot.remaining.toString());
  reply.header('ratelimit-reset', snapshot.reset.toString());
}

export const tenantRateLimitPlugin: FastifyPluginAsync = fp(async (fastify) => {
  const logger = getLogger({ module: 'rate-limit' });
  const config = getConfig();
  let redisClient: any | null = null;

  async function ensureRedis(): Promise<any> {
    if (redisClient && redisClient.isReady) {
      return redisClient;
    }

    redisClient = await getRedisClient();
    return redisClient;
  }

  fastify.addHook('preHandler', async (request, reply) => {
    if (request.url.startsWith('/health') || request.url.startsWith('/ready')) {
      return;
    }

    const tenantId = request.user?.orgId ?? request.tenant?.id;
    if (!tenantId) {
      return;
    }

    const client = await ensureRedis();
    const burst = config.rateLimits.tenantBurst;
    const routeLimit = resolveRouteLimit(request, config.rateLimits);
    let snapshot: RateLimitSnapshot | null = null;

    if (routeLimit && routeLimit.limit > 0) {
      try {
        snapshot = await enforceLimit(client, tenantId, routeLimit.bucket, routeLimit.limit, burst, reply);
      } catch (error) {
        logger.warn({ error, tenantId, bucket: routeLimit.bucket }, 'Route-specific rate limit exceeded.');
        throw error;
      }
    }

    if (config.rateLimits.globalRps > 0) {
      try {
        const globalSnapshot = await enforceLimit(client, tenantId, 'global', config.rateLimits.globalRps, burst, reply);
        if (!snapshot && globalSnapshot) {
          snapshot = globalSnapshot;
        }
      } catch (error) {
        logger.warn({ error, tenantId }, 'Global rate limit exceeded.');
        throw error;
      }
    }

    applyHeaders(reply, snapshot);
  });
});
