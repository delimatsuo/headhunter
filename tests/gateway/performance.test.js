const { performance } = require('perf_hooks');
const { getMissingEnv, requestToken, gatewayFetch } = require('./utils');

const missing = getMissingEnv();
const READ_SLO = Number(process.env.HYBRID_P95_TARGET_MS || 250);
const RERANK_SLO = Number(process.env.RERANK_P95_TARGET_MS || 350);
const RUN_TESTS = process.env.RUN_GATEWAY_PERF_TESTS === 'true';

function percentile(values, percentileRank) {
  if (values.length === 0) {
    return 0;
  }
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.ceil((percentileRank / 100) * sorted.length) - 1;
  return sorted[Math.max(index, 0)];
}

describe('API Gateway performance', () => {
  if (!RUN_TESTS) {
    test.skip('performance tests disabled (set RUN_GATEWAY_PERF_TESTS=true to enable)', () => {});
    return;
  }

  if (missing.length > 0) {
    test.skip(`skipping because ${missing.join(', ')} env vars are not set`, () => {});
    return;
  }

  let token;

  beforeAll(async () => {
    token = await requestToken();
  }, 20000);

  test('hybrid search p95 latency meets SLO', async () => {
    const durations = [];

    for (let i = 0; i < 25; i += 1) {
      const start = performance.now();
      const response = await gatewayFetch('/v1/search/hybrid', {
        method: 'POST',
        token,
        body: {
          query: 'site reliability engineer',
          pageSize: 10
        }
      });
      const end = performance.now();
      durations.push(end - start);

      expect([200, 202]).toContain(response.status);
    }

    const p95 = percentile(durations, 95);
    expect(p95).toBeLessThanOrEqual(READ_SLO);
  }, 60000);

  test('rerank p95 latency meets SLO', async () => {
    const durations = [];

    for (let i = 0; i < 25; i += 1) {
      const start = performance.now();
      const response = await gatewayFetch('/v1/search/rerank', {
        method: 'POST',
        token,
        body: {
          query: 'site reliability engineer',
          candidates: Array.from({ length: 20 }, (_, idx) => ({ id: `${idx}`, text: 'candidate profile' }))
        }
      });
      const end = performance.now();
      durations.push(end - start);

      expect([200, 202]).toContain(response.status);
    }

    const p95 = percentile(durations, 95);
    expect(p95).toBeLessThanOrEqual(RERANK_SLO);
  }, 60000);
});
