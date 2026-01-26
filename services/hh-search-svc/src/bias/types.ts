/**
 * Anonymization types for BIAS-01: Resume anonymization toggle
 *
 * Enables blind hiring workflows by stripping PII and demographic proxies
 * from search results, leaving only job-relevant qualifications.
 */

/**
 * Configuration for what fields to anonymize.
 * Separates PII (always strip) from proxy fields (configurable).
 */
export interface AnonymizationConfig {
  /** Fields containing direct PII - always stripped */
  piiFields: string[];

  /** Fields that may reveal demographics (location, school) - configurable */
  proxyFields: string[];

  /** Fields to always preserve (skills, experience, scores) */
  preserveFields: string[];

  /** Whether to strip proxy fields (e.g., location) in addition to PII */
  stripProxyFields?: boolean;
}

/**
 * Anonymized candidate with PII stripped.
 * Preserves only qualification-relevant data.
 */
export interface AnonymizedCandidate {
  /** Preserved for tracking and selection logging */
  candidateId: string;

  /** Final match score */
  score: number;

  /** Vector similarity score */
  vectorScore: number;

  /** Text search score */
  textScore: number;

  /** RRF score if enabled */
  rrfScore?: number;

  /** Confidence in match */
  confidence: number;

  /** Years of experience - job-relevant */
  yearsExperience?: number;

  /** Skills with match weights - job-relevant */
  skills?: Array<{ name: string; weight: number }>;

  /** Industry experience - job-relevant */
  industries?: string[];

  /** Match reasons (anonymized) */
  matchReasons: string[];

  /** Signal scores breakdown */
  signalScores?: {
    vectorSimilarity: number;
    levelMatch: number;
    specialtyMatch: number;
    techStackMatch: number;
    functionMatch: number;
    trajectoryFit: number;
    // Note: companyPedigree excluded - may be proxy
    skillsExactMatch?: number;
    skillsInferred?: number;
    seniorityAlignment?: number;
    recencyBoost?: number;
  };

  /** Weights applied for transparency */
  weightsApplied?: Record<string, number>;

  /** ML trajectory (if enabled) - role/tenure predictions */
  mlTrajectory?: {
    nextRole: string;
    nextRoleConfidence: number;
    tenureMonths: { min: number; max: number };
    hireability: number;
    lowConfidence: boolean;
    uncertaintyReason?: string;
  };

  /** Anonymization applied indicator */
  anonymized: true;
}

/**
 * Anonymized search response with all candidates stripped of PII.
 */
export interface AnonymizedSearchResponse {
  /** Anonymized candidate results */
  results: AnonymizedCandidate[];

  /** Total number of candidates found */
  total: number;

  /** Whether result came from cache */
  cacheHit: boolean;

  /** Request ID for tracking */
  requestId: string;

  /** Timing information */
  timings: {
    totalMs: number;
    embeddingMs?: number;
    retrievalMs?: number;
    rankingMs?: number;
    cacheMs?: number;
    rerankMs?: number;
    nlpMs?: number;
  };

  /** Anonymization metadata */
  metadata: {
    anonymized: true;
    anonymizedAt: string;
  };
}

/**
 * Default anonymization configuration.
 * Based on proxy variable audit in 14-RESEARCH.md.
 */
export const DEFAULT_ANONYMIZATION_CONFIG: AnonymizationConfig = {
  // Direct PII - always strip
  piiFields: [
    'fullName',
    'title', // May contain identifying info
    'headline', // Often contains name/company
    'location', // HIGH risk proxy
    'country', // HIGH risk proxy
    'metadata', // May contain anything
  ],

  // Demographic proxies - strip when stripProxyFields=true
  proxyFields: [
    'educationInstitutions', // HIGH risk - reveals socioeconomic/race
    'graduationYear', // HIGH risk - reveals age
    'companyPedigree', // MEDIUM risk - correlates with demographics
  ],

  // Always preserve - job-relevant qualifications
  preserveFields: [
    'candidateId',
    'score',
    'vectorScore',
    'textScore',
    'rrfScore',
    'confidence',
    'yearsExperience',
    'skills',
    'industries',
    'matchReasons',
    'signalScores',
    'weightsApplied',
    'mlTrajectory',
  ],

  // Default: also strip proxy fields for full anonymization
  stripProxyFields: true,
};

// ============================================================================
// Slate Diversity Types for BIAS-05
// ============================================================================

/**
 * Diversity dimension for slate analysis.
 */
export type DiversityDimension = 'companyTier' | 'experienceBand' | 'specialty';

/**
 * Distribution of candidates across a dimension.
 */
export interface DimensionDistribution {
  /** The dimension being analyzed */
  dimension: DiversityDimension;

  /** Count of candidates per group value */
  distribution: Record<string, number>;

  /** The dominant group (highest count) */
  dominantGroup: string;

  /** Concentration percentage (dominant group / total) */
  concentrationPct: number;

  /** Whether concentration exceeds warning threshold */
  isConcentrated: boolean;
}

/**
 * Warning about slate homogeneity.
 */
export interface DiversityWarning {
  /** Severity level */
  level: 'info' | 'warning' | 'alert';

  /** Human-readable message */
  message: string;

  /** The dimension with concentration issue */
  dimension: DiversityDimension;

  /** Concentration percentage */
  concentrationPct: number;

  /** Suggested action */
  suggestion: string;
}

/**
 * Complete slate diversity analysis.
 */
export interface SlateDiversityAnalysis {
  /** Total candidates analyzed */
  totalCandidates: number;

  /** Distribution per dimension */
  dimensions: DimensionDistribution[];

  /** Generated warnings */
  warnings: DiversityWarning[];

  /** Summary diversity score (0-100, higher = more diverse) */
  diversityScore: number;

  /** Whether any dimension has concentration warning */
  hasConcentrationIssue: boolean;
}

/**
 * Configuration for diversity analysis.
 */
export interface DiversityConfig {
  /** Concentration threshold for warnings (default: 0.70 = 70%) */
  concentrationThreshold: number;

  /** Minimum candidates to analyze (skip if fewer) */
  minCandidates: number;

  /** Dimensions to analyze */
  dimensions: DiversityDimension[];
}

/**
 * Default diversity configuration.
 */
export const DEFAULT_DIVERSITY_CONFIG: DiversityConfig = {
  concentrationThreshold: 0.70,  // 70% triggers warning
  minCandidates: 5,              // Need at least 5 to analyze
  dimensions: ['companyTier', 'experienceBand', 'specialty'],
};
