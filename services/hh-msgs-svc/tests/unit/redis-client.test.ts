import { beforeEach, describe, expect, it, vi } from 'vitest';

import { MsgsRedisClient } from '../../src/redis-client';
import type { MsgsRedisConfig } from '../../src/config';

const clusterCalls: Array<{ nodes: unknown; options: unknown }> = [];

const redisMock = vi.fn().mockImplementation(() => ({
  on: vi.fn(),
  get: vi.fn().mockResolvedValue(null),
  setex: vi.fn()
}));

const clusterMock = vi.fn().mockImplementation((nodes, options) => {
  clusterCalls.push({ nodes, options });
  return {
    on: vi.fn(),
    get: vi.fn().mockResolvedValue(null),
    setex: vi.fn()
  };
});

vi.mock('ioredis', () => ({
  __esModule: true,
  default: redisMock,
  Cluster: clusterMock
}));

const loggerStub = {
  warn: vi.fn(),
  error: vi.fn(),
  info: vi.fn()
};

function buildConfig(url: string): MsgsRedisConfig {
  return {
    url,
    tls: false,
    keyPrefix: 'hh:msgs',
    skillTtlSeconds: 60,
    roleTtlSeconds: 120,
    demandTtlSeconds: 90,
    disable: false
  } satisfies MsgsRedisConfig;
}

describe('MsgsRedisClient cluster auth', () => {
  beforeEach(() => {
    clusterCalls.length = 0;
    redisMock.mockClear();
    clusterMock.mockClear();
  });

  it('propagates credentials from cluster URLs into redisOptions', async () => {
    const config = buildConfig('redis://user-one:pass-one@localhost:6379,redis://user-one:pass-one@localhost:6380');
    const client = new MsgsRedisClient(config, loggerStub as any);

    await client.readSkillExpansion('tenant-1', 'skill-1', 'fingerprint');

    expect(clusterMock).toHaveBeenCalledTimes(1);
    const [{ options }] = clusterCalls;
    expect(options).toBeDefined();
    const redisOptions = (options as { redisOptions: Record<string, unknown> }).redisOptions;
    expect(redisOptions).toMatchObject({
      username: 'user-one',
      password: 'pass-one',
      keyPrefix: 'hh:msgs:'
    });
  });
});
