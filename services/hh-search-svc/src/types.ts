import type { AuthenticatedUser, TenantContext } from '@hh/common';

export type EmbeddingVector = number[];

export interface HybridSearchFilters {
  locations?: string[];
  countries?: string[];
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
  score: number;           // Primary score (RRF score when enabled, hybrid score otherwise)
  vectorScore: number;
  textScore: number;
  rrfScore?: number;       // Explicit RRF score when RRF is enabled
  vectorRank?: number;     // Rank position in vector search results (1-based)
  textRank?: number;       // Rank position in text search results (1-based)
  confidence: number;
  fullName?: string;
  title?: string;
  location?: string;
  country?: string;
  headline?: string;
  skills?: CandidateSkillMatch[];
  industries?: string[];
  yearsExperience?: number;
  matchReasons: string[];
  metadata?: Record<string, unknown>;
  compliance?: {
    legalBasis?: string | null;
    consentRecord?: string | null;
    transferMechanism?: string | null;
  };
}

export interface HybridSearchTimings {
  totalMs: number;
  embeddingMs?: number;
  retrievalMs?: number;
  rankingMs?: number;
  cacheMs?: number;
  rerankMs?: number;
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
  country?: string | null;
  industries?: string[] | null;
  skills?: string[] | null;
  years_experience?: number | null;
  analysis_confidence?: number | null;
  profile?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  legal_basis?: string | null;
  consent_record?: string | null;
  transfer_mechanism?: string | null;
  vector_score: number | null;
  text_score: number | null;
  vector_rank?: number | null;  // Rank position in vector search results (for RRF)
  text_rank?: number | null;    // Rank position in text search results (for RRF)
  rrf_score?: number | null;    // RRF fusion score: 1/(k+vector_rank) + 1/(k+text_rank)
  hybrid_score: number | null;  // When RRF enabled, this equals rrf_score for backward compatibility
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
