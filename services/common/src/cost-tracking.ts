import type { FastifyRequest } from 'fastify';

import { emitCostMetric, type CostMetricEntry } from './logger';

const TOGETHER_PRICING_USD_PER_1K_TOKENS: Record<string, { prompt: number; completion: number }> = {
  'rerank-large': { prompt: 0.2, completion: 0.2 },
  default: { prompt: 0.15, completion: 0.15 }
};

const GEMINI_PRICE_PER_1K_TOKENS_USD = 0.0005;
const CLOUD_SQL_COST_PER_1K_ROW_READS_CENTS = 0.25;
const CLOUD_SQL_COST_PER_1K_ROW_WRITES_CENTS = 0.4;
const REDIS_OPERATION_COST_CENTS = 0.0002;
const CLOUD_RUN_CPU_COST_PER_SECOND_CENTS = 0.000024;
const CLOUD_RUN_MEMORY_COST_PER_GIB_SECOND_CENTS = 0.0000028;

export interface CostComputationResult {
  costCents: number;
  details: Record<string, unknown>;
}

export interface TogetherAICostInput {
  apiName: string;
  tenantId?: string;
  promptTokens: number;
  completionTokens: number;
  model?: string;
  provider?: string;
  metadata?: Record<string, unknown>;
  request?: FastifyRequest;
}

export interface GeminiEmbeddingCostInput {
  apiName: string;
  tenantId?: string;
  textTokens: number;
  dimensions: number;
  metadata?: Record<string, unknown>;
  request?: FastifyRequest;
}

export interface CloudSqlCostInput {
  apiName: string;
  tenantId?: string;
  rowsRead: number;
  rowsWritten: number;
  metadata?: Record<string, unknown>;
  request?: FastifyRequest;
}

export interface RedisCostInput {
  apiName: string;
  tenantId?: string;
  operations: number;
  operationType?: 'read' | 'write' | 'delete';
  metadata?: Record<string, unknown>;
  request?: FastifyRequest;
}

export interface CloudRunExecutionCostInput {
  apiName: string;
  tenantId?: string;
  cpuSeconds: number;
  memoryGbSeconds: number;
  metadata?: Record<string, unknown>;
  request?: FastifyRequest;
}

export interface CostAnomaly {
  isAnomalous: boolean;
  score: number;
  baseline: number;
  latest: number;
}

export interface CostSummary {
  totalCostCents: number;
  breakdown: Record<string, number>;
}

type DispatchableCostEntry = Omit<CostMetricEntry, 'request_id' | 'trace_id' | 'span_id'>;

function roundCents(value: number): number {
  return Math.max(0, Number(value.toFixed(4)));
}

function dispatchCostMetric(entry: DispatchableCostEntry, request?: FastifyRequest): CostMetricEntry {
  if (request && typeof (request as { logCostMetric?: (payload: DispatchableCostEntry) => void }).logCostMetric === 'function') {
    (request as { logCostMetric?: (payload: DispatchableCostEntry) => void }).logCostMetric!(entry);
    return entry;
  }

  emitCostMetric(entry);
  return entry;
}

export function calculateTogetherAICostCents({ promptTokens, completionTokens, model }: TogetherAICostInput): CostComputationResult {
  const pricing = TOGETHER_PRICING_USD_PER_1K_TOKENS[model ?? ''] ?? TOGETHER_PRICING_USD_PER_1K_TOKENS.default;
  const promptCostUsd = (promptTokens / 1000) * pricing.prompt;
  const completionCostUsd = (completionTokens / 1000) * pricing.completion;
  const costCents = roundCents((promptCostUsd + completionCostUsd) * 100);

  return {
    costCents,
    details: {
      promptTokens,
      completionTokens,
      promptCostUsd,
      completionCostUsd,
      model: model ?? 'default'
    }
  };
}

export function trackTogetherAICost(input: TogetherAICostInput): CostMetricEntry {
  const { costCents, details } = calculateTogetherAICostCents(input);
  return dispatchCostMetric(
    {
      tenant_id: input.tenantId,
      api_name: input.apiName,
      cost_cents: costCents,
      provider: input.provider ?? 'together-ai',
      cost_category: 'llm',
      source: 'together_ai_api',
      metadata: { ...details, ...(input.metadata ?? {}) }
    },
    input.request
  );
}

export function calculateGeminiEmbeddingCostCents({ textTokens, dimensions }: GeminiEmbeddingCostInput): CostComputationResult {
  const totalTokens = textTokens * Math.max(dimensions / 1024, 1);
  const costUsd = (totalTokens / 1000) * GEMINI_PRICE_PER_1K_TOKENS_USD;
  const costCents = roundCents(costUsd * 100);

  return {
    costCents,
    details: {
      textTokens,
      dimensions,
      totalChargeableTokens: totalTokens,
      pricePer1kTokensUsd: GEMINI_PRICE_PER_1K_TOKENS_USD
    }
  };
}

export function trackGeminiEmbeddingCost(input: GeminiEmbeddingCostInput): CostMetricEntry {
  const { costCents, details } = calculateGeminiEmbeddingCostCents(input);
  return dispatchCostMetric(
    {
      tenant_id: input.tenantId,
      api_name: input.apiName,
      cost_cents: costCents,
      provider: 'gemini',
      cost_category: 'embedding',
      source: 'gemini_embeddings',
      metadata: { ...details, ...(input.metadata ?? {}) }
    },
    input.request
  );
}

export function calculateCloudSqlCostCents({ rowsRead, rowsWritten }: CloudSqlCostInput): CostComputationResult {
  const readCost = (rowsRead / 1000) * CLOUD_SQL_COST_PER_1K_ROW_READS_CENTS;
  const writeCost = (rowsWritten / 1000) * CLOUD_SQL_COST_PER_1K_ROW_WRITES_CENTS;
  const costCents = roundCents(readCost + writeCost);

  return {
    costCents,
    details: {
      rowsRead,
      rowsWritten,
      readCostCents: roundCents(readCost),
      writeCostCents: roundCents(writeCost)
    }
  };
}

export function trackCloudSqlCost(input: CloudSqlCostInput): CostMetricEntry {
  const { costCents, details } = calculateCloudSqlCostCents(input);
  return dispatchCostMetric(
    {
      tenant_id: input.tenantId,
      api_name: input.apiName,
      cost_cents: costCents,
      provider: 'cloud-sql',
      cost_category: 'database',
      source: 'cloud_sql',
      metadata: { ...details, ...(input.metadata ?? {}) }
    },
    input.request
  );
}

export function calculateRedisCostCents({ operations }: RedisCostInput): CostComputationResult {
  const costCents = roundCents(operations * REDIS_OPERATION_COST_CENTS);

  return {
    costCents,
    details: {
      operations,
      pricePerOperationCents: REDIS_OPERATION_COST_CENTS
    }
  };
}

export function trackRedisCost(input: RedisCostInput): CostMetricEntry {
  const { costCents, details } = calculateRedisCostCents(input);
  return dispatchCostMetric(
    {
      tenant_id: input.tenantId,
      api_name: input.apiName,
      cost_cents: costCents,
      provider: 'redis',
      cost_category: 'cache',
      source: 'redis_cache',
      metadata: { ...details, operationType: input.operationType ?? 'read', ...(input.metadata ?? {}) }
    },
    input.request
  );
}

export function calculateCloudRunExecutionCostCents({ cpuSeconds, memoryGbSeconds }: CloudRunExecutionCostInput): CostComputationResult {
  const cpuCost = cpuSeconds * CLOUD_RUN_CPU_COST_PER_SECOND_CENTS;
  const memoryCost = memoryGbSeconds * CLOUD_RUN_MEMORY_COST_PER_GIB_SECOND_CENTS;
  const costCents = roundCents(cpuCost + memoryCost);

  return {
    costCents,
    details: {
      cpuSeconds,
      memoryGbSeconds,
      cpuCostCents: roundCents(cpuCost),
      memoryCostCents: roundCents(memoryCost)
    }
  };
}

export function trackCloudRunExecutionCost(input: CloudRunExecutionCostInput): CostMetricEntry {
  const { costCents, details } = calculateCloudRunExecutionCostCents(input);
  return dispatchCostMetric(
    {
      tenant_id: input.tenantId,
      api_name: input.apiName,
      cost_cents: costCents,
      provider: 'cloud-run',
      cost_category: 'compute',
      source: 'cloud_run',
      metadata: { ...details, ...(input.metadata ?? {}) }
    },
    input.request
  );
}

export function detectCostAnomaly(series: number[]): CostAnomaly {
  if (series.length < 5) {
    return {
      isAnomalous: false,
      score: 0,
      baseline: series.length > 0 ? series[series.length - 1] : 0,
      latest: series.length > 0 ? series[series.length - 1] : 0
    };
  }

  const latest = series[series.length - 1];
  const previous = series.slice(0, -1);
  const mean = previous.reduce((sum, value) => sum + value, 0) / previous.length;
  const variance = previous.reduce((sum, value) => sum + (value - mean) ** 2, 0) / previous.length;
  const stdDev = Math.sqrt(variance);
  const score = stdDev === 0 ? 0 : (latest - mean) / stdDev;

  return {
    isAnomalous: score >= 3,
    score,
    baseline: mean,
    latest
  };
}

export function summarizeCosts(entries: CostMetricEntry[]): CostSummary {
  const summary: CostSummary = {
    totalCostCents: 0,
    breakdown: {}
  };

  for (const entry of entries) {
    summary.totalCostCents += entry.cost_cents;
    const category = entry.cost_category ?? 'uncategorized';
    summary.breakdown[category] = (summary.breakdown[category] ?? 0) + entry.cost_cents;
  }

  summary.totalCostCents = roundCents(summary.totalCostCents);
  for (const key of Object.keys(summary.breakdown)) {
    summary.breakdown[key] = roundCents(summary.breakdown[key]);
  }

  return summary;
}

export function buildCostReport(entries: CostMetricEntry[]): Record<string, unknown> {
  const summary = summarizeCosts(entries);
  const anomaly = detectCostAnomaly(entries.map((entry) => entry.cost_cents));

  return {
    summary,
    anomaly,
    generatedAt: new Date().toISOString()
  };
}
