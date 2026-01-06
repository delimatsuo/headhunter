// Jest provides beforeEach, describe, expect, it as globals
import { MsgsRedisClient } from '../../src/redis-client';
import type { MsgsRedisConfig } from '../../src/config';

const clusterCalls: Array<{ nodes: unknown; options: unknown }> = [];

const redisMock = jest.fn().mockImplementation(() => ({
  on: jest.fn(),
  get: jest.fn().mockResolvedValue(null),
  setex: jest.fn()
}));

const clusterMock = jest.fn().mockImplementation((nodes: unknown, options: unknown) => {
  clusterCalls.push({ nodes, options });
  return {
    on: jest.fn(),
    get: jest.fn().mockResolvedValue(null),
    setex: jest.fn()
  };
});

jest.mock('ioredis', () => ({
  __esModule: true,
  default: redisMock,
  Cluster: clusterMock
}));

const loggerStub = {
  warn: jest.fn(),
  error: jest.fn(),
  info: jest.fn()
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
