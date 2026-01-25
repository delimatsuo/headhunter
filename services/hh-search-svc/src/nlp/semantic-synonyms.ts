/**
 * Semantic Synonyms Module
 *
 * Expands seniority levels and roles to include semantically similar terms.
 * This enables "Lead engineer" to match candidates with "Senior", "Principal", "Staff" titles.
 *
 * Based on NLNG-02: Semantic query understanding requirement.
 *
 * @module nlp/semantic-synonyms
 * @see Phase 12: Natural Language Search
 */

/**
 * Seniority level synonyms - maps canonical seniority to semantically equivalent terms.
 * Higher seniority levels include lower ones in some cases (e.g., "Lead" implies "Senior").
 */
export const SENIORITY_SYNONYMS: Record<string, string[]> = {
  // Entry-level equivalents
  'junior': ['entry', 'entry-level', 'associate', 'trainee', 'graduate', 'júnior'],

  // Mid-level equivalents
  'mid': ['mid-level', 'intermediate', 'experienced', 'pleno'],

  // Senior-level equivalents (common interchangeable titles)
  'senior': ['sr', 'sr.', 'experienced', 'sênior'],

  // Staff-level equivalents (includes senior)
  'staff': ['senior staff', 'staff+'],

  // Principal-level equivalents (includes staff and senior)
  'principal': ['distinguished', 'fellow', 'architect'],

  // Lead-level equivalents (leadership track, overlaps with senior/staff IC)
  'lead': ['tech lead', 'team lead', 'lead engineer', 'lead developer', 'senior', 'staff'],

  // Manager-level equivalents
  'manager': ['engineering manager', 'em', 'mgr', 'gerente'],

  // Director-level equivalents
  'director': ['dir', 'senior director', 'diretor'],

  // VP-level equivalents
  'vp': ['vice president', 'svp', 'evp'],

  // C-level equivalents
  'c-level': ['cto', 'ceo', 'cpo', 'coo', 'chief']
};

/**
 * Role synonyms - maps canonical roles to equivalent titles.
 */
export const ROLE_SYNONYMS: Record<string, string[]> = {
  'developer': ['engineer', 'programmer', 'coder', 'dev', 'desenvolvedor'],
  'engineer': ['developer', 'programmer', 'dev', 'engenheiro'],
  'designer': ['ux designer', 'ui designer', 'product designer', 'visual designer'],
  'manager': ['lead', 'head', 'director'],
  'analyst': ['specialist', 'consultant'],
  'architect': ['principal engineer', 'system architect', 'solutions architect'],
  'devops': ['sre', 'site reliability', 'platform engineer', 'infrastructure'],
  'data scientist': ['ml engineer', 'data engineer', 'ai engineer'],
  'product manager': ['pm', 'product owner', 'po']
};

/**
 * Semantic level groupings for "at least this level" matching.
 * Index indicates hierarchy (higher = more senior).
 */
export const SENIORITY_HIERARCHY: string[] = [
  'junior',
  'mid',
  'senior',
  'staff',
  'principal',
  'lead',
  'manager',
  'director',
  'vp',
  'c-level'
];

/**
 * Result of semantic synonym expansion.
 */
export interface SemanticExpansionResult {
  /** Original input term (normalized to lowercase) */
  original: string;
  /** All synonyms including the original */
  synonyms: string[];
  /** Whether higher seniority levels are included */
  includesHigher: boolean;
}

/**
 * Expand a seniority term to include synonyms.
 *
 * @param seniority - Canonical seniority term (e.g., 'senior', 'lead')
 * @param includeHigherLevels - If true, include all seniority levels >= input
 * @returns Expansion result with synonyms
 */
export function expandSenioritySynonyms(
  seniority: string,
  includeHigherLevels = false
): SemanticExpansionResult {
  const normalized = seniority.toLowerCase().trim();

  // Get direct synonyms
  const directSynonyms = SENIORITY_SYNONYMS[normalized] ?? [];

  // Build result
  const synonyms = new Set<string>([normalized, ...directSynonyms]);

  // Optionally include higher levels
  if (includeHigherLevels) {
    const currentIndex = SENIORITY_HIERARCHY.indexOf(normalized);
    if (currentIndex !== -1) {
      for (let i = currentIndex + 1; i < SENIORITY_HIERARCHY.length; i++) {
        const higherLevel = SENIORITY_HIERARCHY[i];
        synonyms.add(higherLevel);
        // Add synonyms of higher levels too
        const higherSynonyms = SENIORITY_SYNONYMS[higherLevel] ?? [];
        for (const syn of higherSynonyms) {
          synonyms.add(syn);
        }
      }
    }
  }

  return {
    original: normalized,
    synonyms: Array.from(synonyms),
    includesHigher: includeHigherLevels
  };
}

/**
 * Expand a role term to include synonyms.
 *
 * @param role - Role term (e.g., 'developer', 'engineer')
 * @returns Expansion result with synonyms
 */
export function expandRoleSynonyms(role: string): SemanticExpansionResult {
  const normalized = role.toLowerCase().trim();

  const directSynonyms = ROLE_SYNONYMS[normalized] ?? [];

  return {
    original: normalized,
    synonyms: [normalized, ...directSynonyms],
    includesHigher: false
  };
}

/**
 * Expand all semantic synonyms in extracted entities.
 * Modifies the entities to include expanded seniority levels and roles.
 *
 * @param entities - Extracted entities from NLP parser
 * @returns Enhanced entities with semantic synonyms
 */
export function expandSemanticSynonyms(entities: {
  role?: string;
  seniority?: string;
  seniorityLevels?: string[];
}): {
  expandedRoles: string[];
  expandedSeniorities: string[];
} {
  const expandedRoles: string[] = [];
  const expandedSeniorities: string[] = [];

  // Expand role
  if (entities.role) {
    const roleExpansion = expandRoleSynonyms(entities.role);
    expandedRoles.push(...roleExpansion.synonyms);
  }

  // Expand seniority (with higher levels for "at least this level" matching)
  if (entities.seniority) {
    const seniorityExpansion = expandSenioritySynonyms(entities.seniority, true);
    expandedSeniorities.push(...seniorityExpansion.synonyms);
  }

  // Expand explicit seniority levels array (without higher levels)
  if (entities.seniorityLevels) {
    for (const level of entities.seniorityLevels) {
      const expansion = expandSenioritySynonyms(level, false);
      for (const syn of expansion.synonyms) {
        if (!expandedSeniorities.includes(syn)) {
          expandedSeniorities.push(syn);
        }
      }
    }
  }

  return {
    expandedRoles,
    expandedSeniorities
  };
}

/**
 * Check if a candidate's level matches the target level semantically.
 *
 * @param candidateLevel - Candidate's seniority level
 * @param targetLevel - Target seniority level from query
 * @param allowHigher - Allow candidates with higher levels
 * @returns True if semantically matches
 */
export function matchesSeniorityLevel(
  candidateLevel: string,
  targetLevel: string,
  allowHigher = true
): boolean {
  const candidateNormalized = candidateLevel.toLowerCase().trim();
  const targetNormalized = targetLevel.toLowerCase().trim();

  // Direct match
  if (candidateNormalized === targetNormalized) {
    return true;
  }

  // Check synonyms
  const expansion = expandSenioritySynonyms(targetNormalized, allowHigher);
  return expansion.synonyms.some(syn => candidateNormalized.includes(syn));
}

/**
 * Get the hierarchy index for a seniority level.
 * Used for comparing seniority levels.
 *
 * @param seniority - Seniority level to look up
 * @returns Index in hierarchy (0 = junior, higher = more senior), or -1 if not found
 */
export function getSeniorityIndex(seniority: string): number {
  const normalized = seniority.toLowerCase().trim();
  return SENIORITY_HIERARCHY.indexOf(normalized);
}

/**
 * Compare two seniority levels.
 *
 * @param a - First seniority level
 * @param b - Second seniority level
 * @returns Negative if a < b, positive if a > b, 0 if equal
 */
export function compareSeniorityLevels(a: string, b: string): number {
  const indexA = getSeniorityIndex(a);
  const indexB = getSeniorityIndex(b);

  // If either is unknown, treat them as equal
  if (indexA === -1 || indexB === -1) {
    return 0;
  }

  return indexA - indexB;
}
