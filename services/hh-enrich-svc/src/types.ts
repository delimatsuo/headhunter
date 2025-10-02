import type { AuthenticatedUser, TenantContext } from '@hh/common';

export type EnrichmentJobStatus = 'queued' | 'processing' | 'completed' | 'failed';

export interface EnrichProfileRequest {
  candidateId: string;
  async?: boolean;
  idempotencyKey?: string;
  force?: boolean;
  payload?: Record<string, unknown>;
}

export interface EnrichmentJobResult {
  processingTimeSeconds?: number;
  candidateSnapshot?: Record<string, unknown>;
  embeddingUpserted?: boolean;
  embeddingSkippedReason?: string;
  modelVersion: string;
  promptVersion: string;
  phaseDurationsMs?: Record<string, number>;
  attempts?: number;
  queueDurationMs?: number;
}

export interface EnrichmentJobRecord {
  jobId: string;
  tenantId: string;
  candidateId: string;
  candidateDocumentId: string;
  dedupeKey: string;
  status: EnrichmentJobStatus;
  createdAt: string;
  updatedAt: string;
  error?: string;
  result?: EnrichmentJobResult;
  correlationId?: string;
  priority?: number;
  attemptCount?: number;
}

export interface EnrichmentJobResponse {
  job: EnrichmentJobRecord;
}

export interface EnrichmentContext {
  tenant: TenantContext;
  user?: AuthenticatedUser;
  requestId: string;
}
