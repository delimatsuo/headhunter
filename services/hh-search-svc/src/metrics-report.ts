import type { PerformanceSnapshot } from './performance-tracker';

type MaybeNumber = number | null;

function formatValue(value: MaybeNumber): string {
  if (value === null || Number.isNaN(value)) {
    return 'n/a';
  }
  return `${Math.round(value)} ms`;
}

export function formatSnapshot(snapshot: PerformanceSnapshot): string {
  const lines: string[] = [];

  lines.push(`samples: ${snapshot.nonCacheCount}/${snapshot.totalCount} (non-cache/total)`);
  lines.push(`cache hits: ${snapshot.cacheHitCount}/${snapshot.totalCount} (${(snapshot.cacheHitRatio * 100).toFixed(2)}%)`);
  lines.push(`window size: ${snapshot.windowSize}`);

  lines.push(`p95 total: ${formatValue(snapshot.totals.p95)}`);
  lines.push(`p95 embedding: ${formatValue(snapshot.embedding.p95)}`);
  lines.push(`p95 retrieval: ${formatValue(snapshot.retrieval.p95)}`);
  lines.push(`p95 rerank: ${formatValue(snapshot.rerank.p95)}`);

  lines.push(`embedding p90: ${formatValue(snapshot.embedding.p90)}`);
  lines.push(`retrieval p90: ${formatValue(snapshot.retrieval.p90)}`);

  return lines.join('\n');
}
