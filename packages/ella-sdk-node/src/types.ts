export interface RetryOptions {
  retries?: number;
  factor?: number;
  minTimeoutMs?: number;
  maxTimeoutMs?: number;
}

export interface GatewayLogEvent {
  type: 'request' | 'response' | 'error';
  method: string;
  path: string;
  durationMs?: number;
  status?: number;
  requestId?: string;
  message?: string;
  metadata?: Record<string, unknown>;
}

export interface RateLimitInfo {
  limit?: number;
  remaining?: number;
  reset?: number;
}

export interface GatewayResponse<T> {
  data: T;
  rateLimit?: RateLimitInfo;
  correlationId?: string;
  traceId?: string;
}

export interface RequestOptions {
  requestId?: string;
  traceId?: string;
  signal?: AbortSignal;
  retry?: RetryOptions;
}

export interface EllaGatewayClientOptions {
  baseUrl: string;
  tenantId: string;
  clientId: string;
  clientSecret: string;
  audience?: string;
  tokenEndpoint?: string;
  fetch?: typeof fetch;
  requestTimeoutMs?: number;
  retry?: RetryOptions;
  logger?: (event: GatewayLogEvent) => void;
  tokenCacheOffsetSeconds?: number;
}

export interface ErrorResponse {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface EmbeddingsInput {
  id: string;
  text: string;
  metadata?: Record<string, unknown>;
}

export interface EmbeddingsBatchRequest {
  inputs: EmbeddingsInput[];
  model?: string;
  tenantContext?: TenantContext;
}

export interface EmbeddingsBatchResponse {
  jobId: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  submittedAt?: string;
}

export interface EmbeddingsStatusResponse {
  jobId: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  completedAt?: string;
  error?: ErrorResponse;
}

export interface HybridSearchRequest {
  query: string;
  filters?: Record<string, unknown>;
  rerank?: boolean;
  pageSize?: number;
  pageToken?: string;
}

export interface HybridSearchResult {
  id: string;
  score: number;
  metadata?: Record<string, unknown>;
}

export interface HybridSearchResponse {
  results: HybridSearchResult[];
  nextPageToken?: string;
}

export interface RerankCandidate {
  id: string;
  text: string;
  metadata?: Record<string, unknown>;
}

export interface RerankRequest {
  query: string;
  candidates: RerankCandidate[];
}

export interface RerankResult {
  id: string;
  score: number;
  metadata?: Record<string, unknown>;
}

export interface RerankResponse {
  results: RerankResult[];
}

export interface EvidenceDocument {
  id: string;
  title?: string;
  summary?: string;
  source?: string;
  createdAt?: string;
  metadata?: Record<string, unknown>;
}

export interface EvidenceListResponse {
  documents: EvidenceDocument[];
  nextPageToken?: string;
}

export interface ListRequest {
  pageSize?: number;
  pageToken?: string;
}

export interface OccupationResponse {
  id: string;
  title: string;
  description?: string;
  skills?: string[];
}

export interface OccupationListResponse {
  occupations: OccupationResponse[];
  nextPageToken?: string;
}

export type OccupationDetail = OccupationResponse;

export interface SkillRecord {
  id: string;
  name: string;
  category?: string;
}

export interface SkillsListResponse {
  skills: SkillRecord[];
  nextPageToken?: string;
}

export interface MarketInsightsRequest {
  region: string;
  role: string;
  metrics?: string[];
  horizonMonths?: number;
}

export interface MarketInsightsMetric {
  name: string;
  value: number;
  unit?: string;
}

export interface MarketInsightsResponse {
  role: string;
  summary?: string;
  metrics: MarketInsightsMetric[];
}

export interface RoleRecommendationRequest {
  profileId: string;
  context?: Record<string, unknown>;
}

export interface RoleRecommendation {
  roleId: string;
  score: number;
  rationale?: string;
}

export interface RoleRecommendationResponse {
  recommendations: RoleRecommendation[];
}

export interface TenantContext {
  id: string;
  name?: string;
  isActive?: boolean;
  rawRecord?: Record<string, unknown>;
  quota?: Record<string, number>;
}

export interface AdminTenantListResponse {
  tenants: TenantContext[];
}

export type Json = Record<string, unknown> | Array<unknown> | string | number | boolean | null;
