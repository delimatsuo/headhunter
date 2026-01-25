import axios, { type AxiosInstance } from 'axios';
import type { Logger } from 'pino';
import { getIdTokenManager } from '@hh/common';

export interface RerankServiceConfig {
  baseUrl: string;
  timeoutMs: number;
  retries: number;
  retryDelayMs: number;
  idTokenAudience?: string;
  authToken?: string;
  enabled: boolean;
}

export interface RerankCandidateFeatures {
  vectorScore?: number;
  textScore?: number;
  confidence?: number;
  yearsExperience?: number;
  matchReasons?: string[];
  skills?: string[];
  metadata?: Record<string, unknown>;
}

export interface RerankCandidatePayload {
  [key: string]: unknown;
}

export interface RerankCandidate {
  candidateId: string;
  summary?: string;
  highlights?: string[];
  initialScore?: number;
  features?: RerankCandidateFeatures;
  payload?: RerankCandidatePayload;
}

export interface RerankRequest {
  jobDescription: string;
  candidates: RerankCandidate[];
  query?: string;
  limit?: number;
  jdHash?: string;
  docsetHash?: string;
  includeReasons?: boolean;
  disableCache?: boolean;
  requestMetadata?: Record<string, unknown>;
}

export interface RerankResult {
  candidateId: string;
  rank: number;
  score: number;
  reasons: string[];
  summary?: string;
  payload?: Record<string, unknown>;
}

export interface RerankResponseMetadata {
  cacheKey?: string;
  [key: string]: unknown;
}

export interface RerankResponse {
  results: RerankResult[];
  cacheHit: boolean;
  usedFallback: boolean;
  requestId: string;
  timings: {
    totalMs: number;
    togetherMs?: number;
    promptMs?: number;
    cacheMs?: number;
  };
  metadata?: RerankResponseMetadata;
}

export interface RerankHealthStatus {
  status: 'healthy' | 'degraded' | 'disabled' | 'unavailable';
  message?: string;
  latencyMs?: number;
}

/**
 * LLM-generated match rationale for top candidates.
 * @see TRNS-03
 */
export interface MatchRationale {
  summary: string;
  keyStrengths: string[];
  signalHighlights: Array<{
    signal: string;
    score: number;
    reason: string;
  }>;
}

export interface MatchRationaleRequest {
  jobDescription: string;
  candidateSummary: string;
  topSignals: Array<{ name: string; score: number }>;
}

export class RerankClient {
  private readonly http: AxiosInstance;
  private failureCount = 0;

  constructor(private readonly config: RerankServiceConfig, private readonly logger: Logger) {
    this.http = axios.create({
      baseURL: config.baseUrl,
      timeout: config.timeoutMs,
      headers: {
        'Content-Type': 'application/json'
      }
    });
  }

  isEnabled(): boolean {
    return this.config.enabled;
  }

  async rerank(request: RerankRequest, context: { tenantId: string; requestId: string }): Promise<RerankResponse> {
    if (!this.config.enabled) {
      throw new Error('Rerank client is disabled.');
    }

    const headers: Record<string, string> = {
      'X-Tenant-ID': context.tenantId,
      'X-Request-ID': context.requestId
    };

    const authHeader = await this.resolveAuthHeader();
    if (authHeader) {
      headers.Authorization = authHeader;
    }

    const attempts = Math.max(1, this.config.retries + 1);
    let lastError: unknown;

    for (let attempt = 1; attempt <= attempts; attempt += 1) {
      const started = Date.now();
      try {
        const response = await this.http.post<RerankResponse>('/v1/search/rerank', request, { headers });
        const latency = Date.now() - started;

        this.logger.info({ requestId: context.requestId, latencyMs: latency }, 'Rerank request completed.');
        this.resetCircuit();
        return response.data;
      } catch (error) {
        lastError = error;
        this.recordFailure(error);
        this.logger.warn({ attempt, error }, 'Rerank request failed.');
        if (attempt >= attempts) {
          break;
        }
        const backoff = this.config.retryDelayMs * attempt;
        await new Promise((resolve) => setTimeout(resolve, backoff));
      }
    }

    throw lastError instanceof Error ? lastError : new Error('Failed to call rerank service.');
  }

  async healthCheck(tenantId?: string): Promise<RerankHealthStatus> {
    if (!this.config.enabled) {
      return { status: 'disabled', message: 'Rerank disabled via configuration.' } satisfies RerankHealthStatus;
    }

    const headers: Record<string, string> = {
      'X-Request-ID': `rerank-health-${Date.now()}`
    };

    if (tenantId) {
      headers['X-Tenant-ID'] = tenantId;
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
        return { status: 'healthy', latencyMs: latency } satisfies RerankHealthStatus;
      }
      return {
        status: 'degraded',
        latencyMs: latency,
        message: `Unexpected status ${response.status}`
      } satisfies RerankHealthStatus;
    } catch (error) {
      this.logger.error({ error }, 'Rerank health check failed.');
      return {
        status: 'unavailable',
        message: error instanceof Error ? error.message : 'Unknown error'
      } satisfies RerankHealthStatus;
    }
  }

  private async resolveAuthHeader(): Promise<string | undefined> {
    if (this.config.authToken) {
      return `Bearer ${this.config.authToken}`;
    }

    if (!this.config.idTokenAudience) {
      return undefined;
    }

    try {
      const token = await getIdTokenManager().getToken(this.config.idTokenAudience);
      return `Bearer ${token}`;
    } catch (error) {
      this.logger.error({ error }, 'Failed to acquire ID token for rerank service.');
      throw error instanceof Error ? error : new Error('Failed to acquire rerank ID token');
    }
  }

  private recordFailure(error: unknown): void {
    this.failureCount += 1;
    this.logger.warn({ error, failureCount: this.failureCount }, 'Rerank client failure recorded.');
  }

  private resetCircuit(): void {
    this.failureCount = 0;
  }

  /**
   * Generate LLM match rationale for a candidate.
   * @see TRNS-03
   */
  async generateMatchRationale(
    request: MatchRationaleRequest,
    context: { tenantId: string; requestId: string }
  ): Promise<MatchRationale> {
    const fallbackRationale: MatchRationale = {
      summary: 'Match analysis unavailable.',
      keyStrengths: [],
      signalHighlights: []
    };

    if (!this.config.enabled) {
      return fallbackRationale;
    }

    const headers: Record<string, string> = {
      'X-Tenant-ID': context.tenantId,
      'X-Request-ID': context.requestId
    };

    const authHeader = await this.resolveAuthHeader();
    if (authHeader) {
      headers.Authorization = authHeader;
    }

    try {
      const response = await this.http.post<MatchRationale>('/v1/search/rationale', request, {
        headers,
        timeout: 5000 // 5 second timeout for rationale generation
      });

      this.logger.debug({ requestId: context.requestId }, 'Match rationale generated.');
      return response.data;
    } catch (error) {
      this.logger.warn({ error, requestId: context.requestId }, 'Match rationale generation failed.');
      return fallbackRationale;
    }
  }
}
