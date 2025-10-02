import Fastify from 'fastify';
import fp from 'fastify-plugin';

import { tenantRateLimitPlugin } from '../rate_limit';
import { resetConfigForTesting } from '../config';

const redisStore = new Map<string, number>();

jest.mock('../redis', () => ({
  getRedisClient: jest.fn(async () => ({
    isOpen: true,
    async incr(key: string) {
      const next = (redisStore.get(key) ?? 0) + 1;
      redisStore.set(key, next);
      return next;
    },
    async expire() {
      return true;
    }
  }))
}));

describe('tenantRateLimitPlugin', () => {
  beforeEach(() => {
    process.env.FIREBASE_PROJECT_ID = 'test-project';
    process.env.GATEWAY_HYBRID_RPS = '1';
    process.env.GATEWAY_GLOBAL_RPS = '5';
    process.env.GATEWAY_TENANT_BURST = '0';
    resetConfigForTesting();
    redisStore.clear();
  });

  afterEach(() => {
    resetConfigForTesting();
    delete process.env.FIREBASE_PROJECT_ID;
    delete process.env.GATEWAY_HYBRID_RPS;
    delete process.env.GATEWAY_GLOBAL_RPS;
    delete process.env.GATEWAY_TENANT_BURST;
    redisStore.clear();
  });

  function buildApp() {
    const app = Fastify();
    app.register(fp(async (instance) => {
      instance.decorateRequest('user', null);
      instance.addHook('onRequest', async (request) => {
        request.user = {
          uid: 'user-1',
          orgId: 'tenant-1',
          claims: {}
        } as any;
      });
    }));
    app.register(tenantRateLimitPlugin);
    app.post('/v1/search/hybrid', () => ({ status: 'ok' }));
    return app;
  }

  it('enforces per-route limits', async () => {
    const app = buildApp();

    const first = await app.inject({
      method: 'POST',
      url: '/v1/search/hybrid',
      headers: {
        'x-tenant-id': 'tenant-1'
      }
    });
    expect(first.statusCode).toBe(200);
    expect(first.headers['ratelimit-limit']).toBe('1');

    const second = await app.inject({
      method: 'POST',
      url: '/v1/search/hybrid',
      headers: {
        'x-tenant-id': 'tenant-1'
      }
    });
    expect(second.statusCode).toBe(429);

    await app.close();
  });

  it('falls back to global limits for untagged routes', async () => {
    process.env.GATEWAY_GLOBAL_RPS = '1';
    resetConfigForTesting();
    redisStore.clear();

    const app = Fastify();
    app.register(fp(async (instance) => {
      instance.decorateRequest('user', null);
      instance.addHook('onRequest', async (request) => {
        request.user = {
          uid: 'user-1',
          orgId: 'tenant-2',
          claims: {}
        } as any;
      });
    }));
    app.register(tenantRateLimitPlugin);
    app.get('/v1/occupations', () => ({ status: 'ok' }));

    const first = await app.inject({
      method: 'GET',
      url: '/v1/occupations',
      headers: {
        'x-tenant-id': 'tenant-2'
      }
    });
    expect(first.statusCode).toBe(200);

    const second = await app.inject({
      method: 'GET',
      url: '/v1/occupations',
      headers: {
        'x-tenant-id': 'tenant-2'
      }
    });
    expect(second.statusCode).toBe(429);

    await app.close();
  });
});
