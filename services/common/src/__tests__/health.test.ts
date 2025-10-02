import type { FastifyInstance } from 'fastify';

describe('health endpoints', () => {
  let server: FastifyInstance;
  let buildServer: typeof import('../server').buildServer;
  let resetConfigForTesting: typeof import('../config').resetConfigForTesting;
  let resetAuthForTesting: typeof import('../auth').resetAuthForTesting;
  let resetFirestoreForTesting: typeof import('../firestore').resetFirestoreForTesting;

  beforeEach(async () => {
    process.env.FIREBASE_PROJECT_ID = 'test-project';
    process.env.ENABLE_REQUEST_LOGGING = 'false';

    jest.resetModules();

    ({ buildServer } = await import('../server'));
    ({ resetConfigForTesting } = await import('../config'));
    ({ resetAuthForTesting } = await import('../auth'));
    ({ resetFirestoreForTesting } = await import('../firestore'));

    server = await buildServer();
  });

  afterEach(async () => {
    if (server) {
      await server.close();
    }

    resetFirestoreForTesting();
    resetAuthForTesting();
    resetConfigForTesting();

    delete process.env.FIREBASE_PROJECT_ID;
    delete process.env.ENABLE_REQUEST_LOGGING;
  });

  it('responds to /health without auth headers', async () => {
    const response = await server.inject({ method: 'GET', url: '/health' });

    expect(response.statusCode).toBe(200);
    expect(response.json()).toMatchObject({ status: 'ok', service: expect.any(String) });
  });

  it('responds to /ready without auth headers', async () => {
    const response = await server.inject({ method: 'GET', url: '/ready' });

    expect(response.statusCode).toBe(200);
    expect(response.json()).toMatchObject({ status: 'ready', service: expect.any(String) });
  });
});
