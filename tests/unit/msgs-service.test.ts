import { describe, it, expect, beforeEach, vi } from 'vitest';
import type { Logger } from 'pino';

import type { MsgsServiceConfig } from '../../services/hh-msgs-svc/src/config';
import type { MsgsCloudSqlClient } from '../../services/hh-msgs-svc/src/cloudsql-client';
import type { MsgsRedisClient } from '../../services/hh-msgs-svc/src/redis-client';
import { MsgsService } from '../../services/hh-msgs-svc/src/msgs-service';

function buildBaseConfig(): MsgsServiceConfig {
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

function buildService(config: MsgsServiceConfig): MsgsService {
  const redis = {
    readSkillExpansion: async () => null,
    writeSkillExpansion: async () => {},
    readRoleTemplate: async () => null,
    writeRoleTemplate: async () => {},
    readDemand: async () => null,
    writeDemand: async () => {},
    healthCheck: async () => ({ status: 'disabled' as const }),
    close: async () => {}
  } as unknown as MsgsRedisClient;

  const db = {
    fetchSkillAdjacency: async () => [],
    fetchRoleTemplate: async () => null,
    fetchDemandSeries: async () => [],
    healthCheck: async () => ({ status: 'healthy' as const }),
    close: async () => {}
  } as unknown as MsgsCloudSqlClient;

  return new MsgsService({
    config,
    redisClient: redis,
    dbClient: db,
    logger: { info: () => {}, error: () => {}, warn: () => {}, child: () => ({}) } as unknown as Logger
  });
}

describe('MsgsService (seed data mode)', () => {
  let config: MsgsServiceConfig;
  let service: MsgsService;

  beforeEach(() => {
    config = buildBaseConfig();
    config.runtime.useSeedData = true;
    service = buildService(config);
  });

  it('expands known skills using seed adjacency', async () => {
    const response = await service.expandSkills('tenant-1', { skillId: 'javascript', topK: 3 });

    expect(response.seedSkill.skillId).toBe('javascript');
    expect(response.adjacent.length).toBeGreaterThan(0);
    expect(response.meta.algorithm).toBe('pmi-seed');
  });

  it('returns seeded role template', async () => {
    const response = await service.getRoleTemplate('tenant-1', { ecoId: 'frontend-developer' });

    expect(response).not.toBeNull();
    expect(response?.requiredSkills.map((skill) => skill.skillId)).toContain('javascript');
  });

  it('provides seeded market demand series', async () => {
    const response = await service.getMarketDemand('tenant-1', { skillId: 'javascript', region: 'BR-SP' });

    expect(response).not.toBeNull();
    expect(response?.points.length).toBeGreaterThan(0);
    expect(['rising', 'steady', 'declining']).toContain(response?.trend);
  });
});

describe('MsgsService (Cloud SQL mode)', () => {
  it('computes PMI-adjusted adjacency from Cloud SQL rows', async () => {
    const config = buildBaseConfig();
    config.runtime.useSeedData = false;
    config.redis.disable = true;

    const redis = {
      readSkillExpansion: async () => null,
      writeSkillExpansion: async () => {},
      healthCheck: async () => ({ status: 'disabled' as const }),
      close: async () => {}
    } as unknown as MsgsRedisClient;

    const fetchDemandSeries = vi.fn().mockResolvedValue([
      { week_start: '2024-01-01', postings_count: 100, demand_index: 1.2 },
      { week_start: '2024-01-08', postings_count: 120, demand_index: 1.3 }
    ]);

    const db = {
      fetchSkillAdjacency: vi.fn().mockResolvedValue([
        {
          related_skill_id: 'typescript',
          related_skill_label: 'TypeScript',
          score: 0,
          support: 25,
          recency_days: 7,
          sources: ['job_postings']
        }
      ]),
      fetchRoleTemplate: vi.fn().mockResolvedValue({
        eco_id: 'frontend-developer',
        locale: 'pt-BR',
        title: 'Frontend Dev',
        summary: 'Build UI',
        required_skills: [
          { skill_id: 'javascript', label: 'JavaScript', importance: 0.9 },
          { skill_id: 'typescript', label: 'TypeScript', importance: 0.8 }
        ],
        preferred_skills: [
          { skill_id: 'react', label: 'React', importance: 0.7 }
        ],
        yoe_min: 2,
        yoe_max: 5,
        version: '2024.1'
      }),
      fetchDemandSeries,
      healthCheck: vi.fn().mockResolvedValue({ status: 'healthy' as const }),
      close: vi.fn()
    } as unknown as MsgsCloudSqlClient;

    const service = new MsgsService({
      config,
      redisClient: redis,
      dbClient: db
    });

    const result = await service.expandSkills('tenant-1', { skillId: 'javascript', topK: 5 });
    expect(result.adjacent[0]?.skillId).toBe('typescript');
    expect(result.meta.algorithm).toBe('pmi-cloudsql');

    const template = await service.getRoleTemplate('tenant-1', { ecoId: 'frontend-developer', locale: 'pt-BR' });
    expect(template?.requiredSkills.length).toBe(2);

    const demand = await service.getMarketDemand('tenant-1', { skillId: 'javascript', region: 'BR-SP' });
    expect(demand?.points.length).toBeGreaterThan(0);

    const enriched = await service.getRoleTemplate('tenant-1', {
      ecoId: 'frontend-developer',
      locale: 'pt-BR',
      includeDemand: true
    });

    expect(fetchDemandSeries).toHaveBeenCalled();
    expect(enriched?.demandIndex).toBeDefined();
    expect(typeof enriched?.demandIndex).toBe('number');
  });
});
