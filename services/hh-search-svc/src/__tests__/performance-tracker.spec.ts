import { PerformanceTracker } from '../performance-tracker';

describe('PerformanceTracker', () => {
  it('computes percentiles for non-cache samples', () => {
    const tracker = new PerformanceTracker({ maxSamples: 10 });

    tracker.record({ totalMs: 100, embeddingMs: 50, retrievalMs: 30, rerankMs: 10, cacheHit: false, rerankApplied: true });
    tracker.record({ totalMs: 200, embeddingMs: 60, retrievalMs: 40, cacheHit: false });
    tracker.record({ totalMs: 300, embeddingMs: 80, retrievalMs: 60, cacheHit: false });
    tracker.record({ totalMs: 400, embeddingMs: 90, retrievalMs: 70, cacheHit: false });
    tracker.record({ totalMs: 500, embeddingMs: 110, retrievalMs: 90, cacheHit: true });

    const snapshot = tracker.getSnapshot();

    expect(snapshot.totalCount).toBe(5);
    expect(snapshot.nonCacheCount).toBe(4);
    expect(snapshot.cacheHitCount).toBe(1);
    expect(snapshot.cacheHitRatio).toBeCloseTo(0.2, 5);
    expect(snapshot.totals.p95).toBe(400);
    expect(snapshot.embedding.p90).toBe(90);
    expect(snapshot.retrieval.p95).toBe(70);
    expect(snapshot.rerank.p95).toBe(10);
  });

  it('enforces a sliding window of samples', () => {
    const tracker = new PerformanceTracker({ maxSamples: 3 });

    tracker.record({ totalMs: 10, cacheHit: false });
    tracker.record({ totalMs: 20, cacheHit: false });
    tracker.record({ totalMs: 30, cacheHit: false });
    tracker.record({ totalMs: 40, cacheHit: false });

    const snapshot = tracker.getSnapshot();

    expect(snapshot.totalCount).toBe(3);
    expect(snapshot.totals.p95).toBe(40);
  });
});
