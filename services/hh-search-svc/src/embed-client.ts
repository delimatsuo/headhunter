import axios, { type AxiosInstance } from 'axios';
import type { Logger } from 'pino';
import { getIdTokenManager } from '@hh/common';

import type { EmbedServiceConfig } from './config';
import type { EmbeddingVector } from './types';

export interface GenerateEmbeddingOptions {
  tenantId: string;
  requestId: string;
  query: string;
  dimensions?: number;
  metadata?: Record<string, unknown>;
}

export interface GenerateEmbeddingResult {
  embedding: EmbeddingVector;
  provider: string;
  model: string;
  dimensions: number;
  latencyMs: number;
}

export interface EmbedHealthStatus {
  status: 'healthy' | 'degraded' | 'unavailable';
  latencyMs?: number;
  message?: string;
}

export class EmbedClient {
  private readonly http: AxiosInstance;
  private failureCount = 0;
  private circuitOpenedAt: number | null = null;
  private readonly idTokenAudience?: string;

  constructor(private readonly config: EmbedServiceConfig, private readonly logger: Logger) {
    this.http = axios.create({
      baseURL: config.baseUrl,
      timeout: config.timeoutMs,
      headers: {
        'Content-Type': 'application/json'
      }
    });
    this.idTokenAudience = config.idTokenAudience;
  }

  async generateEmbedding(options: GenerateEmbeddingOptions): Promise<GenerateEmbeddingResult> {
    const { tenantId, requestId, query, dimensions, metadata } = options;

    if (this.isCircuitOpen()) {
      this.logger.warn(
        {
          event: 'embed.circuit_short_circuit',
          failureCount: this.failureCount,
          cooldownMs: this.config.circuitBreakerCooldownMs
        },
        'Embedding circuit breaker is open; skipping downstream call.'
      );
      throw new Error('Embedding circuit breaker is open');
    }

    const headers: Record<string, string> = {
      'X-Tenant-ID': tenantId,
      'X-Request-ID': requestId
    };

    const authHeader = await this.resolveAuthHeader();
    if (authHeader) {
      headers.Authorization = authHeader;
    }

    const payload: Record<string, unknown> = {
      text: query
    };

    if (dimensions) {
      payload.dimensions = dimensions;
    }

    if (metadata) {
      payload.metadata = metadata;
    }

    const attempts = Math.max(1, this.config.retries + 1);
    let lastError: unknown;

    for (let attempt = 1; attempt <= attempts; attempt += 1) {
      const started = Date.now();
      try {
        const response = await this.http.post('/v1/embeddings/generate', payload, { headers });
        const latencyMs = Date.now() - started;
        const data = response.data as Record<string, unknown>;
        const embedding = data.embedding as number[] | undefined;
        const provider = (data.provider as string | undefined) ?? 'unknown';
        const model = (data.model as string | undefined) ?? 'unknown';
        const dims = Number(data.dimensions ?? embedding?.length ?? 0);

        if (!Array.isArray(embedding) || embedding.length === 0) {
          throw new Error('Embedding service returned an empty embedding.');
        }

        this.resetCircuit();

        return {
          embedding,
          provider,
          model,
          dimensions: Number.isFinite(dims) && dims > 0 ? dims : embedding.length,
          latencyMs
        } satisfies GenerateEmbeddingResult;
      } catch (error) {
        lastError = error;
        this.recordFailure(error);
        const delay = this.config.retryDelayMs * attempt;
        this.logger.warn({ attempt, error }, 'Embedding generation failed.');
        if (attempt >= attempts) {
          break;
        }
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }

    throw lastError instanceof Error ? lastError : new Error('Failed to generate embedding.');
  }

  async healthCheck(tenantId?: string): Promise<EmbedHealthStatus> {
    const headers: Record<string, string> = {
      'X-Request-ID': `health-${Date.now()}`
    };

    const resolvedTenant = tenantId ?? this.config.healthTenantId;

    if (resolvedTenant) {
      headers['X-Tenant-ID'] = resolvedTenant;
    }

    const authHeader = await this.resolveAuthHeader();
    if (authHeader) {
      headers.Authorization = authHeader;
    }

    const start = Date.now();
    try {
      const response = await this.http.get('/health', { headers });
      const latency = Date.now() - start;
      if (response.status >= 200 && response.status < 300) {
        return { status: 'healthy', latencyMs: latency } satisfies EmbedHealthStatus;
      }

      return {
        status: 'degraded',
        latencyMs: latency,
        message: `Unexpected status ${response.status}`
      } satisfies EmbedHealthStatus;
    } catch (error) {
      this.logger.error({ error }, 'Embedding service health check failed.');
      return {
        status: 'unavailable',
        message: error instanceof Error ? error.message : 'Unknown error'
      } satisfies EmbedHealthStatus;
    }
  }

  private async resolveAuthHeader(): Promise<string | undefined> {
    if (this.config.authToken) {
      return `Bearer ${this.config.authToken}`;
    }

    if (!this.idTokenAudience) {
      return undefined;
    }

    try {
      const token = await getIdTokenManager().getToken(this.idTokenAudience);
      return `Bearer ${token}`;
    } catch (error) {
      this.logger.error({ error }, 'Failed to acquire ID token for embed service.');
      throw error instanceof Error ? error : new Error('Failed to acquire ID token');
    }
  }

  private isCircuitOpen(): boolean {
    if (this.circuitOpenedAt === null) {
      return false;
    }

    if (Date.now() - this.circuitOpenedAt >= this.config.circuitBreakerCooldownMs) {
      this.circuitOpenedAt = null;
      this.failureCount = 0;
      return false;
    }

    return true;
  }

  private resetCircuit(): void {
    this.failureCount = 0;
    this.circuitOpenedAt = null;
  }

  private recordFailure(error: unknown): void {
    this.failureCount += 1;

    if (this.failureCount >= this.config.circuitBreakerFailures) {
      if (this.circuitOpenedAt === null) {
        this.circuitOpenedAt = Date.now();
        this.logger.error(
          { event: 'embed.circuit_opened', failureCount: this.failureCount, error },
          'Embedding circuit breaker opened after consecutive failures.'
        );
      }
    } else {
      this.logger.debug(
        { event: 'embed.circuit_failure', failureCount: this.failureCount, error },
        'Embedding request failure recorded.'
      );
    }
  }
}
