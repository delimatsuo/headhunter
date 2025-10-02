import Fastify from 'fastify';
import fp from 'fastify-plugin';

import { tenantValidationPlugin, clearTenantCache } from '../tenant';
import { resetConfigForTesting } from '../config';

const tenants: Record<string, Record<string, unknown>> = {};

jest.mock('../firestore', () => ({
  getFirestore: () => ({
    collection: () => ({
      doc: (id: string) => ({
        async get() {
          const record = tenants[id];
          if (!record) {
            return { exists: false };
          }

          return {
            exists: true,
            data: () => record
          };
        }
      })
    })
  })
}));

describe('tenantValidationPlugin', () => {
  beforeEach(() => {
    process.env.FIREBASE_PROJECT_ID = 'test-project';
    resetConfigForTesting();
    clearTenantCache();
    for (const key of Object.keys(tenants)) {
      delete tenants[key];
    }
  });

  afterEach(() => {
    resetConfigForTesting();
    clearTenantCache();
    delete process.env.FIREBASE_PROJECT_ID;
  });

  function buildApp(userOrgId = 'tenant-1') {
    const app = Fastify();

    app.register(fp(async (instance) => {
      instance.decorateRequest('user', null);
      instance.addHook('onRequest', async (request) => {
        request.user = {
          uid: 'user-1',
          orgId: userOrgId,
          claims: {}
        } as any;
      });
    }));

    app.register(tenantValidationPlugin);

    app.get('/resource', (request) => ({
      tenant: request.tenant?.id
    }));

    return app;
  }

  it('returns 400 when X-Tenant-ID header is missing', async () => {
    const app = buildApp();
    const response = await app.inject({ method: 'GET', url: '/resource' });
    expect(response.statusCode).toBe(400);
    await app.close();
  });

  it('returns 403 when tenant header does not match user organization', async () => {
    const app = buildApp('tenant-1');
    const response = await app.inject({
      method: 'GET',
      url: '/resource',
      headers: {
        'x-tenant-id': 'tenant-2'
      }
    });

    expect(response.statusCode).toBe(403);
    await app.close();
  });

  it('returns 404 when tenant is inactive', async () => {
    tenants['tenant-1'] = {
      name: 'Tenant 1',
      status: 'inactive'
    };

    const app = buildApp('tenant-1');
    const response = await app.inject({
      method: 'GET',
      url: '/resource',
      headers: {
        'x-tenant-id': 'tenant-1'
      }
    });

    expect(response.statusCode).toBe(404);
    await app.close();
  });

  it('attaches tenant context for active tenants', async () => {
    tenants['tenant-1'] = {
      name: 'Tenant 1',
      status: 'active'
    };

    const app = buildApp('tenant-1');
    const response = await app.inject({
      method: 'GET',
      url: '/resource',
      headers: {
        'x-tenant-id': 'tenant-1'
      }
    });

    expect(response.statusCode).toBe(200);
    const payload = JSON.parse(response.payload) as { tenant: string };
    expect(payload.tenant).toBe('tenant-1');
    await app.close();
  });
});
