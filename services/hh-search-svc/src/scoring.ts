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

// Re-export SignalScores for convenience
export type { SignalScores } from './types';

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
 * Normalizes vector score to 0-1 range (database may return 0-100 or 0-1).
 *
 * @param row - Database row with scores
 * @returns SignalScores with all signals extracted and normalized
 *
 * @example
 * const signals = extractSignalScores(dbRow);
 * const score = computeWeightedScore(signals, weights);
 */
export function extractSignalScores(row: PgHybridSearchRow): SignalScores {
  // Normalize vector score to 0-1 (handle both 0-100 and 0-1 scales)
  const rawVector = Number(row.vector_score ?? 0);
  const vectorSimilarity = rawVector > 1 ? rawVector / 100 : rawVector;

  // Extract profile-based scores from metadata if available
  // These will be populated by Phase 2 scoring or default to 0.5
  const metadata = row.metadata as Record<string, unknown> | null;

  return {
    vectorSimilarity,
    levelMatch: extractScore(metadata, '_level_score'),
    specialtyMatch: extractScore(metadata, '_specialty_score'),
    techStackMatch: extractScore(metadata, '_tech_stack_score'),
    functionMatch: extractScore(metadata, '_function_title_score'),
    trajectoryFit: extractScore(metadata, '_trajectory_score'),
    companyPedigree: extractScore(metadata, '_company_score')
  };
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
