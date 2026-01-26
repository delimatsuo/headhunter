/**
 * Anonymization middleware for BIAS-01: Resume anonymization toggle
 *
 * Transforms search results to remove PII and demographic proxies,
 * enabling blind hiring workflows that reduce unconscious bias.
 */

import type { HybridSearchResultItem, HybridSearchResponse } from '../types';
import type {
  AnonymizationConfig,
  AnonymizedCandidate,
  AnonymizedSearchResponse,
} from './types';
import { DEFAULT_ANONYMIZATION_CONFIG } from './types';
import { getLogger } from '@hh/common';

const logger = getLogger({ module: 'anonymization' });

/**
 * Anonymize a single candidate result.
 * Strips PII fields and optionally proxy fields based on config.
 *
 * @param candidate - Full candidate result with PII
 * @param _config - Anonymization configuration (reserved for future use)
 * @returns Anonymized candidate with only job-relevant data
 */
export function anonymizeCandidate(
  candidate: HybridSearchResultItem,
  _config: AnonymizationConfig = DEFAULT_ANONYMIZATION_CONFIG
): AnonymizedCandidate {
  // Extract signal scores, excluding companyPedigree if proxy stripping enabled
  let signalScores: AnonymizedCandidate['signalScores'] | undefined;

  if (candidate.signalScores) {
    signalScores = {
      vectorSimilarity: candidate.signalScores.vectorSimilarity,
      levelMatch: candidate.signalScores.levelMatch,
      specialtyMatch: candidate.signalScores.specialtyMatch,
      techStackMatch: candidate.signalScores.techStackMatch,
      functionMatch: candidate.signalScores.functionMatch,
      trajectoryFit: candidate.signalScores.trajectoryFit,
      // Only include Phase 7 signals if present
      ...(candidate.signalScores.skillsExactMatch !== undefined && {
        skillsExactMatch: candidate.signalScores.skillsExactMatch,
      }),
      ...(candidate.signalScores.skillsInferred !== undefined && {
        skillsInferred: candidate.signalScores.skillsInferred,
      }),
      ...(candidate.signalScores.seniorityAlignment !== undefined && {
        seniorityAlignment: candidate.signalScores.seniorityAlignment,
      }),
      ...(candidate.signalScores.recencyBoost !== undefined && {
        recencyBoost: candidate.signalScores.recencyBoost,
      }),
      // Note: companyPedigree and companyRelevance excluded - proxy risk
    };
  }

  // Build anonymized result
  const anonymized: AnonymizedCandidate = {
    candidateId: candidate.candidateId,
    score: candidate.score,
    vectorScore: candidate.vectorScore,
    textScore: candidate.textScore,
    confidence: candidate.confidence,
    matchReasons: anonymizeMatchReasons(candidate.matchReasons),
    anonymized: true,
  };

  // Optional fields
  if (candidate.rrfScore !== undefined) {
    anonymized.rrfScore = candidate.rrfScore;
  }

  if (candidate.yearsExperience !== undefined) {
    anonymized.yearsExperience = candidate.yearsExperience;
  }

  // Skills - preserve skill names and weights, no company context
  if (candidate.skills && candidate.skills.length > 0) {
    anonymized.skills = candidate.skills.map((s) => ({
      name: s.name,
      weight: s.weight,
    }));
  }

  // Industries - job-relevant context
  if (candidate.industries && candidate.industries.length > 0) {
    anonymized.industries = [...candidate.industries];
  }

  // Signal scores (without company pedigree)
  if (signalScores) {
    anonymized.signalScores = signalScores;
  }

  // Weights for transparency
  if (candidate.weightsApplied) {
    // Exclude companyPedigree and companyRelevance weights
    const weights = candidate.weightsApplied;
    const safeWeights: Record<string, number> = {};

    // Copy all weights except company-related ones
    for (const key of Object.keys(weights) as Array<keyof typeof weights>) {
      if (key !== 'companyPedigree' && key !== 'companyRelevance') {
        const value = weights[key];
        if (value !== undefined) {
          safeWeights[key] = value;
        }
      }
    }

    anonymized.weightsApplied = safeWeights;
  }

  // ML trajectory - predictive, not identifying
  if (candidate.mlTrajectory) {
    anonymized.mlTrajectory = { ...candidate.mlTrajectory };
  }

  logger.debug(
    { candidateId: candidate.candidateId },
    'Anonymized candidate for blind review'
  );

  return anonymized;
}

/**
 * Anonymize match reasons by removing any that might leak PII.
 * Removes reasons mentioning specific companies, schools, or names.
 */
function anonymizeMatchReasons(reasons: string[]): string[] {
  if (!reasons || reasons.length === 0) return [];

  return reasons
    .filter((reason) => {
      // Filter out reasons that mention specific identifying info
      // Keep generic ones like "Strong skill match", "Senior level alignment"
      const hasCompanyMention =
        /\b(at|from|worked at|experience at)\s+[A-Z]/i.test(reason);
      const hasSchoolMention =
        /\b(graduated|degree from|alumni|university|college)\b/i.test(reason);
      const hasLocationMention =
        /\b(based in|located in|from|lives in)\b/i.test(reason);

      return !hasCompanyMention && !hasSchoolMention && !hasLocationMention;
    })
    .map((reason) => {
      // Generalize any remaining specific mentions
      return reason
        .replace(/\b\d{4}\b/g, '[year]') // Replace years
        .replace(/\b[A-Z][a-z]+ [A-Z][a-z]+\b/g, '[name]'); // Replace potential names
    });
}

/**
 * Anonymize an entire search response.
 * Applies anonymization to all candidates and removes response-level PII.
 *
 * @param response - Full search response
 * @param config - Anonymization configuration
 * @returns Response with all candidates anonymized
 */
export function anonymizeSearchResponse(
  response: HybridSearchResponse,
  config: AnonymizationConfig = DEFAULT_ANONYMIZATION_CONFIG
): AnonymizedSearchResponse {
  const anonymizedResults = response.results.map((candidate) =>
    anonymizeCandidate(candidate, config)
  );

  logger.info(
    {
      requestId: response.requestId,
      candidateCount: anonymizedResults.length,
    },
    'Anonymized search response for blind review'
  );

  return {
    results: anonymizedResults,
    total: response.total,
    cacheHit: response.cacheHit,
    requestId: response.requestId,
    timings: response.timings,
    metadata: {
      anonymized: true,
      anonymizedAt: new Date().toISOString(),
    },
  };
}

/**
 * Check if a response is already anonymized.
 */
export function isAnonymizedResponse(
  response: HybridSearchResponse | AnonymizedSearchResponse
): response is AnonymizedSearchResponse {
  const metadata = response.metadata as { anonymized?: boolean } | undefined;
  return metadata?.anonymized === true;
}
