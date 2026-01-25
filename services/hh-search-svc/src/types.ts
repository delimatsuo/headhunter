import type { AuthenticatedUser, TenantContext } from '@hh/common';
import type { SignalWeightConfig, RoleType } from './signal-weights';

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

  /**
   * Override signal weights for this search.
   * If not provided, role-type defaults are used.
   * Weights should sum to 1.0 (will be normalized if not).
   */
  signalWeights?: Partial<SignalWeightConfig>;

  /**
   * Role type for weight preset selection.
   * Options: 'executive', 'manager', 'ic', 'default'
   * If not provided, defaults to 'default'.
   */
  roleType?: RoleType;

  /**
   * Whether to generate LLM match rationale for top candidates.
   * @see TRNS-03
   */
  includeMatchRationale?: boolean;

  /**
   * Maximum number of candidates to generate rationale for.
   * Defaults to 10.
   */
  rationaleLimit?: number;
}

export interface CandidateSkillMatch {
  name: string;
  weight: number;
}

/**
 * Individual signal scores (0-1 normalized) contributing to final weighted score.
 * These represent the multi-signal scoring framework's component scores.
 */
export interface SignalScores {
  /** Vector similarity from hybrid search (0-1 normalized) */
  vectorSimilarity: number;

  /** Level/seniority match alignment (0-1) */
  levelMatch: number;

  /** Specialty match score (0-1) - backend, frontend, fullstack, etc */
  specialtyMatch: number;

  /** Tech stack compatibility score (0-1) */
  techStackMatch: number;

  /** Function alignment score (0-1) - engineering, product, design, etc */
  functionMatch: number;

  /** Career trajectory fit score (0-1) */
  trajectoryFit: number;

  /** Company pedigree score (0-1) */
  companyPedigree: number;

  /** Skills match score (0-1) - for skill-aware searches, optional */
  skillsMatch?: number;

  // ===== PHASE 7 SIGNALS (all 0-1 normalized, optional) =====

  /** SCOR-02: Skills exact match score (0-1) */
  skillsExactMatch?: number;

  /** SCOR-03: Skills inferred score (0-1) */
  skillsInferred?: number;

  /** SCOR-04: Seniority alignment score (0-1) */
  seniorityAlignment?: number;

  /** SCOR-05: Recency boost score (0-1) */
  recencyBoost?: number;

  /** SCOR-06: Company relevance score (0-1) */
  companyRelevance?: number;
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

  /**
   * Individual signal scores (0-1 normalized) contributing to final score.
   * Only present when signal scoring is enabled.
   */
  signalScores?: SignalScores;

  /**
   * The signal weights that were applied to compute the score.
   * Useful for transparency and debugging.
   */
  weightsApplied?: SignalWeightConfig;

  /**
   * Which role type preset was used for scoring.
   */
  roleTypeUsed?: RoleType;

  /**
   * LLM-generated match rationale (only for top candidates).
   * @see TRNS-03
   */
  matchRationale?: MatchRationale;
}

export interface HybridSearchTimings {
  totalMs: number;
  embeddingMs?: number;
  retrievalMs?: number;
  rankingMs?: number;
  cacheMs?: number;
  rerankMs?: number;
}

/**
 * Pipeline stage metrics for debugging and SLO tracking.
 * @see PIPE-01: 3-stage pipeline logging requirement
 */
export interface PipelineStageMetrics {
  /** Stage 1: Retrieval - candidates returned from hybrid search */
  retrievalCount: number;
  retrievalMs: number;

  /** Stage 2: Scoring - candidates after signal weighting and cutoff */
  scoringCount: number;
  scoringMs: number;

  /** Stage 3: Reranking - final candidates after LLM rerank */
  rerankCount: number;
  rerankMs: number;

  /** Whether LLM reranking was applied (vs passthrough) */
  rerankApplied: boolean;

  /** Total pipeline latency */
  totalMs: number;
}

export interface HybridSearchResponse {
  results: HybridSearchResultItem[];
  total: number;
  cacheHit: boolean;
  requestId: string;
  timings: HybridSearchTimings;
  metadata?: Record<string, unknown>;
  debug?: Record<string, unknown>;
  /** Pipeline execution metrics for stage debugging */
  pipelineMetrics?: PipelineStageMetrics;
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

/**
 * LLM-generated match rationale for top candidates.
 * Explains why a candidate is a good fit for the role.
 * @see TRNS-03
 */
export interface MatchRationale {
  /** 2-3 sentence summary of why candidate matches */
  summary: string;
  /** Top 2-3 key strengths */
  keyStrengths: string[];
  /** Which signals drove the match */
  signalHighlights: Array<{
    signal: string;
    score: number;
    reason: string;
  }>;
}
