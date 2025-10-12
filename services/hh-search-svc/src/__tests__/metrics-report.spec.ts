import { formatSnapshot } from '../metrics-report';
import type { PerformanceSnapshot } from '../performance-tracker';

describe('formatSnapshot', () => {
  const snapshot: PerformanceSnapshot = {
    totalCount: 10,
    nonCacheCount: 6,
    cacheHitCount: 4,
    cacheHitRatio: 0.4,
    windowSize: 500,
    lastUpdatedAt: 1730000000000,
    totals: { p50: 900, p90: 1100, p95: 1180, p99: 1300, average: 950, max: 1250, min: 870 },
    embedding: { p50: 300, p90: 450, p95: 500, p99: 600, average: 320, max: 560, min: 280 },
    retrieval: { p50: 120, p90: 200, p95: 240, p99: 260, average: 180, max: 250, min: 110 },
    rerank: { p50: 80, p90: 120, p95: 140, p99: 180, average: 100, max: 160, min: 70 }
  };

  it('produces a human-readable summary', () => {
    const output = formatSnapshot(snapshot);
    expect(output).toContain('p95 total: 1180 ms');
    expect(output).toContain('cache hits: 4/10 (40.00%)');
    expect(output).toContain('embedding p90: 450 ms');
    expect(output).toContain('p95 rerank: 140 ms');
  });

  it('handles missing rerank samples gracefully', () => {
    const clone: PerformanceSnapshot = {
      ...snapshot,
      rerank: { p50: null, p90: null, p95: null, p99: null, average: null, max: null, min: null }
    };

    const output = formatSnapshot(clone);
    expect(output).toContain('p95 rerank: n/a');
  });
});
