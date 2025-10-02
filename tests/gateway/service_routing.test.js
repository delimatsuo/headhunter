const { getMissingEnv, requestToken, gatewayFetch } = require('./utils');

const missing = getMissingEnv();

const ROUTES = [
  {
    method: 'GET',
    path: '/v1/occupations',
    description: 'Occupations catalogue',
    expectJsonArray: 'occupations'
  },
  {
    method: 'GET',
    path: '/v1/skills',
    description: 'Skills catalogue',
    expectJsonArray: 'skills'
  },
  {
    method: 'GET',
    path: '/v1/evidence/documents',
    description: 'Evidence documents',
    expectJsonArray: 'documents'
  },
  {
    method: 'POST',
    path: '/v1/search/hybrid',
    body: { query: 'data scientist', pageSize: 5 },
    description: 'Hybrid search',
    expectJsonArray: 'results'
  },
  {
    method: 'POST',
    path: '/v1/search/rerank',
    body: { query: 'data scientist', candidates: [{ id: '1', text: 'sample profile' }] },
    description: 'Rerank',
    expectJsonArray: 'results'
  },
  {
    method: 'GET',
    path: '/v1/admin/tenants',
    description: 'Admin tenants',
    expectJsonArray: 'tenants'
  }
];

describe('API Gateway routing', () => {
  if (missing.length > 0) {
    test.skip(`skipping because ${missing.join(', ')} env vars are not set`, () => {});
    return;
  }

  let token;

  beforeAll(async () => {
    token = await requestToken();
  }, 20000);

  for (const route of ROUTES) {
    const name = `${route.method} ${route.path} (${route.description})`;
    test(name, async () => {
      const response = await gatewayFetch(route.path, {
        method: route.method,
        token,
        body: route.body
      });

      const allowedStatuses = [200, 202, 204];
      expect(allowedStatuses).toContain(response.status);

      const traceHeader = response.headers.get('x-cloud-trace-context');
      expect(traceHeader).toBeTruthy();

      const isJson = response.headers.get('content-type')?.includes('application/json');
      if (isJson && response.status === 200) {
        const data = await response.json();
        if (route.expectJsonArray) {
          expect(data).toHaveProperty(route.expectJsonArray);
          expect(Array.isArray(data[route.expectJsonArray])).toBe(true);
        } else {
          expect(typeof data).toBe('object');
        }
      }
    }, 20000);
  }
});
