#!/usr/bin/env ts-node
import process from 'node:process';

interface CliOptions {
  baseUrl: string;
  apiKey?: string;
  tenantId?: string;
  iterations: number;
  concurrency: number;
  limit: number;
  query?: string;
  jobDescription?: string;
  includeDebug: boolean;
  bustCache: boolean;
}

interface PercentileResult {
  p50: number;
  p90: number;
  p95: number;
  p99: number;
  average: number;
  min: number;
  max: number;
}

type HeaderMap = Record<string, string>;

interface TimingRecord {
  totalMs: number;
  embeddingMs?: number;
  retrievalMs?: number;
  rerankMs?: number;
  rankingMs?: number;
  cacheMs?: number;
  cacheHit: boolean;
}

function parseArgs(argv: string[]): CliOptions {
  const options: Record<string, string> = {};
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg.startsWith('--')) {
      const key = arg.slice(2);
      const value = argv[i + 1];
      if (value && !value.startsWith('--')) {
        options[key] = value;
        i += 1;
      } else {
        options[key] = 'true';
      }
    }
  }

  return {
    baseUrl: options.url ?? process.env.SEARCH_BASE_URL ?? 'http://localhost:7102',
    apiKey: options.apiKey ?? process.env.SEARCH_API_KEY,
    tenantId: options.tenantId ?? process.env.SEARCH_TENANT_ID,
    iterations: Number(options.iterations ?? process.env.SEARCH_BENCH_ITERS ?? 20),
    concurrency: Number(options.concurrency ?? process.env.SEARCH_BENCH_CONCURRENCY ?? 4),
    limit: Number(options.limit ?? 10),
    query: options.query ?? process.env.SEARCH_BENCH_QUERY,
    jobDescription: options.jobDescription ?? process.env.SEARCH_BENCH_JD,
    includeDebug: options.debug === 'true' || process.env.SEARCH_BENCH_DEBUG === 'true',
    bustCache: options.bustCache === 'true' || process.env.SEARCH_BENCH_BUST_CACHE === 'true'
  } satisfies CliOptions;
}

function computePercentiles(values: number[]): PercentileResult {
  if (values.length === 0) {
    return { p50: 0, p90: 0, p95: 0, p99: 0, average: 0, min: 0, max: 0 };
  }
  const sorted = [...values].sort((a, b) => a - b);
  const percentile = (p: number) => {
    const rank = Math.ceil((p / 100) * sorted.length) - 1;
    const index = Math.max(0, Math.min(sorted.length - 1, rank));
    return sorted[index];
  };
  const average = sorted.reduce((sum, value) => sum + value, 0) / sorted.length;
  return {
    p50: percentile(50),
    p90: percentile(90),
    p95: percentile(95),
    p99: percentile(99),
    average,
    min: sorted[0],
    max: sorted[sorted.length - 1]
  } satisfies PercentileResult;
}

async function runIteration(options: CliOptions): Promise<TimingRecord> {
  const payload: Record<string, unknown> = {
    limit: options.limit,
    includeDebug: options.includeDebug
  };
  if (options.query) {
    payload.query = options.query;
  }
  if (options.jobDescription) {
    payload.jobDescription = options.jobDescription;
  }
  if (options.bustCache) {
    payload.jdHash = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  }

  const headers: HeaderMap = {
    'Content-Type': 'application/json'
  };
  if (options.apiKey) {
    headers['x-api-key'] = options.apiKey;
  }
  if (options.tenantId) {
    headers['X-Tenant-ID'] = options.tenantId;
  }

  const url = new URL(`${options.baseUrl.replace(/\/$/, '')}/v1/search/hybrid`);
  if (options.apiKey) {
    url.searchParams.set('key', options.apiKey);
  }

  const started = performance.now();
  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload)
  });
  const finished = performance.now();

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request failed: ${response.status} ${response.statusText} -> ${body}`);
  }

  const json = (await response.json()) as {
    cacheHit: boolean;
    timings: {
      totalMs: number;
      embeddingMs?: number;
      retrievalMs?: number;
      rankingMs?: number;
      rerankMs?: number;
      cacheMs?: number;
    };
  };

  return {
    totalMs: json.timings?.totalMs ?? finished - started,
    embeddingMs: json.timings?.embeddingMs,
    retrievalMs: json.timings?.retrievalMs,
    rankingMs: json.timings?.rankingMs,
    rerankMs: json.timings?.rerankMs,
    cacheMs: json.timings?.cacheMs,
    cacheHit: json.cacheHit === true
  } satisfies TimingRecord;
}

async function runBenchmark(options: CliOptions): Promise<void> {
  const totalIterations = Math.max(1, options.iterations);
  const concurrency = Math.max(1, options.concurrency);
  const timings: TimingRecord[] = [];
  let inflight = 0;
  let index = 0;
  let failures = 0;

  const next = async (): Promise<void> => {
    if (index >= totalIterations) {
      return;
    }
    const current = index;
    index += 1;
    inflight += 1;
    try {
      const record = await runIteration(options);
      timings.push(record);
      process.stdout.write(`Iteration ${current + 1}/${totalIterations} -> total ${record.totalMs.toFixed(1)} ms\n`);
    } catch (error) {
      failures += 1;
      process.stderr.write(`Iteration ${current + 1} failed: ${(error as Error).message}\n`);
    } finally {
      inflight -= 1;
      if (index < totalIterations) {
        void next();
      }
    }
  };

  const starters = Array(Math.min(concurrency, totalIterations))
    .fill(null)
    .map(() => next());

  await Promise.all(starters);
  while (inflight > 0) {
    await new Promise((resolve) => setTimeout(resolve, 50));
  }

  const nonCache = timings.filter((record) => !record.cacheHit);
  const cacheHits = timings.filter((record) => record.cacheHit);

  const totalStats = computePercentiles(nonCache.map((record) => record.totalMs));
  const embeddingStats = computePercentiles(
    nonCache
      .map((record) => record.embeddingMs)
      .filter((value): value is number => typeof value === 'number')
  );
  const rerankStats = computePercentiles(
    nonCache
      .map((record) => record.rerankMs)
      .filter((value): value is number => typeof value === 'number')
  );

  process.stdout.write('\nBenchmark complete\n');
  process.stdout.write(`Successful iterations: ${timings.length}, Failures: ${failures}\n`);
  process.stdout.write(`Cache hits: ${cacheHits.length}/${timings.length} (${((cacheHits.length / Math.max(1, timings.length)) * 100).toFixed(2)}%)\n`);
  process.stdout.write(`p95 totalMs: ${totalStats.p95.toFixed(1)} ms\n`);
  process.stdout.write(`p95 embeddingMs: ${embeddingStats.p95.toFixed(1)} ms\n`);
  process.stdout.write(`p95 rerankMs: ${rerankStats.p95.toFixed(1)} ms\n`);
}

(async () => {
  const options = parseArgs(process.argv.slice(2));
  await runBenchmark(options);
})();
