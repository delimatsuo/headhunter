import type { TenantContext, AuthenticatedUser } from '@hh/common';

export type EmbeddingVector = number[];

export type EmbeddingProviderName = 'vertex-ai' | 'local' | 'together';

export interface GenerateEmbeddingRequest {
  text: string;
  provider?: EmbeddingProviderName;
  dimensions?: number;
  metadata?: Record<string, unknown>;
}

export interface GenerateEmbeddingResponse {
  embedding: EmbeddingVector;
  provider: EmbeddingProviderName;
  model: string;
  dimensions: number;
  requestId: string;
  cached?: boolean;
}

export interface UpsertEmbeddingRequest {
  entityId: string;
  text?: string;
  embedding?: EmbeddingVector;
  metadata?: Record<string, unknown>;
  modelVersion?: string;
  chunkType?: string;
  provider?: EmbeddingProviderName;
}

export interface UpsertEmbeddingResponse {
  entityId: string;
  tenantId: string;
  vectorId: string;
  modelVersion: string;
  chunkType: string;
  dimensions: number;
  createdAt: string;
  updatedAt: string;
  requestId: string;
}

export interface QueryEmbeddingRequest {
  query?: string;
  embedding?: EmbeddingVector;
  limit?: number;
  similarityThreshold?: number;
  provider?: EmbeddingProviderName;
  filter?: Record<string, unknown>;
}

export interface EmbeddingSearchResult {
  entityId: string;
  similarity: number;
  metadata?: Record<string, unknown>;
  modelVersion: string;
  chunkType: string;
  embeddingId: string;
  updatedAt: string;
}

export interface QueryEmbeddingResponse {
  results: EmbeddingSearchResult[];
  count: number;
  provider: EmbeddingProviderName;
  model: string;
  dimensions: number;
  requestId: string;
  executionMs: number;
}

export interface EmbeddingRecord {
  tenantId: string;
  entityId: string;
  embedding: EmbeddingVector;
  embeddingText?: string;
  metadata?: Record<string, unknown>;
  modelVersion: string;
  chunkType: string;
}

export interface EmbeddingQueryOptions {
  tenant: TenantContext;
  user?: AuthenticatedUser;
  limit: number;
  similarityThreshold: number;
}

export interface EmbeddingProviderMetadata {
  name: EmbeddingProviderName;
  model: string;
  dimensions: number;
}

export interface EmbeddingsServiceGenerateInput extends GenerateEmbeddingRequest {
  tenant: TenantContext;
  user?: AuthenticatedUser;
  requestId: string;
}

export interface EmbeddingsServiceUpsertInput extends UpsertEmbeddingRequest {
  tenant: TenantContext;
  user?: AuthenticatedUser;
  requestId: string;
}

export interface EmbeddingsServiceQueryInput extends QueryEmbeddingRequest {
  tenant: TenantContext;
  user?: AuthenticatedUser;
  requestId: string;
}
