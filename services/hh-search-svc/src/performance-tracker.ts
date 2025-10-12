export interface PerformanceTrackerOptions {
  maxSamples?: number;
}

export interface PerformanceSample {
  totalMs: number;
  embeddingMs?: number;
  retrievalMs?: number;
  rerankMs?: number;
  cacheHit: boolean;
  rerankApplied?: boolean;
  timestamp?: number;
}

export interface MetricSnapshot {
  p50: number | null;
  p90: number | null;
  p95: number | null;
  p99: number | null;
  average: number | null;
  max: number | null;
  min: number | null;
}

export interface PerformanceSnapshot {
  totalCount: number;
  nonCacheCount: number;
  cacheHitCount: number;
  cacheHitRatio: number;
  windowSize: number;
  lastUpdatedAt: number | null;
  totals: MetricSnapshot;
  embedding: MetricSnapshot;
  retrieval: MetricSnapshot;
  rerank: MetricSnapshot;
}

export class PerformanceTracker {
  private readonly maxSamples: number;
  private readonly samples: PerformanceSample[] = [];

  constructor(options?: PerformanceTrackerOptions) {
    this.maxSamples = Math.max(1, options?.maxSamples ?? 500);
  }

  record(sample: PerformanceSample): void {
    const timestamp = sample.timestamp ?? Date.now();
    this.samples.push({ ...sample, timestamp });

    if (this.samples.length > this.maxSamples) {
      this.samples.splice(0, this.samples.length - this.maxSamples);
    }
  }

  clear(): void {
    this.samples.length = 0;
  }

  getSnapshot(): PerformanceSnapshot {
    const totalCount = this.samples.length;
    const nonCacheSamples = this.samples.filter((sample) => !sample.cacheHit);
    const cacheHitCount = totalCount - nonCacheSamples.length;

    return {
      totalCount,
      nonCacheCount: nonCacheSamples.length,
      cacheHitCount,
      cacheHitRatio: totalCount === 0 ? 0 : cacheHitCount / totalCount,
      windowSize: this.maxSamples,
      lastUpdatedAt: totalCount > 0 ? (this.samples[this.samples.length - 1]?.timestamp ?? null) : null,
      totals: this.buildMetricSnapshot(nonCacheSamples.map((sample) => sample.totalMs)),
      embedding: this.buildMetricSnapshot(
        nonCacheSamples
          .map((sample) => sample.embeddingMs)
          .filter((value): value is number => typeof value === 'number')
      ),
      retrieval: this.buildMetricSnapshot(
        nonCacheSamples
          .map((sample) => sample.retrievalMs)
          .filter((value): value is number => typeof value === 'number')
      ),
      rerank: this.buildMetricSnapshot(
        nonCacheSamples
          .filter((sample) => sample.rerankApplied && typeof sample.rerankMs === 'number')
          .map((sample) => sample.rerankMs as number)
      )
    } satisfies PerformanceSnapshot;
  }

  private buildMetricSnapshot(values: number[]): MetricSnapshot {
    if (values.length === 0) {
      return {
        p50: null,
        p90: null,
        p95: null,
        p99: null,
        average: null,
        max: null,
        min: null
      } satisfies MetricSnapshot;
    }

    const sorted = [...values].sort((a, b) => a - b);

    return {
      p50: this.computePercentile(sorted, 50),
      p90: this.computePercentile(sorted, 90),
      p95: this.computePercentile(sorted, 95),
      p99: this.computePercentile(sorted, 99),
      average: sorted.reduce((sum, value) => sum + value, 0) / sorted.length,
      max: sorted[sorted.length - 1],
      min: sorted[0]
    } satisfies MetricSnapshot;
  }

  private computePercentile(sortedValues: number[], percentile: number): number | null {
    if (sortedValues.length === 0) {
      return null;
    }

    const rank = percentile / 100;
    const index = Math.ceil(rank * sortedValues.length) - 1;
    const boundedIndex = Math.min(sortedValues.length - 1, Math.max(0, index));
    return sortedValues[boundedIndex];
  }
}
