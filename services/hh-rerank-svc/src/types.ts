import type { AuthenticatedUser, TenantContext } from '@hh/common';

export interface RerankCandidateFeatures {
  vectorScore?: number;
  textScore?: number;
  confidence?: number;
  yearsExperience?: number;
  currentTitle?: string;
  location?: string;
  matchReasons?: string[];
  skills?: string[];
  metadata?: Record<string, unknown>;
}

export interface RerankCandidate {
  candidateId: string;
  summary?: string;
  highlights?: string[];
  initialScore?: number;
  features?: RerankCandidateFeatures;
  payload?: Record<string, unknown>;
}

export interface RerankRequest {
  jobDescription: string;
  jdHash?: string;
  docsetHash?: string;
  query?: string;
  candidates: RerankCandidate[];
  limit?: number;
  disableCache?: boolean;
  includeReasons?: boolean;
  requestMetadata?: Record<string, unknown>;
}

export interface RerankTimingBreakdown {
  totalMs: number;
  togetherMs?: number;
  geminiMs?: number;
  promptMs?: number;
  cacheMs?: number;
}

export interface RerankResult {
  candidateId: string;
  rank: number;
  score: number;
  reasons: string[];
  summary?: string;
  payload?: Record<string, unknown>;
}

export interface RerankResponse {
  results: RerankResult[];
  cacheHit: boolean;
  usedFallback: boolean;
  requestId: string;
  timings: RerankTimingBreakdown;
  metadata?: Record<string, unknown>;
}

export interface RerankContext {
  tenant: TenantContext;
  user?: AuthenticatedUser;
  requestId: string;
}

export interface TogetherRerankCandidate {
  id: string;
  content: string;
}

export interface TogetherChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface TogetherChatCompletionRequestPayload {
  model: string;
  messages: TogetherChatMessage[];
  temperature: number;
  max_tokens: number;
  response_format?: { type: string };
  user?: string;
  context?: Record<string, unknown>;
}

export interface TogetherChatCompletionChoice {
  index?: number;
  finish_reason?: string;
  message: {
    role: string;
    content: string;
  };
}

export interface TogetherChatCompletionResponsePayload {
  id?: string;
  choices: TogetherChatCompletionChoice[];
  usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface RerankCacheDescriptor {
  jdHash: string;
  docsetHash: string;
}
