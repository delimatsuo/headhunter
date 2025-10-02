import { fetch as undiciFetch, Headers as UndiciHeaders } from 'undici';

import type {
  AdminTenantListResponse,
  EllaGatewayClientOptions,
  EmbeddingsBatchRequest,
  EmbeddingsBatchResponse,
  EmbeddingsStatusResponse,
  GatewayLogEvent,
  GatewayResponse,
  HybridSearchRequest,
  HybridSearchResponse,
  ListRequest,
  MarketInsightsRequest,
  MarketInsightsResponse,
  RateLimitInfo,
  RequestOptions,
  RetryOptions,
  RoleRecommendationRequest,
  RoleRecommendationResponse,
  RerankRequest,
  RerankResponse,
  EvidenceListResponse,
  EvidenceDocument,
  OccupationListResponse,
  OccupationDetail,
  SkillsListResponse,
  ErrorResponse
} from './types';

export class GatewayError extends Error {
  public readonly status: number;
  public readonly payload?: ErrorResponse;
  public readonly rateLimit?: RateLimitInfo;
  public readonly requestId?: string | null;
  public readonly traceId?: string | null;

  constructor(message: string, status: number, payload?: ErrorResponse, rateLimit?: RateLimitInfo, headers?: Headers) {
    super(message);
    this.name = 'GatewayError';
    this.status = status;
    this.payload = payload;
    this.rateLimit = rateLimit;
    this.requestId = headers?.get('x-request-id');
    this.traceId = headers?.get('x-cloud-trace-context');
  }
}

interface CachedToken {
  accessToken: string;
  expiresAt: number;
}

interface NormalizedRetrySettings {
  retries: number;
  factor: number;
  minTimeoutMs: number;
  maxTimeoutMs: number;
}

export class EllaGatewayClient {
  private readonly baseUrl: string;
  private readonly tenantId: string;
  private readonly clientId: string;
  private readonly clientSecret: string;
  private readonly audience?: string;
  private readonly tokenEndpoint: string;
  private readonly requestTimeoutMs: number;
  private readonly fetchImpl: typeof fetch;
  private readonly logger?: (event: GatewayLogEvent) => void;
  private readonly defaultRetry: NormalizedRetrySettings;
  private readonly tokenCacheOffsetSeconds: number;

  private cachedToken?: CachedToken;

  constructor(options: EllaGatewayClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, '');
    this.tenantId = options.tenantId;
    this.clientId = options.clientId;
    this.clientSecret = options.clientSecret;
    this.audience = options.audience;
    this.tokenEndpoint = options.tokenEndpoint ?? 'https://idp.ella.jobs/oauth/token';
    this.requestTimeoutMs = options.requestTimeoutMs ?? 15000;
    this.fetchImpl = options.fetch ?? (typeof fetch === 'function' ? fetch.bind(globalThis) : undiciFetch);
    this.logger = options.logger;
    this.tokenCacheOffsetSeconds = options.tokenCacheOffsetSeconds ?? 30;

    const retry = options.retry ?? {};
    this.defaultRetry = {
      retries: retry.retries ?? 2,
      factor: retry.factor ?? 2,
      minTimeoutMs: retry.minTimeoutMs ?? 250,
      maxTimeoutMs: retry.maxTimeoutMs ?? 4000
    };
  }

  public async createEmbeddingsBatch(request: EmbeddingsBatchRequest, options?: RequestOptions): Promise<GatewayResponse<EmbeddingsBatchResponse>> {
    return this.send<EmbeddingsBatchResponse>('POST', '/v1/embeddings/batch', { body: request }, options);
  }

  public async getEmbeddingsStatus(jobId: string, options?: RequestOptions): Promise<GatewayResponse<EmbeddingsStatusResponse>> {
    return this.send<EmbeddingsStatusResponse>('GET', `/v1/embeddings/status/${encodeURIComponent(jobId)}`, undefined, options);
  }

  public async hybridSearch(request: HybridSearchRequest, options?: RequestOptions): Promise<GatewayResponse<HybridSearchResponse>> {
    return this.send<HybridSearchResponse>('POST', '/v1/search/hybrid', { body: request }, options);
  }

  public async rerank(request: RerankRequest, options?: RequestOptions): Promise<GatewayResponse<RerankResponse>> {
    return this.send<RerankResponse>('POST', '/v1/search/rerank', { body: request }, options);
  }

  public async listEvidenceDocuments(params: ListRequest = {}, options?: RequestOptions): Promise<GatewayResponse<EvidenceListResponse>> {
    return this.send<EvidenceListResponse>('GET', '/v1/evidence/documents', { query: params }, options);
  }

  public async getEvidenceDocument(documentId: string, options?: RequestOptions): Promise<GatewayResponse<EvidenceDocument>> {
    return this.send<EvidenceDocument>('GET', `/v1/evidence/documents/${encodeURIComponent(documentId)}`, undefined, options);
  }

  public async listOccupations(params: ListRequest = {}, options?: RequestOptions): Promise<GatewayResponse<OccupationListResponse>> {
    return this.send<OccupationListResponse>('GET', '/v1/occupations', { query: params }, options);
  }

  public async getOccupation(occupationId: string, options?: RequestOptions): Promise<GatewayResponse<OccupationDetail>> {
    return this.send<OccupationDetail>('GET', `/v1/occupations/${encodeURIComponent(occupationId)}`, undefined, options);
  }

  public async listSkills(params: ListRequest = {}, options?: RequestOptions): Promise<GatewayResponse<SkillsListResponse>> {
    return this.send<SkillsListResponse>('GET', '/v1/skills', { query: params }, options);
  }

  public async getMarketInsights(request: MarketInsightsRequest, options?: RequestOptions): Promise<GatewayResponse<MarketInsightsResponse>> {
    return this.send<MarketInsightsResponse>('POST', '/v1/market/insights', { body: request }, options);
  }

  public async getRoleRecommendations(request: RoleRecommendationRequest, options?: RequestOptions): Promise<GatewayResponse<RoleRecommendationResponse>> {
    return this.send<RoleRecommendationResponse>('POST', '/v1/roles/recommendations', { body: request }, options);
  }

  public async listTenants(options?: RequestOptions): Promise<GatewayResponse<AdminTenantListResponse>> {
    return this.send<AdminTenantListResponse>('GET', '/v1/admin/tenants', undefined, options);
  }

  public clearTokenCache(): void {
    this.cachedToken = undefined;
  }

  private async send<T>(
    method: string,
    path: string,
    payload?: { body?: unknown; query?: Record<string, unknown> },
    options: RequestOptions = {}
  ): Promise<GatewayResponse<T>> {
    const url = new URL(path, this.baseUrl.endsWith('/') ? `${this.baseUrl}` : `${this.baseUrl}/`);

    if (payload?.query) {
      for (const [key, value] of Object.entries(payload.query)) {
        if (value === undefined || value === null) {
          continue;
        }
        url.searchParams.set(key, String(value));
      }
    }

    const retries = this.normalizeRetry(options.retry);
    let attempt = 0;
    let lastError: unknown;

    while (attempt <= retries.retries) {
      attempt += 1;
      const start = Date.now();
      try {
        const response = await this.performHttpRequest(method, url, payload?.body, options);
        const rateLimit = this.parseRateLimit(response);

        if (!response.ok) {
          const errorPayload = await this.safeJson(response);
          if (this.shouldRetry(response.status, attempt, retries.retries)) {
            await this.waitWithBackoff(attempt, retries, response.headers.get('retry-after'));
            continue;
          }

          const message = errorPayload?.message || `Request failed with status ${response.status}`;
          throw new GatewayError(message, response.status, errorPayload ?? undefined, rateLimit, response.headers);
        }

        const duration = Date.now() - start;
        this.log({ type: 'response', method, path: url.pathname, status: response.status, durationMs: duration, requestId: response.headers.get('x-request-id') ?? options.requestId ?? undefined });

        let data: T;
        if (response.status === 204) {
          data = undefined as unknown as T;
        } else if (response.headers.get('content-type')?.includes('application/json')) {
          data = (await response.json()) as T;
        } else {
          data = undefined as unknown as T;
        }

        return {
          data,
          rateLimit,
          correlationId: response.headers.get('x-request-id') ?? undefined,
          traceId: response.headers.get('x-cloud-trace-context') ?? undefined
        };
      } catch (error) {
        lastError = error;
        if (error instanceof GatewayError) {
          throw error;
        }

        if (attempt > retries.retries) {
          break;
        }

        await this.waitWithBackoff(attempt, retries);
      }
    }

    if (lastError instanceof Error) {
      throw lastError;
    }

    throw new Error('Request failed without explicit error');
  }

  private async performHttpRequest(method: string, url: URL, body?: unknown, options: RequestOptions = {}) {
    const accessToken = await this.getAccessToken();
    const HeadersCtor = typeof Headers !== 'undefined' ? Headers : UndiciHeaders;
    const headers = new HeadersCtor({
      Authorization: `Bearer ${accessToken}`,
      'X-Tenant-ID': this.tenantId,
      Accept: 'application/json'
    });

    if (body !== undefined) {
      headers.set('Content-Type', 'application/json');
    }

    if (options.requestId) {
      headers.set('X-Request-ID', options.requestId);
    }

    if (options.traceId) {
      headers.set('X-Cloud-Trace-Context', options.traceId);
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.requestTimeoutMs);

    this.log({ type: 'request', method, path: url.pathname, requestId: options.requestId });

    try {
      return await this.fetchImpl(url.toString(), {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: options.signal ?? controller.signal
      });
    } finally {
      clearTimeout(timeout);
    }
  }

  private async getAccessToken(): Promise<string> {
    if (this.cachedToken && Date.now() < this.cachedToken.expiresAt) {
      return this.cachedToken.accessToken;
    }

    const params = new URLSearchParams({
      grant_type: 'client_credentials',
      client_id: this.clientId,
      client_secret: this.clientSecret
    });

    if (this.audience) {
      params.append('audience', this.audience);
    }

    const response = await this.fetchImpl(this.tokenEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: params.toString()
    });

    const payload = await response.json();
    if (!response.ok) {
      const message = payload?.error_description || payload?.error || 'Failed to obtain access token';
      throw new Error(message);
    }

    if (typeof payload.token_type === 'string' && payload.token_type.toLowerCase() !== 'bearer') {
      throw new Error(`Unsupported token type: ${payload.token_type}`);
    }

    const expiresIn = typeof payload.expires_in === 'number' ? payload.expires_in : 3600;
    const cacheOffset = this.tokenCacheOffsetSeconds;
    this.cachedToken = {
      accessToken: payload.access_token,
      expiresAt: Date.now() + Math.max(expiresIn - cacheOffset, 15) * 1000
    };

    return payload.access_token as string;
  }

  private parseRateLimit(response: Response): RateLimitInfo {
    const headers = response.headers;
    const limit = this.parseHeaderNumber(headers, 'ratelimit-limit');
    const remaining = this.parseHeaderNumber(headers, 'ratelimit-remaining');
    const reset = this.parseHeaderNumber(headers, 'ratelimit-reset');

    return { limit: limit ?? undefined, remaining: remaining ?? undefined, reset: reset ?? undefined };
  }

  private parseHeaderNumber(headers: Headers, name: string): number | null {
    const value = headers.get(name) ?? headers.get(name.toLowerCase()) ?? headers.get(name.replace(/(^.|-.?)/g, (segment) => segment.toUpperCase()));
    if (!value) {
      return null;
    }

    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  private async safeJson(response: Response): Promise<ErrorResponse | undefined> {
    try {
      if (!response.headers.get('content-type')?.includes('application/json')) {
        return undefined;
      }
      return (await response.json()) as ErrorResponse;
    } catch (error) {
      this.log({ type: 'error', method: response.url, path: response.url, status: response.status, message: String(error) });
      return undefined;
    }
  }

  private async waitWithBackoff(attempt: number, settings: NormalizedRetrySettings, retryAfterHeader?: string | null): Promise<void> {
    let delayMs = settings.minTimeoutMs * Math.pow(settings.factor, attempt - 1);
    if (retryAfterHeader) {
      const retryAfterSeconds = Number(retryAfterHeader);
      if (Number.isFinite(retryAfterSeconds)) {
        delayMs = Math.max(delayMs, retryAfterSeconds * 1000);
      }
    }

    delayMs = Math.min(delayMs, settings.maxTimeoutMs);
    await new Promise((resolve) => setTimeout(resolve, delayMs));
  }

  private shouldRetry(status: number, attempt: number, maxRetries: number): boolean {
    if (attempt > maxRetries) {
      return false;
    }

    if (status === 429) {
      return true;
    }

    return status >= 500;
  }

  private normalizeRetry(retry?: RetryOptions): NormalizedRetrySettings {
    if (!retry) {
      return this.defaultRetry;
    }

    return {
      retries: retry.retries ?? this.defaultRetry.retries,
      factor: retry.factor ?? this.defaultRetry.factor,
      minTimeoutMs: retry.minTimeoutMs ?? this.defaultRetry.minTimeoutMs,
      maxTimeoutMs: retry.maxTimeoutMs ?? this.defaultRetry.maxTimeoutMs
    };
  }

  private log(event: GatewayLogEvent): void {
    if (!this.logger) {
      return;
    }

    try {
      this.logger(event);
    } catch (error) {
      // Suppress logger errors so they do not disrupt SDK consumers.
    }
  }
}

export type {
  EllaGatewayClientOptions,
  EmbeddingsBatchRequest,
  EmbeddingsBatchResponse,
  EmbeddingsStatusResponse,
  HybridSearchRequest,
  HybridSearchResponse,
  RerankRequest,
  RerankResponse,
  EvidenceListResponse,
  EvidenceDocument,
  ListRequest,
  OccupationListResponse,
  OccupationDetail,
  SkillsListResponse,
  MarketInsightsRequest,
  MarketInsightsResponse,
  RoleRecommendationRequest,
  RoleRecommendationResponse,
  AdminTenantListResponse,
  GatewayResponse,
  RateLimitInfo,
  GatewayLogEvent,
  RequestOptions,
  RetryOptions,
  ErrorResponse
} from './types';
