/**
 * Scoring Utilities for Multi-Signal Framework
 *
 * This module provides computation utilities for the multi-signal scoring system.
 * It computes weighted combinations of individual signals (vector similarity, level match,
 * specialty match, etc.) to produce a final candidate relevance score.
 *
 * @module scoring
 */

import type { SignalWeightConfig } from './signal-weights';
import type { SignalScores, PgHybridSearchRow } from './types';
import {
  calculateSkillsExactMatch,
  calculateSkillsInferred,
  calculateSeniorityAlignment,
  calculateRecencyBoost,
  calculateCompanyRelevance,
  detectCompanyTier,
  type CandidateExperience
} from './signal-calculators';
import {
  calculateTrajectoryFit,
  computeTrajectoryMetrics,
  type TrajectoryContext,
  type ExperienceEntry
} from './trajectory-calculators';

// Re-export SignalScores for convenience
export type { SignalScores } from './types';

/**
 * Search context for Phase 7+ signal computation.
 * Provides the query-side data needed to compute match scores.
 */
export interface SignalComputationContext {
  requiredSkills?: string[];
  preferredSkills?: string[];
  targetLevel?: string;
  targetCompanies?: string[];
  targetIndustries?: string[];
  roleType?: 'executive' | 'manager' | 'ic' | 'default';

  // Phase 8: Trajectory context
  targetTrack?: 'technical' | 'management';
  roleGrowthType?: 'high_growth' | 'stable' | 'turnaround';
  allowPivot?: boolean;
}

/**
 * Computes the final weighted score from individual signals.
 * Missing signals default to 0.5 (neutral) to avoid NaN.
 *
 * @param signals - Individual signal scores (0-1 normalized)
 * @param weights - Weight configuration (should sum to 1.0)
 * @returns Final weighted score (0-1 range)
 *
 * @example
 * const score = computeWeightedScore(
 *   { vectorSimilarity: 0.8, levelMatch: 1.0, specialtyMatch: 0.9 },
 *   defaultWeights
 * );
 */
export function computeWeightedScore(
  signals: Partial<SignalScores>,
  weights: SignalWeightConfig
): number {
  // Default missing signals to 0.5 (neutral)
  const vs = signals.vectorSimilarity ?? 0.5;
  const lm = signals.levelMatch ?? 0.5;
  const sm = signals.specialtyMatch ?? 0.5;
  const ts = signals.techStackMatch ?? 0.5;
  const fm = signals.functionMatch ?? 0.5;
  const tf = signals.trajectoryFit ?? 0.5;
  const cp = signals.companyPedigree ?? 0.5;

  let score = 0;
  score += vs * weights.vectorSimilarity;
  score += lm * weights.levelMatch;
  score += sm * weights.specialtyMatch;
  score += ts * weights.techStackMatch;
  score += fm * weights.functionMatch;
  score += tf * weights.trajectoryFit;
  score += cp * weights.companyPedigree;

  // Handle optional skillsMatch if both signal and weight exist
  if (signals.skillsMatch !== undefined && weights.skillsMatch) {
    score += signals.skillsMatch * weights.skillsMatch;
  }

  // Phase 7 signals (only add if both signal and weight exist)
  if (signals.skillsExactMatch !== undefined && weights.skillsExactMatch) {
    score += signals.skillsExactMatch * weights.skillsExactMatch;
  }
  if (signals.skillsInferred !== undefined && weights.skillsInferred) {
    score += signals.skillsInferred * weights.skillsInferred;
  }
  if (signals.seniorityAlignment !== undefined && weights.seniorityAlignment) {
    score += signals.seniorityAlignment * weights.seniorityAlignment;
  }
  if (signals.recencyBoost !== undefined && weights.recencyBoost) {
    score += signals.recencyBoost * weights.recencyBoost;
  }
  if (signals.companyRelevance !== undefined && weights.companyRelevance) {
    score += signals.companyRelevance * weights.companyRelevance;
  }

  return score;
}

/**
 * Helper to extract a score from metadata, defaulting to 0.5 if not found.
 */
function extractScore(
  obj: Record<string, unknown> | null | undefined,
  key: string,
  defaultValue = 0.5
): number {
  if (!obj) return defaultValue;
  const value = obj[key];
  if (typeof value === 'number' && Number.isFinite(value)) {
    // Normalize to 0-1 if in 0-100 range
    return value > 1 ? value / 100 : value;
  }
  return defaultValue;
}

/**
 * Extracts signal scores from a PgHybridSearchRow.
 * When signalContext is provided, also computes Phase 7 signals.
 *
 * @param row - Database row with scores
 * @param signalContext - Optional search context for Phase 7 signals
 * @returns SignalScores with all signals extracted and normalized
 *
 * @example
 * const signals = extractSignalScores(dbRow);
 * const score = computeWeightedScore(signals, weights);
 */
export function extractSignalScores(
  row: PgHybridSearchRow,
  signalContext?: SignalComputationContext
): SignalScores {
  // Normalize vector score to 0-1 (handle both 0-100 and 0-1 scales)
  const rawVector = Number(row.vector_score ?? 0);
  const vectorSimilarity = rawVector > 1 ? rawVector / 100 : rawVector;

  // Extract profile-based scores from metadata if available
  // These will be populated by Phase 2 scoring or default to 0.5
  const metadata = row.metadata as Record<string, unknown> | null;

  const scores: SignalScores = {
    vectorSimilarity,
    levelMatch: extractScore(metadata, '_level_score'),
    specialtyMatch: extractScore(metadata, '_specialty_score'),
    techStackMatch: extractScore(metadata, '_tech_stack_score'),
    functionMatch: extractScore(metadata, '_function_title_score'),
    trajectoryFit: extractScore(metadata, '_trajectory_score'),
    companyPedigree: extractScore(metadata, '_company_score')
  };

  // Phase 7 signals (only compute if context provided)
  if (signalContext) {
    const candidateSkills = extractCandidateSkills(row);
    const candidateExperience = extractCandidateExperience(row);
    const candidateCompanies = extractCandidateCompanies(row);
    const candidateIndustries = (row.industries || []) as string[];
    const candidateLevel = extractCandidateLevel(row);
    const companyTier = detectCompanyTier(candidateCompanies);

    // SCOR-02: Skills exact match
    scores.skillsExactMatch = calculateSkillsExactMatch(candidateSkills, {
      requiredSkills: signalContext.requiredSkills || [],
      preferredSkills: signalContext.preferredSkills || []
    });

    // SCOR-03: Skills inferred
    scores.skillsInferred = calculateSkillsInferred(candidateSkills, {
      requiredSkills: signalContext.requiredSkills || [],
      preferredSkills: signalContext.preferredSkills || []
    });

    // SCOR-04: Seniority alignment
    scores.seniorityAlignment = calculateSeniorityAlignment(
      candidateLevel,
      companyTier,
      {
        targetLevel: signalContext.targetLevel || 'mid',
        roleType: signalContext.roleType || 'default'
      }
    );

    // SCOR-05: Recency boost
    scores.recencyBoost = calculateRecencyBoost(
      candidateExperience,
      signalContext.requiredSkills || []
    );

    // SCOR-06: Company relevance
    scores.companyRelevance = calculateCompanyRelevance(
      candidateCompanies,
      candidateIndustries,
      companyTier,
      {
        targetCompanies: signalContext.targetCompanies,
        targetIndustries: signalContext.targetIndustries
      }
    );

    // Phase 8: Trajectory fit scoring (TRAJ-03)
    // Extract title sequence from experience
    const titleSequence = candidateExperience
      .sort((a, b) => {
        const aTime = a.startDate ? new Date(a.startDate).getTime() : 0;
        const bTime = b.startDate ? new Date(b.startDate).getTime() : 0;
        return aTime - bTime;
      })
      .map(exp => exp.title)
      .filter(Boolean);

    if (titleSequence.length >= 2) {
      // Convert CandidateExperience[] to ExperienceEntry[] for velocity calculation
      const experienceEntries: ExperienceEntry[] = candidateExperience.map(exp => {
        const startDate = exp.startDate instanceof Date
          ? exp.startDate.toISOString()
          : exp.startDate;
        const endDate = exp.endDate instanceof Date
          ? exp.endDate.toISOString()
          : typeof exp.endDate === 'string'
          ? exp.endDate
          : undefined;

        return { title: exp.title, startDate, endDate };
      });

      const togetherAiData = extractTogetherAITrajectory(row);

      // Compute trajectory metrics
      const metrics = computeTrajectoryMetrics(titleSequence, experienceEntries, togetherAiData);

      // Build trajectory context from signal context
      const trajectoryContext: TrajectoryContext = {
        targetTrack: signalContext.targetTrack || inferTargetTrack(signalContext.roleType),
        roleGrowthType: signalContext.roleGrowthType,
        allowPivot: signalContext.allowPivot
      };

      // Calculate trajectory fit score
      const trajectoryFitScore = calculateTrajectoryFit(metrics, trajectoryContext);

      // Override the Phase 2 trajectory score with Phase 8 computed value
      scores.trajectoryFit = trajectoryFitScore;
    }
  }

  return scores;
}

/**
 * Normalizes a vector similarity score to 0-1 range.
 * Handles both 0-100 and 0-1 input scales.
 *
 * @param score - Raw vector score
 * @returns Normalized score in 0-1 range
 */
export function normalizeVectorScore(score: number | null | undefined): number {
  const value = Number(score ?? 0);
  if (!Number.isFinite(value)) return 0;
  return value > 1 ? value / 100 : value;
}

/**
 * Creates a complete SignalScores object with all fields, using defaults
 * for any missing values. Useful for ensuring all scores are present.
 *
 * @param partial - Partial signal scores
 * @param defaultValue - Default value for missing scores (default: 0.5)
 * @returns Complete SignalScores with all fields populated
 */
export function completeSignalScores(
  partial: Partial<SignalScores>,
  defaultValue = 0.5
): SignalScores {
  return {
    vectorSimilarity: partial.vectorSimilarity ?? defaultValue,
    levelMatch: partial.levelMatch ?? defaultValue,
    specialtyMatch: partial.specialtyMatch ?? defaultValue,
    techStackMatch: partial.techStackMatch ?? defaultValue,
    functionMatch: partial.functionMatch ?? defaultValue,
    trajectoryFit: partial.trajectoryFit ?? defaultValue,
    companyPedigree: partial.companyPedigree ?? defaultValue,
    ...(partial.skillsMatch !== undefined && { skillsMatch: partial.skillsMatch })
  };
}

/**
 * Extract candidate skills from row data
 */
function extractCandidateSkills(row: PgHybridSearchRow): string[] {
  const skills: string[] = [];

  // From skills array
  if (row.skills) {
    skills.push(...row.skills);
  }

  // From metadata intelligent_analysis
  const metadata = row.metadata as Record<string, unknown> | null;
  if (metadata?.intelligent_analysis) {
    const analysis = metadata.intelligent_analysis as Record<string, unknown>;

    // Explicit skills
    if (analysis.explicit_skills) {
      const explicit = analysis.explicit_skills as Record<string, unknown>;
      if (Array.isArray(explicit.technical_skills)) {
        explicit.technical_skills.forEach((s: unknown) => {
          if (typeof s === 'string') skills.push(s);
          else if (s && typeof s === 'object' && 'skill' in s) skills.push(String((s as {skill: string}).skill));
        });
      }
    }
  }

  return [...new Set(skills)];
}

/**
 * Extract candidate level from row data
 */
function extractCandidateLevel(row: PgHybridSearchRow): string | null {
  const metadata = row.metadata as Record<string, unknown> | null;

  if (metadata?.intelligent_analysis) {
    const analysis = metadata.intelligent_analysis as Record<string, unknown>;
    if (analysis.career_trajectory_analysis) {
      const trajectory = analysis.career_trajectory_analysis as Record<string, unknown>;
      if (trajectory.current_level) return String(trajectory.current_level);
    }
  }

  if (metadata?.current_level) return String(metadata.current_level);
  return null;
}

/**
 * Extract candidate companies from row data
 */
function extractCandidateCompanies(row: PgHybridSearchRow): string[] {
  const companies: string[] = [];
  const metadata = row.metadata as Record<string, unknown> | null;

  if (metadata?.intelligent_analysis) {
    const analysis = metadata.intelligent_analysis as Record<string, unknown>;
    if (Array.isArray(analysis.experience)) {
      (analysis.experience as Array<{company?: string}>).forEach(exp => {
        if (exp.company) companies.push(exp.company);
      });
    }
  }

  return [...new Set(companies)];
}

/**
 * Extract candidate experience for recency calculation
 */
function extractCandidateExperience(row: PgHybridSearchRow): CandidateExperience[] {
  const experience: CandidateExperience[] = [];
  const metadata = row.metadata as Record<string, unknown> | null;

  if (metadata?.intelligent_analysis) {
    const analysis = metadata.intelligent_analysis as Record<string, unknown>;
    if (Array.isArray(analysis.experience)) {
      (analysis.experience as Array<Record<string, unknown>>).forEach(exp => {
        experience.push({
          title: String(exp.title || ''),
          skills: Array.isArray(exp.skills) ? exp.skills.map(String) : [],
          startDate: exp.start_date as string | undefined,
          endDate: exp.end_date as string | null | undefined,
          isCurrent: Boolean(exp.is_current)
        });
      });
    }
  }

  return experience;
}

/**
 * Extract Together AI trajectory data from metadata
 */
function extractTogetherAITrajectory(row: PgHybridSearchRow) {
  const metadata = row.metadata as Record<string, unknown> | null;

  if (metadata?.intelligent_analysis) {
    const analysis = metadata.intelligent_analysis as Record<string, unknown>;
    if (analysis.career_trajectory_analysis) {
      const trajectory = analysis.career_trajectory_analysis as Record<string, unknown>;
      return {
        promotion_velocity: trajectory.promotion_velocity as 'fast' | 'normal' | 'slow' | undefined,
        current_level: trajectory.current_level as string | undefined,
        trajectory_type: trajectory.trajectory_type as string | undefined
      };
    }
  }

  return undefined;
}

/**
 * Infer target track from role type or job description.
 * Defaults to 'technical' for IC roles, 'management' for manager/executive.
 */
function inferTargetTrack(
  roleType?: 'executive' | 'manager' | 'ic' | 'default'
): 'technical' | 'management' | undefined {
  if (!roleType || roleType === 'default') return undefined;
  if (roleType === 'ic') return 'technical';
  return 'management'; // executive or manager
}
