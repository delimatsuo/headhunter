import Fastify from 'fastify';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { authenticationPlugin, resetAuthForTesting } from '../../services/common/src/auth';
import { clearTenantCache, tenantValidationPlugin } from '../../services/common/src/tenant';

const baseConfig = {
  firestore: { projectId: 'test-project' },
  auth: {
    mode: 'hybrid',
    enableGatewayTokens: true,
    issuerConfigs: [
      { issuer: 'https://issuer.example.com', jwksUri: 'https://issuer.example.com/jwks' }
    ],
    gatewayAudiences: ['headhunter'],
    allowedIssuers: ['https://issuer.example.com', 'https://securetoken.google.com/test-project'],
    tokenCacheEnabled: false,
    tokenCacheTtlSeconds: 60,
    tokenClockSkewSeconds: 30,
    checkRevoked: false
  },
  runtime: {
    cacheTtlSeconds: 10
  }
};

interface TenantRecord {
  status?: string;
  isActive?: boolean;
  name?: string;
}

const configRef: { value: typeof baseConfig } = { value: JSON.parse(JSON.stringify(baseConfig)) };
const firebaseVerifyMock = vi.fn();
const jwtVerifyMock = vi.fn();
const loggerWarnMock = vi.hoisted(() => vi.fn());

(globalThis as unknown as Record<string, unknown>).__firebaseVerifyMock = firebaseVerifyMock;
(globalThis as unknown as Record<string, unknown>).__jwtVerifyMock = jwtVerifyMock;
const tenantStore = new Map<string, TenantRecord>();

vi.mock('../../services/common/src/config', () => ({
  getConfig: () => configRef.value
}));

vi.mock('firebase-admin/app', () => ({
  getApps: () => [],
  initializeApp: () => ({ app: 'mock' }),
  applicationDefault: () => ({}),
  cert: (input: unknown) => input
}));

// Use Vitest alias for firebase-admin/auth to inject mocks via globalThis.

vi.mock('../../services/common/src/logger', () => ({
  getLogger: () => ({
    info: vi.fn(),
    warn: loggerWarnMock,
    error: vi.fn()
  })
}));

vi.mock('../../services/common/src/firestore', () => ({
  getFirestore: () => ({
    collection: () => ({
      doc: (id: string) => ({
        get: async () => {
          const record = tenantStore.get(id);
          return {
            id,
            exists: !!record,
            data: () => record
          };
        }
      })
    })
  })
}));

function cloneConfig(): typeof baseConfig {
  return JSON.parse(JSON.stringify(baseConfig));
}

async function createApp(registerTenantPlugin = false) {
  const app = Fastify();
  await app.register(authenticationPlugin);
  if (registerTenantPlugin) {
    await app.register(tenantValidationPlugin);
  }
  app.get('/protected', (request) => ({
    user: request.user ?? null,
    tenant: (request as any).tenant ?? null
  }));
  return app;
}

function setTenant(id: string, record: TenantRecord) {
  tenantStore.set(id, record);
}

beforeEach(() => {
  configRef.value = cloneConfig();
  firebaseVerifyMock.mockReset();
  jwtVerifyMock.mockReset();
  tenantStore.clear();
  resetAuthForTesting();
  clearTenantCache();
  (globalThis as unknown as Record<string, unknown>).__firebaseVerifyMock = firebaseVerifyMock;
  (globalThis as unknown as Record<string, unknown>).__jwtVerifyMock = jwtVerifyMock;
});

describe('authentication plugin', () => {
  it('rejects requests without bearer token', async () => {
    const app = await createApp();
    const response = await app.inject({ method: 'GET', url: '/protected' });
    expect(response.statusCode).toBe(401);
    await app.close();
  });

  it('accepts Firebase tokens and attaches user context', async () => {
    const app = await createApp(true);
    setTenant('tenant-123', { status: 'active', name: 'Tenant 123' });
    firebaseVerifyMock.mockResolvedValue({
      uid: 'user-1',
      iss: 'https://securetoken.google.com/test-project',
      org_id: 'tenant-123',
      email: 'user@example.com'
    });

    const response = await app.inject({
      method: 'GET',
      url: '/protected',
      headers: {
        authorization: 'Bearer firebase-token',
        'x-tenant-id': 'tenant-123'
      }
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.user.orgId).toBe('tenant-123');
    expect(body.tenant.id).toBe('tenant-123');
    await app.close();
  });

  it('rejects mismatched tenant headers', async () => {
    const app = await createApp(true);
    setTenant('tenant-123', { status: 'active' });
    firebaseVerifyMock.mockResolvedValue({
      uid: 'user-1',
      iss: 'https://securetoken.google.com/test-project',
      org_id: 'tenant-123'
    });

    const response = await app.inject({
      method: 'GET',
      url: '/protected',
      headers: {
        authorization: 'Bearer firebase-token',
        'x-tenant-id': 'tenant-999'
      }
    });

    expect(response.statusCode).toBe(403);
    await app.close();
  });

  it('rejects requests without tenant header', async () => {
    const app = await createApp(true);
    setTenant('tenant-123', { status: 'active' });
    firebaseVerifyMock.mockResolvedValue({
      uid: 'user-1',
      iss: 'https://securetoken.google.com/test-project',
      org_id: 'tenant-123'
    });

    const response = await app.inject({
      method: 'GET',
      url: '/protected',
      headers: {
        authorization: 'Bearer firebase-token'
      }
    });

    expect(response.statusCode).toBe(400);
    await app.close();
  });

  it('falls back to API Gateway verification when Firebase fails', async () => {
    const app = await createApp(true);
    setTenant('tenant-abc', { status: 'active' });
    firebaseVerifyMock.mockRejectedValue(new Error('firebase failure'));
    jwtVerifyMock.mockResolvedValue({
      payload: {
        sub: 'gateway-user',
        iss: 'https://issuer.example.com',
        tenant_id: 'tenant-abc',
        aud: 'headhunter',
        client_id: 'client-123'
      }
    });

    const response = await app.inject({
      method: 'GET',
      url: '/protected',
      headers: {
        authorization: 'Bearer gateway-token',
        'x-tenant-id': 'tenant-abc'
      }
    });
    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.user.uid).toBe('gateway-user');
    expect(body.user.orgId).toBe('tenant-abc');
    await app.close();
  });

  it('rejects inactive tenants', async () => {
    const app = await createApp(true);
    setTenant('tenant-inactive', { status: 'disabled', isActive: false });
    firebaseVerifyMock.mockResolvedValue({
      uid: 'user-1',
      iss: 'https://securetoken.google.com/test-project',
      org_id: 'tenant-inactive'
    });

    const response = await app.inject({
      method: 'GET',
      url: '/protected',
      headers: {
        authorization: 'Bearer firebase-token',
        'x-tenant-id': 'tenant-inactive'
      }
    });

    expect(response.statusCode).toBe(404);
    await app.close();
  });
});
