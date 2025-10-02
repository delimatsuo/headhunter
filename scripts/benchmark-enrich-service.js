#!/usr/bin/env node
import { performance } from 'node:perf_hooks';
import { setTimeout as delay } from 'node:timers/promises';

const args = process.argv.slice(2);
const options = {
  jobs: 20,
  concurrency: 5,
  pollIntervalMs: 750
};

for (let i = 0; i < args.length; i += 1) {
  const [key, value] = args[i].split('=');
  if (key === '--jobs' && value) {
    options.jobs = Number(value);
  } else if (key === '--concurrency' && value) {
    options.concurrency = Number(value);
  } else if (key === '--poll' && value) {
    options.pollIntervalMs = Number(value);
  }
}

const serviceUrl = process.env.ENRICH_URL ?? 'http://localhost:7112';
const tenantId = process.env.ENRICH_BENCH_TENANT ?? 'tenant-alpha';
const results = [] as Array<{ jobId: string; duration: number; status: string; embedding: boolean }>;
const errors: Array<{ jobId: string; error: string }> = [];

function percentile(samples: number[], target: number): number {
  if (samples.length === 0) {
    return 0;
  }
  const sorted = [...samples].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.round((target / 100) * (sorted.length - 1)));
  return Number(sorted[idx].toFixed(2));
}

async function submitJob(candidateId: string): Promise<string> {
  const payload = {
    candidateId,
    async: true,
    payload: {
      benchmark: true,
      issuedAt: new Date().toISOString()
    }
  };

  const response = await fetch(`${serviceUrl}/v1/enrich/profile`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-ID': tenantId
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`Failed to submit job: ${response.status}`);
  }

  const body = await response.json();
  return body.job.jobId as string;
}

async function waitForStatus(jobId: string): Promise<{ status: string; embedding: boolean }> {
  const start = performance.now();
  while (true) {
    const res = await fetch(`${serviceUrl}/v1/enrich/status/${jobId}`, {
      headers: { 'X-Tenant-ID': tenantId }
    });
    if (!res.ok) {
      throw new Error(`Status check failed for ${jobId}: ${res.status}`);
    }
    const body = await res.json();
    const status = body.job?.status ?? 'unknown';
    if (status === 'completed' || status === 'failed') {
      const duration = performance.now() - start;
      return {
        status,
        embedding: Boolean(body.job?.result?.embeddingUpserted),
        duration
      } as { status: string; embedding: boolean; duration: number };
    }
    await delay(options.pollIntervalMs);
  }
}

async function runJob(index: number): Promise<void> {
  const candidateId = `bench-${Date.now()}-${index}`;
  try {
    const jobId = await submitJob(candidateId);
    const { status, embedding, duration } = await waitForStatus(jobId);
    results.push({ jobId, status, embedding, duration });
    process.stdout.write(`Job ${jobId} ${status} in ${duration.toFixed(2)}ms\n`);
  } catch (error) {
    errors.push({ jobId: `bench-${index}`, error: error instanceof Error ? error.message : String(error) });
  }
}

async function main(): Promise<void> {
  let index = 0;

  async function workerLoop(): Promise<void> {
    while (true) {
      const current = index;
      index += 1;
      if (current >= options.jobs) {
        return;
      }
      await runJob(current);
    }
  }

  const workers = Array.from({ length: Math.max(1, options.concurrency) }, () => workerLoop());
  await Promise.allSettled(workers);

  const durations = results.map((r) => r.duration);
  const completed = results.filter((r) => r.status === 'completed');
  const failureCount = results.filter((r) => r.status !== 'completed').length + errors.length;

  console.log('\n=== Benchmark Summary ===');
  console.log(`Jobs attempted: ${options.jobs}`);
  console.log(`Jobs completed: ${completed.length}`);
  console.log(`Jobs failed: ${failureCount}`);
  console.log(`Embedding success rate: ${completed.filter((r) => r.embedding).length}/${completed.length}`);
  console.log(`Average latency: ${durations.length ? (durations.reduce((a, b) => a + b, 0) / durations.length).toFixed(2) : 0} ms`);
  console.log(`p50 latency: ${percentile(durations, 50)} ms`);
  console.log(`p95 latency: ${percentile(durations, 95)} ms`);
  console.log(`p99 latency: ${percentile(durations, 99)} ms`);

  if (errors.length > 0) {
    console.log('\nErrors encountered:');
    errors.forEach((entry) => {
      console.log(` - ${entry.jobId}: ${entry.error}`);
    });
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
