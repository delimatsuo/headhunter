const { getMissingEnv, requestToken, gatewayFetch } = require('./utils');

const missing = getMissingEnv();

async function burstRequests(path, options) {
  const responses = await Promise.all(
    Array.from({ length: options.count }, () => gatewayFetch(path, options))
  );
  return responses.map((response) => response.status);
}

describe('API Gateway rate limiting', () => {
  if (missing.length > 0) {
    test.skip(`skipping because ${missing.join(', ')} env vars are not set`, () => {});
    return;
  }

  let token;

  beforeAll(async () => {
    token = await requestToken();
  }, 20000);

  test('enforces hybrid search tenant quota', async () => {
    const probe = await gatewayFetch('/v1/search/hybrid', {
      method: 'POST',
      token,
      body: {
        query: 'machine learning engineer',
        pageSize: 5
      }
    });
    expect(probe.headers.get('ratelimit-limit')).toBeTruthy();

    const statuses = await burstRequests('/v1/search/hybrid', {
      method: 'POST',
      token,
      count: 40,
      body: {
        query: 'machine learning engineer',
        pageSize: 10
      }
    });

    const rateLimited = statuses.filter((status) => status === 429).length;
    const successes = statuses.filter((status) => [200, 202].includes(status)).length;
    expect(successes).toBeGreaterThan(0);
    expect(rateLimited).toBeGreaterThan(0);
  }, 30000);

  test('enforces rerank tenant quota', async () => {
    const probe = await gatewayFetch('/v1/search/rerank', {
      method: 'POST',
      token,
      body: {
        query: 'machine learning engineer',
        candidates: [{ id: '1', text: 'sample candidate profile' }]
      }
    });
    expect(probe.headers.get('ratelimit-limit')).toBeTruthy();

    const statuses = await burstRequests('/v1/search/rerank', {
      method: 'POST',
      token,
      count: 25,
      body: {
        query: 'machine learning engineer',
        candidates: Array.from({ length: 15 }, (_, idx) => ({ id: `${idx}`, text: 'sample candidate profile' }))
      }
    });

    const rateLimited = statuses.filter((status) => status === 429).length;
    const successes = statuses.filter((status) => status === 200).length;
    expect(successes).toBeGreaterThan(0);
    expect(rateLimited).toBeGreaterThan(0);
  }, 30000);
});
