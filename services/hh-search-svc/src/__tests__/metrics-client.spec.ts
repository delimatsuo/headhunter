import { MetricsClient } from '../metrics-client';
import type { PerformanceSnapshot } from '../performance-tracker';

describe('MetricsClient', () => {
  const sampleSnapshot: PerformanceSnapshot = {
    totalCount: 5,
    nonCacheCount: 3,
    cacheHitCount: 2,
    cacheHitRatio: 0.4,
    windowSize: 500,
    lastUpdatedAt: 123,
    totals: { p50: 120, p90: 300, p95: 360, p99: 400, average: 210, max: 420, min: 110 },
    embedding: { p50: 60, p90: 120, p95: 150, p99: 180, average: 90, max: 160, min: 50 },
    retrieval: { p50: 40, p90: 80, p95: 110, p99: 150, average: 75, max: 140, min: 35 },
    rerank: { p50: 20, p90: 40, p95: 45, p99: 75, average: 30, max: 70, min: 15 }
  };

  function createClient(mockResponse: { status: number; ok: boolean; body: unknown }) {
    const fetchFn = vi.fn(async () => ({
      status: mockResponse.status,
      ok: mockResponse.ok,
      json: async () => mockResponse.body
    })) as unknown as typeof fetch;

    const client = new MetricsClient({ baseUrl: 'http://localhost:7102', fetchFn, apiKey: 'key-123' });
    return { client, fetchFn };
  }

  it('returns metrics from healthy response', async () => {
    const { client, fetchFn } = createClient({
      status: 200,
      ok: true,
      body: { status: 'ok', metrics: sampleSnapshot }
    });

    const snapshot = await client.fetchSnapshot();

    const call = (fetchFn as jest.Mock).mock.calls[0];
    expect(call[0]).toBeInstanceOf(URL);
    expect((call[0] as URL).toString()).toBe('http://localhost:7102/health?key=key-123');
    expect(snapshot).toEqual(sampleSnapshot);
  });

  it('returns metrics when service is degraded', async () => {
    const { client } = createClient({
      status: 503,
      ok: false,
      body: { status: 'degraded', metrics: sampleSnapshot }
    });

    const snapshot = await client.fetchSnapshot();
    expect(snapshot).toEqual(sampleSnapshot);
  });

  it('throws when metrics are missing', async () => {
    const { client } = createClient({
      status: 200,
      ok: true,
      body: { status: 'ok' }
    });

    await expect(client.fetchSnapshot()).rejects.toThrow(/metrics payload missing/i);
  });
});
