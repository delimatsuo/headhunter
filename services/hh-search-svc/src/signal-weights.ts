/**
 * Signal Weight Configuration for Multi-Signal Scoring Framework
 *
 * This module provides configurable weight distributions for the multi-signal
 * scoring system. Weights can be customized per-search via request overrides
 * or via role-type presets (executive, manager, ic, default).
 *
 * All weights should sum to 1.0 for normalized scoring.
 *
 * @module signal-weights
 */

/**
 * Signal weight configuration for multi-signal scoring.
 * All weights are 0-1 normalized and should sum to 1.0.
 */
export interface SignalWeightConfig {
  /** Vector similarity from hybrid search (0-1) */
  vectorSimilarity: number;

  /** Level/seniority match score (0-1) */
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
}

/**
 * Role type for weight preset selection.
 * - executive: C-level, VP, Director searches (function and pedigree matter most)
 * - manager: Engineering Manager, Tech Lead searches (balanced weights)
 * - ic: Individual Contributor searches (specialty and tech stack matter most)
 * - default: Balanced fallback when role type is unknown
 */
export type RoleType = 'executive' | 'manager' | 'ic' | 'default';

/**
 * Default weight presets for each role type.
 *
 * These presets are based on recruiter insights about what matters most
 * for different seniority levels:
 *
 * - Executive: Function and company pedigree matter most - they hire for fit
 * - Manager: Balance of skills, trajectory, and function
 * - IC: Specialty and tech stack matter most - exact skill fit
 * - Default: Balanced across all signals
 */
export const ROLE_WEIGHT_PRESETS: Record<RoleType, SignalWeightConfig> = {
  // Executive searches (C-level, VP, Director)
  // Function and company matter most - they hire for fit and pedigree
  executive: {
    vectorSimilarity: 0.10,
    levelMatch: 0.20,
    specialtyMatch: 0.05,
    techStackMatch: 0.05,
    functionMatch: 0.25,
    trajectoryFit: 0.15,
    companyPedigree: 0.20
  },

  // Manager searches (Engineering Manager, Tech Lead, Senior Manager)
  // Balance of skills, trajectory, and function
  manager: {
    vectorSimilarity: 0.15,
    levelMatch: 0.15,
    specialtyMatch: 0.15,
    techStackMatch: 0.10,
    functionMatch: 0.15,
    trajectoryFit: 0.15,
    companyPedigree: 0.15
  },

  // IC searches (Senior, Mid, Junior)
  // Specialty and tech stack matter most - exact skill fit
  ic: {
    vectorSimilarity: 0.20,
    levelMatch: 0.15,
    specialtyMatch: 0.20,
    techStackMatch: 0.20,
    functionMatch: 0.10,
    trajectoryFit: 0.10,
    companyPedigree: 0.05
  },

  // Default fallback (balanced)
  default: {
    vectorSimilarity: 0.15,
    levelMatch: 0.15,
    specialtyMatch: 0.15,
    techStackMatch: 0.15,
    functionMatch: 0.15,
    trajectoryFit: 0.10,
    companyPedigree: 0.15
  }
};

/**
 * Core signal keys (excluding optional skillsMatch)
 */
const CORE_SIGNAL_KEYS: (keyof SignalWeightConfig)[] = [
  'vectorSimilarity',
  'levelMatch',
  'specialtyMatch',
  'techStackMatch',
  'functionMatch',
  'trajectoryFit',
  'companyPedigree'
];

/**
 * Normalizes weights to ensure they sum to 1.0.
 *
 * If the sum of all weights differs from 1.0 by more than 0.001,
 * each weight is divided by the sum to normalize. A warning is logged
 * when normalization is applied.
 *
 * @param weights - The weight configuration to normalize
 * @returns Normalized SignalWeightConfig with weights summing to 1.0
 */
export function normalizeWeights(weights: SignalWeightConfig): SignalWeightConfig {
  // Calculate sum of core signals
  let sum = 0;
  for (const key of CORE_SIGNAL_KEYS) {
    sum += weights[key] ?? 0;
  }

  // Add optional skillsMatch if present
  if (weights.skillsMatch !== undefined) {
    sum += weights.skillsMatch;
  }

  // Check if normalization is needed
  if (Math.abs(sum - 1.0) <= 0.001) {
    return weights;
  }

  // Log warning about normalization
  console.warn(
    `[SignalWeights] Normalizing weights - sum was ${sum.toFixed(3)}, adjusting to 1.0`
  );

  // Normalize each weight
  const normalized: SignalWeightConfig = {
    vectorSimilarity: (weights.vectorSimilarity ?? 0) / sum,
    levelMatch: (weights.levelMatch ?? 0) / sum,
    specialtyMatch: (weights.specialtyMatch ?? 0) / sum,
    techStackMatch: (weights.techStackMatch ?? 0) / sum,
    functionMatch: (weights.functionMatch ?? 0) / sum,
    trajectoryFit: (weights.trajectoryFit ?? 0) / sum,
    companyPedigree: (weights.companyPedigree ?? 0) / sum
  };

  // Preserve optional skillsMatch if present
  if (weights.skillsMatch !== undefined) {
    normalized.skillsMatch = weights.skillsMatch / sum;
  }

  return normalized;
}

/**
 * Resolves final weight configuration by merging request overrides with role presets.
 *
 * Priority order:
 * 1. Request-level weight overrides (highest priority)
 * 2. Role-type preset weights
 * 3. Default preset (lowest priority)
 *
 * After merging, weights are normalized to sum to 1.0.
 *
 * @param requestWeights - Optional partial weight overrides from search request
 * @param roleType - Role type for preset selection (defaults to 'default')
 * @returns Final SignalWeightConfig with all weights defined and normalized
 *
 * @example
 * // Use executive preset
 * const weights = resolveWeights(undefined, 'executive');
 *
 * @example
 * // Override vector weight for IC search
 * const weights = resolveWeights({ vectorSimilarity: 0.30 }, 'ic');
 */
export function resolveWeights(
  requestWeights: Partial<SignalWeightConfig> | undefined,
  roleType: RoleType = 'default'
): SignalWeightConfig {
  // Get base weights from role preset
  const baseWeights = ROLE_WEIGHT_PRESETS[roleType] ?? ROLE_WEIGHT_PRESETS.default;

  // If no request overrides, return base weights (already normalized)
  if (!requestWeights || Object.keys(requestWeights).length === 0) {
    return { ...baseWeights };
  }

  // Merge request overrides with base weights
  const merged: SignalWeightConfig = {
    vectorSimilarity: requestWeights.vectorSimilarity ?? baseWeights.vectorSimilarity,
    levelMatch: requestWeights.levelMatch ?? baseWeights.levelMatch,
    specialtyMatch: requestWeights.specialtyMatch ?? baseWeights.specialtyMatch,
    techStackMatch: requestWeights.techStackMatch ?? baseWeights.techStackMatch,
    functionMatch: requestWeights.functionMatch ?? baseWeights.functionMatch,
    trajectoryFit: requestWeights.trajectoryFit ?? baseWeights.trajectoryFit,
    companyPedigree: requestWeights.companyPedigree ?? baseWeights.companyPedigree
  };

  // Handle optional skillsMatch
  if (requestWeights.skillsMatch !== undefined) {
    merged.skillsMatch = requestWeights.skillsMatch;
  } else if (baseWeights.skillsMatch !== undefined) {
    merged.skillsMatch = baseWeights.skillsMatch;
  }

  // Normalize to ensure sum = 1.0
  return normalizeWeights(merged);
}

/**
 * Validates that a role type string is a valid RoleType.
 *
 * @param value - String to validate
 * @returns True if value is a valid RoleType
 */
export function isValidRoleType(value: string): value is RoleType {
  return ['executive', 'manager', 'ic', 'default'].includes(value);
}

/**
 * Parses a string into a RoleType, with fallback to 'default'.
 *
 * @param value - String to parse
 * @returns RoleType value
 */
export function parseRoleType(value: string | undefined): RoleType {
  if (!value) {
    return 'default';
  }

  const normalized = value.toLowerCase().trim();

  if (isValidRoleType(normalized)) {
    return normalized;
  }

  // Handle common aliases
  if (['c-level', 'vp', 'director', 'exec'].includes(normalized)) {
    return 'executive';
  }

  if (['engineering-manager', 'tech-lead', 'team-lead', 'mgr'].includes(normalized)) {
    return 'manager';
  }

  if (['senior', 'mid', 'junior', 'individual-contributor', 'engineer'].includes(normalized)) {
    return 'ic';
  }

  return 'default';
}
