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

  // Phase 11: Extended metrics
  indexType?: 'hnsw' | 'diskann';
  vectorSearchMs?: number;
  textSearchMs?: number;
  scoringMs?: number;
  parallelSavingsMs?: number;
  poolWaitMs?: number;

  // Cache metrics
  embeddingCacheHit?: boolean;
  rerankCacheHit?: boolean;
  specialtyCacheHit?: boolean;
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

  /**
   * Calculate percentile from recorded samples.
   * @param percentile - 0 to 100 (e.g., 95 for p95)
   */
  getPercentile(percentile: number): number {
    if (this.samples.length === 0) {
      return 0;
    }

    const sorted = [...this.samples].map(s => s.totalMs).sort((a, b) => a - b);
    const index = Math.ceil((percentile / 100) * sorted.length) - 1;
    return sorted[Math.max(0, index)];
  }

  /**
   * Get p50, p95, p99 latencies.
   */
  getLatencyPercentiles(): { p50: number; p95: number; p99: number } {
    return {
      p50: this.getPercentile(50),
      p95: this.getPercentile(95),
      p99: this.getPercentile(99)
    };
  }

  /**
   * Get average latency breakdown by stage.
   */
  getStageBreakdown(): {
    embedding: number;
    vectorSearch: number;
    textSearch: number;
    scoring: number;
    rerank: number;
    total: number;
  } {
    if (this.samples.length === 0) {
      return { embedding: 0, vectorSearch: 0, textSearch: 0, scoring: 0, rerank: 0, total: 0 };
    }

    const sum = (arr: (number | undefined)[]): number =>
      arr.reduce((a, b) => (a ?? 0) + (b ?? 0), 0) ?? 0;
    const n = this.samples.length;

    return {
      embedding: sum(this.samples.map(s => s.embeddingMs)) / n,
      vectorSearch: sum(this.samples.map(s => s.vectorSearchMs)) / n,
      textSearch: sum(this.samples.map(s => s.textSearchMs)) / n,
      scoring: sum(this.samples.map(s => s.scoringMs)) / n,
      rerank: sum(this.samples.map(s => s.rerankMs)) / n,
      total: sum(this.samples.map(s => s.totalMs)) / n
    };
  }

  /**
   * Get latency breakdown by index type.
   */
  getLatencyByIndexType(): { hnsw: number; diskann: number } {
    const hnsw = this.samples.filter(s => s.indexType === 'hnsw');
    const diskann = this.samples.filter(s => s.indexType === 'diskann');

    const avgMs = (arr: PerformanceSample[]): number =>
      arr.length > 0 ? arr.reduce((a, b) => a + b.totalMs, 0) / arr.length : 0;

    return {
      hnsw: avgMs(hnsw),
      diskann: avgMs(diskann)
    };
  }
}
