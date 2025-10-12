#!/usr/bin/env node
import process from 'node:process';

import { MetricsClient } from '../metrics-client';
import { formatSnapshot } from '../metrics-report';

async function main(): Promise<void> {
  const urlArg = process.argv.slice(2).find((arg) => !arg.startsWith('--'));
  const baseUrl = urlArg ?? process.env.SEARCH_HEALTH_URL ?? 'http://localhost:7102';
  const timeoutEnv = Number(process.env.SEARCH_METRICS_TIMEOUT_MS ?? '5000');
  const timeoutMs = Number.isFinite(timeoutEnv) ? timeoutEnv : 5000;

  const client = new MetricsClient({ baseUrl, timeoutMs });
  const snapshot = await client.fetchSnapshot();
  const report = formatSnapshot(snapshot);

  process.stdout.write(`Search metrics from ${baseUrl}\n${report}\n`);
}

main().catch((error) => {
  process.stderr.write(`Failed to fetch metrics: ${(error as Error).message}\n`);
  process.exit(1);
});
