import type { AuthenticatedUser, TenantContext } from '@hh/common';

export type EmbeddingVector = number[];

export interface HybridSearchFilters {
  locations?: string[];
  skills?: string[];
  industries?: string[];
  seniorityLevels?: string[];
  minExperienceYears?: number;
  maxExperienceYears?: number;
  metadata?: Record<string, unknown>;
}

export interface HybridSearchRequest {
  query?: string;
  embedding?: EmbeddingVector;
  jdHash?: string;
  jobDescription?: string;
  filters?: HybridSearchFilters;
  limit?: number;
  offset?: number;
  includeDebug?: boolean;
}

export interface CandidateSkillMatch {
  name: string;
  weight: number;
}

export interface HybridSearchResultItem {
  candidateId: string;
  score: number;
  vectorScore: number;
  textScore: number;
  confidence: number;
  fullName?: string;
  title?: string;
  location?: string;
  headline?: string;
  skills?: CandidateSkillMatch[];
  industries?: string[];
  yearsExperience?: number;
  matchReasons: string[];
  metadata?: Record<string, unknown>;
}

export interface HybridSearchTimings {
  totalMs: number;
  embeddingMs?: number;
  retrievalMs?: number;
  rankingMs?: number;
  cacheMs?: number;
}

export interface HybridSearchResponse {
  results: HybridSearchResultItem[];
  total: number;
  cacheHit: boolean;
  requestId: string;
  timings: HybridSearchTimings;
  metadata?: Record<string, unknown>;
  debug?: Record<string, unknown>;
}

export interface SearchContext {
  tenant: TenantContext;
  user?: AuthenticatedUser;
  requestId: string;
}

export interface PgHybridSearchRow {
  candidate_id: string;
  full_name?: string | null;
  current_title?: string | null;
  headline?: string | null;
  location?: string | null;
  industries?: string[] | null;
  skills?: string[] | null;
  years_experience?: number | null;
  analysis_confidence?: number | null;
  profile?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  vector_score: number | null;
  text_score: number | null;
  hybrid_score: number | null;
  updated_at?: string | null;
}

export interface FirestoreCandidateRecord {
  candidate_id: string;
  full_name?: string;
  current_title?: string;
  headline?: string;
  location?: string;
  industries?: string[];
  skills?: string[];
  years_experience?: number;
  analysis_confidence?: number;
  metadata?: Record<string, unknown>;
}
