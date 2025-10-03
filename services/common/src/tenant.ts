import type { FastifyPluginAsync } from 'fastify';
import fp from 'fastify-plugin';
import { LRUCache } from 'lru-cache';

import { getConfig } from './config';
import { badRequestError, forbiddenError, notFoundError } from './errors';
import { getFirestore } from './firestore';
import { getLogger } from './logger';
import type { TenantContext } from './types';

interface TenantRecord {
  id: string;
  name?: string;
  isActive: boolean;
  [key: string]: unknown;
}

let cache: LRUCache<string, TenantContext> | null = null;

function getTenantCache(): LRUCache<string, TenantContext> {
  if (!cache) {
    const config = getConfig();
    cache = new LRUCache<string, TenantContext>({
      max: 1000,
      ttl: config.runtime.cacheTtlSeconds * 1000
    });
  }

  return cache;
}

const logger = getLogger({ module: 'tenant' });

async function fetchTenant(tenantId: string): Promise<TenantContext> {
  const tenantCache = getTenantCache();
  const cached = tenantCache.get(tenantId);
  if (cached) {
    return cached;
  }

  const doc = await getFirestore().collection('organizations').doc(tenantId).get();
  if (!doc.exists) {
    throw notFoundError('Tenant not found.');
  }

  const data = doc.data() as TenantRecord | undefined;
  if (!data) {
    throw notFoundError('Tenant document is empty.');
  }

  const status = typeof data.status === 'string' ? data.status.toLowerCase() : undefined;
  const isActive = status ? status === 'active' : data.isActive !== false;

  const tenant: TenantContext = {
    id: doc.id,
    name: typeof data.name === 'string' ? data.name : undefined,
    isActive,
    rawRecord: data
  };

  tenantCache.set(tenantId, tenant);
  return tenant;
}

export const tenantValidationPlugin: FastifyPluginAsync = fp(async (fastify) => {
  fastify.addHook('preHandler', async (request) => {
    if (request.url.startsWith('/health') || request.url.startsWith('/ready')) {
      return;
    }

    const tenantHeader = request.headers['x-tenant-id'];
    const tenantId = typeof tenantHeader === 'string' ? tenantHeader.trim() : '';
    if (tenantId.length === 0) {
      throw badRequestError('Missing X-Tenant-ID header.');
    }

    // For gateway tokens (no orgId), trust X-Tenant-ID header since API Gateway validated it
    // For Firebase tokens, validate orgId matches X-Tenant-ID header
    if (request.user?.orgId) {
      if (tenantId !== request.user.orgId) {
        throw forbiddenError('Tenant header does not match authenticated user organization.');
      }
    } else {
      // Gateway token without orgId claim - verify it came through auth plugin successfully
      if (!request.user) {
        logger.warn('Missing user context in request with tenant header.');
        throw forbiddenError('Authentication required for tenant context.');
      }
    }

    const tenant = await fetchTenant(tenantId);

    if (!tenant.isActive) {
      throw notFoundError('Tenant is not active.');
    }

    request.tenant = tenant;
    request.requestContext = request.requestContext ?? { requestId: request.id };
    request.requestContext.tenant = tenant;
  });
});

export function clearTenantCache(): void {
  if (cache) {
    cache.clear();
    cache = null;
  }
}
