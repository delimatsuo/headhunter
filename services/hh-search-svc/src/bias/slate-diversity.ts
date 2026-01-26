/**
 * Slate Diversity Analysis for BIAS-05
 *
 * Analyzes search results to detect homogeneous candidate pools
 * and generate warnings to encourage recruiters to broaden criteria.
 */

import type { HybridSearchResultItem } from '../types';
import type {
  DiversityDimension,
  DimensionDistribution,
  DiversityWarning,
  SlateDiversityAnalysis,
  DiversityConfig,
} from './types';
import { DEFAULT_DIVERSITY_CONFIG } from './types';
import { getLogger } from '@hh/common';

const logger = getLogger({ module: 'slate-diversity' });

// ============================================================================
// Dimension Inference Functions
// ============================================================================

/**
 * FAANG and major tech company names for tier inference.
 */
const FAANG_COMPANIES = new Set([
  'google', 'meta', 'facebook', 'amazon', 'apple', 'microsoft', 'netflix',
  'alphabet', 'openai', 'anthropic', 'deepmind', 'nvidia', 'tesla',
  'uber', 'airbnb', 'stripe', 'linkedin', 'twitter', 'x corp', 'salesforce',
  'oracle', 'adobe', 'snap', 'spotify', 'dropbox', 'slack', 'zoom',
]);

/**
 * Enterprise company indicators.
 */
const ENTERPRISE_INDICATORS = [
  'bank', 'insurance', 'capital', 'financial', 'consulting', 'group',
  'holdings', 'corporation', 'corp', 'inc', 'ltd', 'llc', 'plc',
];

/**
 * Infer company tier from company names.
 */
export function inferCompanyTier(companies: string[]): string {
  if (!companies || companies.length === 0) {
    return 'unknown';
  }

  // Check for FAANG/Big Tech
  for (const company of companies) {
    const normalized = company.toLowerCase().trim();
    if (FAANG_COMPANIES.has(normalized)) {
      return 'faang';
    }
    // Partial match for variations like "Google Inc."
    for (const faang of FAANG_COMPANIES) {
      if (normalized.includes(faang)) {
        return 'faang';
      }
    }
  }

  // Check for enterprise indicators
  for (const company of companies) {
    const normalized = company.toLowerCase();
    for (const indicator of ENTERPRISE_INDICATORS) {
      if (normalized.includes(indicator)) {
        return 'enterprise';
      }
    }
  }

  // Default to startup (smaller companies)
  return 'startup';
}

/**
 * Infer experience band from years of experience.
 */
export function inferExperienceBand(yearsExperience: number | undefined): string {
  if (yearsExperience === undefined || yearsExperience === null) {
    return 'unknown';
  }

  if (yearsExperience < 3) return '0-3';
  if (yearsExperience < 7) return '3-7';
  if (yearsExperience < 15) return '7-15';
  return '15+';
}

/**
 * Specialty keywords for classification.
 */
const SPECIALTY_KEYWORDS: Record<string, string[]> = {
  frontend: [
    'react', 'vue', 'angular', 'javascript', 'typescript', 'css', 'html',
    'svelte', 'next.js', 'nextjs', 'gatsby', 'webpack', 'tailwind',
  ],
  backend: [
    'python', 'java', 'go', 'golang', 'rust', 'node', 'nodejs', 'postgresql',
    'mysql', 'mongodb', 'redis', 'kafka', 'rabbitmq', 'sql', 'api', 'rest',
    'graphql', 'microservices', 'django', 'flask', 'spring', 'express',
  ],
  mobile: [
    'ios', 'android', 'swift', 'kotlin', 'react native', 'flutter', 'mobile',
    'objective-c', 'xcode', 'android studio',
  ],
  devops: [
    'kubernetes', 'docker', 'aws', 'gcp', 'azure', 'terraform', 'jenkins',
    'ci/cd', 'devops', 'infrastructure', 'sre', 'linux', 'ansible', 'helm',
  ],
  data: [
    'machine learning', 'ml', 'ai', 'data science', 'pandas', 'numpy',
    'tensorflow', 'pytorch', 'spark', 'hadoop', 'etl', 'data engineering',
    'analytics', 'bigquery', 'snowflake', 'dbt',
  ],
  fullstack: [
    'full stack', 'fullstack', 'full-stack',
  ],
};

/**
 * Infer specialty from skills and title.
 */
export function inferSpecialty(
  skills: string[] | undefined,
  title: string | undefined
): string {
  const allText = [
    ...(skills || []),
    title || '',
  ].map(s => s.toLowerCase());

  const scores: Record<string, number> = {};

  for (const [specialty, keywords] of Object.entries(SPECIALTY_KEYWORDS)) {
    scores[specialty] = 0;
    for (const text of allText) {
      for (const keyword of keywords) {
        if (text.includes(keyword)) {
          scores[specialty]++;
        }
      }
    }
  }

  // Find highest scoring specialty
  let maxSpecialty = 'generalist';
  let maxScore = 0;

  for (const [specialty, score] of Object.entries(scores)) {
    if (score > maxScore) {
      maxScore = score;
      maxSpecialty = specialty;
    }
  }

  // If very low score, likely generalist
  if (maxScore < 2) {
    return 'generalist';
  }

  return maxSpecialty;
}

// ============================================================================
// Dimension Extraction
// ============================================================================

/**
 * Extract dimension value from a candidate.
 */
function extractDimensionValue(
  candidate: HybridSearchResultItem,
  dimension: DiversityDimension
): string {
  switch (dimension) {
    case 'companyTier': {
      // Extract company names from metadata if available
      const companies = extractCompanies(candidate);
      return inferCompanyTier(companies);
    }
    case 'experienceBand': {
      return inferExperienceBand(candidate.yearsExperience);
    }
    case 'specialty': {
      const skills = candidate.skills?.map(s => s.name) || [];
      const title = candidate.title;
      return inferSpecialty(skills, title);
    }
    default:
      return 'unknown';
  }
}

/**
 * Extract company names from candidate data.
 */
function extractCompanies(candidate: HybridSearchResultItem): string[] {
  const companies: string[] = [];

  // From metadata if available
  const metadata = candidate.metadata as Record<string, unknown> | undefined;
  if (metadata?.intelligent_analysis) {
    const analysis = metadata.intelligent_analysis as Record<string, unknown>;
    if (Array.isArray(analysis.experience)) {
      (analysis.experience as Array<{ company?: string }>).forEach(exp => {
        if (exp.company) companies.push(exp.company);
      });
    }
  }

  // Fallback to title parsing (often contains company)
  if (candidate.title && companies.length === 0) {
    const titleParts = candidate.title.split(/\s+at\s+|\s+-\s+/i);
    if (titleParts.length > 1) {
      companies.push(titleParts[titleParts.length - 1].trim());
    }
  }

  return companies;
}

// ============================================================================
// Distribution Analysis
// ============================================================================

/**
 * Analyze distribution for a single dimension.
 */
function analyzeDimension(
  candidates: HybridSearchResultItem[],
  dimension: DiversityDimension,
  config: DiversityConfig
): DimensionDistribution {
  const distribution: Record<string, number> = {};

  // Count candidates per group
  for (const candidate of candidates) {
    const value = extractDimensionValue(candidate, dimension);
    distribution[value] = (distribution[value] || 0) + 1;
  }

  // Find dominant group
  let dominantGroup = '';
  let maxCount = 0;
  for (const [group, count] of Object.entries(distribution)) {
    if (count > maxCount) {
      maxCount = count;
      dominantGroup = group;
    }
  }

  const concentrationPct = candidates.length > 0
    ? (maxCount / candidates.length) * 100
    : 0;

  return {
    dimension,
    distribution,
    dominantGroup,
    concentrationPct,
    isConcentrated: concentrationPct >= config.concentrationThreshold * 100,
  };
}

// ============================================================================
// Warning Generation
// ============================================================================

/**
 * Generate human-readable warning for concentrated dimension.
 */
function generateWarning(
  distribution: DimensionDistribution,
  _config: DiversityConfig
): DiversityWarning | null {
  if (!distribution.isConcentrated) {
    return null;
  }

  const pct = Math.round(distribution.concentrationPct);

  // Determine severity
  const level: DiversityWarning['level'] =
    pct >= 90 ? 'alert' :
    pct >= 80 ? 'warning' :
    'info';

  // Generate dimension-specific message and suggestion
  let message: string;
  let suggestion: string;

  switch (distribution.dimension) {
    case 'companyTier':
      message = `This slate is ${pct}% from ${formatCompanyTier(distribution.dominantGroup)} companies`;
      suggestion = distribution.dominantGroup === 'faang'
        ? 'Consider including candidates from startups or mid-size companies'
        : distribution.dominantGroup === 'startup'
        ? 'Consider including candidates with enterprise experience'
        : 'Consider broadening company background criteria';
      break;

    case 'experienceBand':
      message = `This slate is ${pct}% in the ${distribution.dominantGroup} years experience band`;
      suggestion = distribution.dominantGroup === '15+'
        ? 'Consider including candidates with less experience but high potential'
        : distribution.dominantGroup === '0-3'
        ? 'Consider including more experienced candidates'
        : 'Consider broadening experience range';
      break;

    case 'specialty':
      message = `This slate is ${pct}% ${distribution.dominantGroup} specialists`;
      suggestion = 'Consider including candidates from adjacent specialties (e.g., fullstack for backend roles)';
      break;

    default:
      message = `High concentration (${pct}%) in ${distribution.dimension}`;
      suggestion = 'Consider broadening search criteria';
  }

  return {
    level,
    message,
    dimension: distribution.dimension,
    concentrationPct: pct,
    suggestion,
  };
}

/**
 * Format company tier for display.
 */
function formatCompanyTier(tier: string): string {
  switch (tier) {
    case 'faang': return 'FAANG/Big Tech';
    case 'enterprise': return 'enterprise';
    case 'startup': return 'startup';
    default: return tier;
  }
}

// ============================================================================
// Diversity Score Calculation
// ============================================================================

/**
 * Calculate overall diversity score.
 * Higher score = more diverse slate.
 */
function calculateDiversityScore(distributions: DimensionDistribution[]): number {
  if (distributions.length === 0) return 100;

  // Calculate entropy-based diversity per dimension
  const scores = distributions.map(dist => {
    const values = Object.values(dist.distribution);
    const total = values.reduce((a, b) => a + b, 0);

    if (total === 0) return 100;

    // Shannon entropy (normalized)
    let entropy = 0;
    for (const count of values) {
      if (count > 0) {
        const p = count / total;
        entropy -= p * Math.log2(p);
      }
    }

    // Normalize to 0-100 (max entropy for n groups = log2(n))
    const maxEntropy = Math.log2(values.length || 1);
    const normalizedScore = maxEntropy > 0
      ? (entropy / maxEntropy) * 100
      : 100;

    return normalizedScore;
  });

  // Average across dimensions
  return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
}

// ============================================================================
// Main Analysis Function
// ============================================================================

/**
 * Analyze slate diversity across all configured dimensions.
 *
 * @param candidates - Search results to analyze
 * @param config - Diversity configuration
 * @returns Complete diversity analysis with warnings
 */
export function analyzeSlateDiversity(
  candidates: HybridSearchResultItem[],
  config: DiversityConfig = DEFAULT_DIVERSITY_CONFIG
): SlateDiversityAnalysis {
  // Skip analysis if too few candidates
  if (candidates.length < config.minCandidates) {
    logger.debug(
      { count: candidates.length, min: config.minCandidates },
      'Skipping diversity analysis - too few candidates'
    );

    return {
      totalCandidates: candidates.length,
      dimensions: [],
      warnings: [],
      diversityScore: 100,  // Assume diverse if we can't analyze
      hasConcentrationIssue: false,
    };
  }

  // Analyze each dimension
  const dimensions = config.dimensions.map(dim =>
    analyzeDimension(candidates, dim, config)
  );

  // Generate warnings for concentrated dimensions
  const warnings = dimensions
    .map(dist => generateWarning(dist, config))
    .filter((w): w is DiversityWarning => w !== null);

  const diversityScore = calculateDiversityScore(dimensions);
  const hasConcentrationIssue = dimensions.some(d => d.isConcentrated);

  logger.info(
    {
      totalCandidates: candidates.length,
      diversityScore,
      warningCount: warnings.length,
      hasConcentrationIssue,
    },
    'Slate diversity analysis complete'
  );

  return {
    totalCandidates: candidates.length,
    dimensions,
    warnings,
    diversityScore,
    hasConcentrationIssue,
  };
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Generate a concise summary message for display.
 */
export function formatDiversitySummary(analysis: SlateDiversityAnalysis): string {
  if (analysis.warnings.length === 0) {
    return `Diverse slate (score: ${analysis.diversityScore}/100)`;
  }

  const topWarning = analysis.warnings
    .sort((a, b) => b.concentrationPct - a.concentrationPct)[0];

  return topWarning.message;
}

/**
 * Check if analysis warrants display to user.
 */
export function shouldShowDiversityWarning(analysis: SlateDiversityAnalysis): boolean {
  return analysis.hasConcentrationIssue || analysis.diversityScore < 50;
}
