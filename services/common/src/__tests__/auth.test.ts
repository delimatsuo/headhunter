import Fastify from 'fastify';
import { exportJWK, generateKeyPair, SignJWT, type KeyLike } from 'jose';

import { authenticationPlugin, resetAuthForTesting } from '../auth';
import { resetConfigForTesting } from '../config';

const verifyIdTokenMock = jest.fn();

jest.mock('firebase-admin/app', () => ({
  getApps: jest.fn(() => []),
  initializeApp: jest.fn(() => ({})),
  applicationDefault: jest.fn(() => ({})),
  cert: jest.fn((credentials) => credentials)
}));

jest.mock('firebase-admin/auth', () => ({
  getAuth: jest.fn(() => ({
    verifyIdToken: verifyIdTokenMock
  }))
}));

describe('authenticationPlugin', () => {
  beforeEach(() => {
    process.env.FIREBASE_PROJECT_ID = 'test-project';
    delete process.env.AUTH_CHECK_REVOKED;
    verifyIdTokenMock.mockReset();
    resetAuthForTesting();
    resetConfigForTesting();
  });

  afterEach(() => {
    resetAuthForTesting();
    resetConfigForTesting();
    delete process.env.FIREBASE_PROJECT_ID;
    delete process.env.AUTH_CHECK_REVOKED;
  });

  it('allows requests with valid tokens and checks for revocation', async () => {
    verifyIdTokenMock.mockResolvedValue({
      uid: 'user-123',
      org_id: 'org-456'
    });

    const app = Fastify();

    await app.register(authenticationPlugin);
    app.get('/protected', (request) => ({
      uid: request.user?.uid,
      orgId: request.user?.orgId
    }));

    const response = await app.inject({
      method: 'GET',
      url: '/protected',
      headers: {
        authorization: 'Bearer good-token'
      }
    });

    expect(response.statusCode).toBe(200);
    expect(verifyIdTokenMock).toHaveBeenCalledWith('good-token', true);

    const payload = JSON.parse(response.payload) as { uid: string; orgId: string };
    expect(payload).toEqual({ uid: 'user-123', orgId: 'org-456' });

    await app.close();
  });

  it('rejects revoked tokens', async () => {
    const revokedError = new Error('auth/id-token-revoked');
    verifyIdTokenMock.mockRejectedValue(revokedError);

    const app = Fastify();

    await app.register(authenticationPlugin);
    app.get('/protected', () => ({ status: 'ok' }));

    const response = await app.inject({
      method: 'GET',
      url: '/protected',
      headers: {
        authorization: 'Bearer revoked-token'
      }
    });

    expect(response.statusCode).toBe(401);
    expect(verifyIdTokenMock).toHaveBeenCalledWith('revoked-token', true);

    await app.close();
  });

  it('honors AUTH_CHECK_REVOKED=false for local development overrides', async () => {
    process.env.AUTH_CHECK_REVOKED = 'false';
    verifyIdTokenMock.mockResolvedValue({
      uid: 'user-789',
      org_id: 'org-789'
    });

    const app = Fastify();

    await app.register(authenticationPlugin);
    app.get('/protected', (request) => ({
      uid: request.user?.uid
    }));

    const response = await app.inject({
      method: 'GET',
      url: '/protected',
      headers: {
        authorization: 'Bearer unchecked-token'
      }
    });

    expect(response.statusCode).toBe(200);
    expect(verifyIdTokenMock).toHaveBeenCalledWith('unchecked-token', false);

    await app.close();
  });
});

describe('gateway token verification', () => {
  let privateKey: KeyLike;
  let jwk: Record<string, unknown>;
  let originalFetch: unknown;
  let mockFetch: jest.Mock;

  beforeAll(async () => {
    const { privateKey: generatedPrivateKey, publicKey } = await generateKeyPair('RS256');
    privateKey = generatedPrivateKey;
    jwk = await exportJWK(publicKey);
    jwk.kid = 'test-key';
    jwk.use = 'sig';
    jwk.alg = 'RS256';
  });

  beforeEach(() => {
    process.env.FIREBASE_PROJECT_ID = 'test-project';
    process.env.AUTH_MODE = 'gateway';
    process.env.ENABLE_GATEWAY_TOKENS = 'true';
    process.env.ALLOWED_TOKEN_ISSUERS = 'https://idp.test/|https://idp.test/.well-known/jwks.json';
    process.env.GATEWAY_AUDIENCE = 'https://api.ella.jobs/gateway';
    process.env.ENABLE_TOKEN_CACHE = 'false';

    originalFetch = (global as unknown as { fetch?: unknown }).fetch;
    mockFetch = jest.fn(async (url: string | URL) => {
      const target = typeof url === 'string' ? url : url.toString();
      if (target === 'https://idp.test/.well-known/jwks.json') {
        return {
          ok: true,
          status: 200,
          headers: new Map([['content-type', 'application/json']]),
          json: async () => ({ keys: [jwk] })
        } as any;
      }

      throw new Error(`Unexpected fetch call: ${target}`);
    });

    (global as unknown as { fetch: unknown }).fetch = mockFetch;

    resetConfigForTesting();
    resetAuthForTesting();
  });

  afterEach(() => {
    resetConfigForTesting();
    resetAuthForTesting();
    delete process.env.FIREBASE_PROJECT_ID;
    delete process.env.AUTH_MODE;
    delete process.env.ENABLE_GATEWAY_TOKENS;
    delete process.env.ALLOWED_TOKEN_ISSUERS;
    delete process.env.GATEWAY_AUDIENCE;
    delete process.env.ENABLE_TOKEN_CACHE;

    if (typeof originalFetch === 'function') {
      (global as unknown as { fetch: unknown }).fetch = originalFetch;
    } else {
      delete (global as unknown as { fetch?: unknown }).fetch;
    }
  });

  it('accepts valid gateway tokens signed by configured issuer', async () => {
    const token = await new SignJWT({ sub: 'client-1', org_id: 'tenant-123' })
      .setProtectedHeader({ alg: 'RS256', kid: 'test-key' })
      .setIssuer('https://idp.test/')
      .setAudience('https://api.ella.jobs/gateway')
      .setIssuedAt()
      .setExpirationTime('5m')
      .sign(privateKey);

    const app = Fastify();
    await app.register(authenticationPlugin);
    app.get('/secure', (request) => ({
      uid: request.user?.uid,
      orgId: request.user?.orgId,
      tokenType: request.requestContext?.auth?.tokenType
    }));

    const response = await app.inject({
      method: 'GET',
      url: '/secure',
      headers: {
        authorization: `Bearer ${token}`
      }
    });

    expect(response.statusCode).toBe(200);
    const payload = JSON.parse(response.payload) as { uid: string; orgId: string; tokenType: string };
    expect(payload).toEqual({ uid: 'client-1', orgId: 'tenant-123', tokenType: 'gateway' });
    expect(mockFetch).toHaveBeenCalledTimes(1);

    await app.close();
  });

  it('rejects tokens with mismatched audience', async () => {
    const token = await new SignJWT({ sub: 'client-1', org_id: 'tenant-123' })
      .setProtectedHeader({ alg: 'RS256', kid: 'test-key' })
      .setIssuer('https://idp.test/')
      .setAudience('https://api.invalid/gateway')
      .setIssuedAt()
      .setExpirationTime('5m')
      .sign(privateKey);

    const app = Fastify();
    await app.register(authenticationPlugin);
    app.get('/secure', () => ({ status: 'ok' }));

    const response = await app.inject({
      method: 'GET',
      url: '/secure',
      headers: {
        authorization: `Bearer ${token}`
      }
    });

    expect(response.statusCode).toBe(401);
    await app.close();
  });
});
