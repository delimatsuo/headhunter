import fastify from 'fastify';
import { describe, it, expect, beforeAll, afterAll } from '@jest/globals';

import type { MsgsServiceConfig } from '../../services/hh-msgs-svc/src/config';
import type { MsgsCloudSqlClient } from '../../services/hh-msgs-svc/src/cloudsql-client';
import type { MsgsRedisClient } from '../../services/hh-msgs-svc/src/redis-client';
import { MsgsService } from '../../services/hh-msgs-svc/src/msgs-service';
import { registerRoutes } from '../../services/hh-msgs-svc/src/routes';

function buildConfig(): MsgsServiceConfig {
  return {
    base: {
      firestore: { projectId: 'test', emulatorHost: 'localhost:8080' },
      redis: { host: 'localhost', port: 6379, password: undefined },
      auth: {
        serviceAccountPath: undefined,
        checkRevoked: false,
        allowedIssuers: [],
        issuerConfigs: [],
        gatewayAudiences: [],
        gatewayProjectId: undefined,
        enableGatewayTokens: false,
        tokenClockSkewSeconds: 30,
        tokenCacheTtlSeconds: 60,
        mode: 'firebase',
        tokenCacheEnabled: false
      },
      runtime: {
        serviceName: 'hh-msgs-svc',
        logLevel: 'info',
        enableRequestLogging: false,
        cacheTtlSeconds: 60
      },
      rateLimits: {
        hybridRps: 10,
        rerankRps: 5,
        globalRps: 20,
        tenantBurst: 10
      },
      monitoring: {
        traceHeader: 'x-trace',
        propagateTrace: false,
        requestIdHeader: 'x-request-id',
        logClientMetadata: false
      }
    },
    redis: {
      url: 'redis://localhost:6379',
      tls: false,
      keyPrefix: 'hh:msgs',
      skillTtlSeconds: 60,
      roleTtlSeconds: 120,
      demandTtlSeconds: 90,
      disable: true
    },
    database: {
      host: '127.0.0.1',
      port: 5432,
      user: 'test',
      password: '',
      database: 'test',
      ssl: false,
      connectTimeoutMs: 1000,
      idleTimeoutMs: 1000,
      maxPoolSize: 2,
      minPoolSize: 0
    },
    calculations: {
      pmiMinScore: 0.1,
      pmiDecayDays: 30,
      pmiMinSupport: 1,
      emaSpan: 6,
      emaMinPoints: 4,
      emaZScoreWindow: 12
    },
    runtime: {
      useSeedData: true,
      templateDefaultLocale: 'pt-BR',
      templateVersion: 'test'
    }
  } satisfies MsgsServiceConfig;
}

describe('MSGS HTTP routes', () => {
  const config = buildConfig();

  const redisClient = {
    healthCheck: async () => ({ status: 'disabled' as const, message: 'disabled for tests' })
  } as unknown as MsgsRedisClient;

  const cloudSqlClient = {
    healthCheck: async () => ({ status: 'healthy' as const, latencyMs: 1 }),
    close: async () => {}
  } as unknown as MsgsCloudSqlClient;

  const service = new MsgsService({
    config,
    redisClient: {
      ...redisClient,
      readSkillExpansion: async () => null,
      writeSkillExpansion: async () => {},
      readRoleTemplate: async () => null,
      writeRoleTemplate: async () => {},
      readDemand: async () => null,
      writeDemand: async () => {},
      close: async () => {}
    } as unknown as MsgsRedisClient,
    dbClient: {
      ...cloudSqlClient,
      fetchSkillAdjacency: async () => [],
      fetchRoleTemplate: async () => null,
      fetchDemandSeries: async () => []
    } as unknown as MsgsCloudSqlClient
  });

  const app = fastify({ logger: false });

  beforeAll(async () => {
    app.addHook('preHandler', async (request) => {
      (request as any).tenant = { id: 'tenant-1' };
      (request as any).requestContext = { requestId: 'integration-test' };
    });

    await registerRoutes(app, {
      service,
      config,
      redisClient: redisClient,
      cloudSqlClient
    });

    await app.ready();
  });

  afterAll(async () => {
    await app.close();
  });

  it('returns skill expansion response', async () => {
    const response = await app.inject({
      method: 'POST',
      url: '/v1/skills/expand',
      payload: { skillId: 'javascript' }
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.seedSkill.skillId).toBe('javascript');
  });

  it('returns role template response', async () => {
    const response = await app.inject({
      method: 'POST',
      url: '/v1/roles/template',
      payload: { ecoId: 'frontend-developer' }
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.ecoId).toBe('frontend-developer');
  });

  it('returns market demand analytics', async () => {
    const response = await app.inject({
      method: 'GET',
      url: '/v1/market/demand?skillId=javascript&region=BR-SP'
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.skillId).toBe('javascript');
  });
});
