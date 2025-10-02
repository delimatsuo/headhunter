import { badRequestError, getLogger, internalError } from '@hh/common';
import type { Logger } from 'pino';

import { createEmbeddingProvider, type EmbeddingProvider } from './embedding-provider';
import type { EmbeddingsServiceConfig } from './config';
import { PgVectorClient } from './pgvector-client';
import type {
  EmbeddingsServiceGenerateInput,
  EmbeddingsServiceQueryInput,
  EmbeddingsServiceUpsertInput,
  EmbeddingProviderName,
  EmbeddingRecord,
  GenerateEmbeddingResponse,
  QueryEmbeddingResponse,
  UpsertEmbeddingResponse
} from './types';

interface ServiceOptions {
  config: EmbeddingsServiceConfig;
  pgClient: PgVectorClient;
  logger?: Logger;
}

export class EmbeddingsService {
  private readonly config: EmbeddingsServiceConfig;
  private readonly pgClient: PgVectorClient;
  private readonly providerCache = new Map<EmbeddingProviderName, EmbeddingProvider>();
  private readonly logger: Logger;

  constructor({ config, pgClient, logger }: ServiceOptions) {
    this.config = config;
    this.pgClient = pgClient;
    this.logger = logger ?? getLogger({ module: 'embeddings-service' });
  }

  async generateEmbedding(input: EmbeddingsServiceGenerateInput): Promise<GenerateEmbeddingResponse> {
    const provider = this.getProvider(input.provider);

    if (input.dimensions && input.dimensions !== provider.dimensions) {
      throw badRequestError(
        `Requested dimensions (${input.dimensions}) do not match provider dimensionality (${provider.dimensions}).`
      );
    }

    const text = this.extractEmbeddingText(input.text, input.metadata);
    const embedding = await provider.generateEmbedding(text);

    this.validateEmbedding(embedding, provider);

    return {
      embedding,
      provider: provider.name,
      model: provider.model,
      dimensions: embedding.length,
      requestId: input.requestId
    } satisfies GenerateEmbeddingResponse;
  }

  async upsertEmbedding(input: EmbeddingsServiceUpsertInput): Promise<UpsertEmbeddingResponse> {
    if (!input.entityId || input.entityId.trim().length === 0) {
      throw badRequestError('entityId is required.');
    }

    const provider = this.getProvider(input.provider);
    const text = this.extractEmbeddingText(input.text, input.metadata);

    const embedding = input.embedding ?? (await provider.generateEmbedding(text));
    this.validateEmbedding(embedding, provider);

    const record: EmbeddingRecord = {
      tenantId: input.tenant.id,
      entityId: input.entityId,
      embedding,
      embeddingText: text,
      metadata: input.metadata,
      modelVersion: input.modelVersion ?? provider.model,
      chunkType: input.chunkType ?? 'default'
    };

    const result = await this.pgClient.upsertEmbedding(record);

    return {
      entityId: result.entityId,
      tenantId: result.tenantId,
      vectorId: result.id,
      modelVersion: result.modelVersion,
      chunkType: result.chunkType,
      dimensions: embedding.length,
      createdAt: result.createdAt,
      updatedAt: result.updatedAt,
      requestId: input.requestId
    } satisfies UpsertEmbeddingResponse;
  }

  async queryEmbeddings(input: EmbeddingsServiceQueryInput): Promise<QueryEmbeddingResponse> {
    const start = Date.now();
    const provider = this.getProvider(input.provider);

    let embedding = input.embedding;
    if (!embedding) {
      const queryText = this.extractEmbeddingText(input.query, input.filter);
      if (!queryText) {
        throw badRequestError('Provide either a query text or a pre-computed embedding vector.');
      }
      embedding = await provider.generateEmbedding(queryText);
    }

    this.validateEmbedding(embedding, provider);

    const limit = Math.max(1, Math.min(input.limit ?? this.config.runtime.queryLimit, this.config.runtime.queryLimit));
    const similarityThreshold = input.similarityThreshold ?? this.config.runtime.similarityThreshold;

    const results = await this.pgClient.querySimilar({
      tenantId: input.tenant.id,
      embedding,
      limit,
      similarityThreshold,
      filter: input.filter
    });

    return {
      results,
      count: results.length,
      provider: provider.name,
      model: provider.model,
      dimensions: embedding.length,
      requestId: input.requestId,
      executionMs: Date.now() - start
    } satisfies QueryEmbeddingResponse;
  }

  private getProvider(override?: EmbeddingProviderName): EmbeddingProvider {
    const target = override ?? this.config.runtime.provider;

    if (!this.providerCache.has(target)) {
      const provider = createEmbeddingProvider({
        runtime: this.config.runtime,
        providers: this.config.providers,
        logger: this.logger,
        providerOverride: target
      });
      this.providerCache.set(target, provider);
    }

    const provider = this.providerCache.get(target);
    if (!provider) {
      throw internalError('Unable to resolve embedding provider.');
    }

    return provider;
  }

  private extractEmbeddingText(primary?: string, supplemental?: Record<string, unknown>): string {
    if (primary && primary.trim().length > 0) {
      return primary.trim();
    }

    if (!supplemental) {
      return '';
    }

    const candidates: Array<string | undefined> = [];

    if (typeof supplemental.summary === 'string') {
      candidates.push(supplemental.summary);
    }
    if (typeof supplemental.title === 'string') {
      candidates.push(supplemental.title);
    }
    if (Array.isArray(supplemental.highlights)) {
      candidates.push((supplemental.highlights as Array<unknown>).filter((x) => typeof x === 'string').join('\n'));
    }
    if (typeof supplemental.description === 'string') {
      candidates.push(supplemental.description);
    }

    const combined = candidates.filter((value): value is string => Boolean(value && value.trim().length > 0)).join('\n');
    return combined.trim();
  }

  private validateEmbedding(embedding: number[], provider: EmbeddingProvider): void {
    if (!Array.isArray(embedding) || embedding.length === 0) {
      throw badRequestError('Embedding vector must be a non-empty array.');
    }

    if (!embedding.every((value) => typeof value === 'number' && Number.isFinite(value))) {
      throw badRequestError('Embedding vector must contain only finite numbers.');
    }

    if (embedding.length !== provider.dimensions) {
      throw badRequestError(
        `Embedding dimensionality mismatch. Expected ${provider.dimensions}, received ${embedding.length}.`
      );
    }
  }
}
