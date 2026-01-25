/**
 * Signal Calculators for Phase 7: Multi-Signal Scoring
 *
 * This module implements 5 pure scoring functions that compute 0-1 normalized scores
 * from candidate data and search context:
 *
 * - SCOR-02: calculateSkillsExactMatch - Required skill coverage score
 * - SCOR-03: calculateSkillsInferred - Transferable/related skill match score
 * - SCOR-04: calculateSeniorityAlignment - Seniority level fit score
 * - SCOR-05: calculateCompanyPedigree - Company quality/tier score
 * - SCOR-06: calculateCareerTrajectory - Career progression fit score
 *
 * All functions return 0.5 (neutral) when required context data is missing.
 */

// ============================================================================
// Context Interfaces
// ============================================================================

export interface SkillMatchContext {
  requiredSkills: string[];
  preferredSkills: string[];
}

export interface SeniorityContext {
  targetLevel: string;
  roleType: 'executive' | 'manager' | 'ic' | 'default';
}

export interface CompanyContext {
  targetCompanies?: string[];
  targetIndustries?: string[];
}

export interface CandidateExperience {
  title: string;
  skills: string[];
  startDate?: string | Date;
  endDate?: string | Date | null;
  isCurrent: boolean;
}

// ============================================================================
// Constants
// ============================================================================

/**
 * Seniority level ordering for alignment scoring.
 * Used to calculate distance between candidate and target levels.
 */
const LEVEL_ORDER = [
  'intern',
  'junior',
  'mid',
  'senior',
  'staff',
  'principal',
  'manager',
  'director',
  'vp',
  'c-level'
];

/**
 * FAANG company tier definitions.
 */
const FAANG_COMPANIES = [
  'google',
  'meta',
  'facebook',
  'amazon',
  'microsoft',
  'apple',
  'netflix'
];

/**
 * Unicorn company tier definitions.
 */
const UNICORN_COMPANIES = [
  'nubank',
  'ifood',
  'mercado libre',
  'stripe',
  'uber',
  'airbnb',
  'spotify'
];

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Returns common aliases for a skill name.
 * Used for fuzzy matching in skill comparison.
 */
function getCommonAliases(skill: string): string[] {
  const COMMON_ALIASES: Record<string, string[]> = {
    'javascript': ['js', 'ecmascript'],
    'typescript': ['ts'],
    'kubernetes': ['k8s'],
    'postgresql': ['postgres', 'psql'],
    'python': ['py'],
    'react': ['reactjs', 'react.js'],
    'node.js': ['node', 'nodejs'],
    'vue.js': ['vue', 'vuejs'],
    'c#': ['csharp', 'c-sharp'],
    'c++': ['cpp'],
  };

  for (const [canonical, aliases] of Object.entries(COMMON_ALIASES)) {
    if (skill === canonical || aliases.includes(skill)) {
      return [canonical, ...aliases];
    }
  }
  return [];
}

// ============================================================================
// Signal Calculator Functions
// ============================================================================

/**
 * SCOR-02: Calculate exact skill match score.
 *
 * Returns 0-1 score based on how many required skills the candidate has.
 * Handles skill aliases for fuzzy matching (e.g., "js" matches "javascript").
 *
 * @param candidateSkills - Skills extracted from candidate profile
 * @param context - Required and preferred skills from search query
 * @returns 0.0 (no match) to 1.0 (perfect match), 0.5 if no required skills
 */
export function calculateSkillsExactMatch(
  candidateSkills: string[],
  context: SkillMatchContext
): number {
  if (!context.requiredSkills || context.requiredSkills.length === 0) {
    return 0.5; // Neutral score when no required skills specified
  }
  if (!candidateSkills || candidateSkills.length === 0) {
    return 0.0; // No skills means no match
  }

  const normalizedCandidateSkills = new Set(
    candidateSkills.map(s => s.toLowerCase().trim())
  );

  let matchCount = 0;
  for (const required of context.requiredSkills) {
    const normalizedRequired = required.toLowerCase().trim();
    if (normalizedCandidateSkills.has(normalizedRequired)) {
      matchCount++;
    } else {
      // Check aliases (e.g., "js" for "javascript")
      const aliases = getCommonAliases(normalizedRequired);
      if (aliases.some(alias => normalizedCandidateSkills.has(alias))) {
        matchCount++;
      }
    }
  }

  return matchCount / context.requiredSkills.length;
}

// ============================================================================
// Transferable Skill Rules
// ============================================================================

interface TransferRule {
  fromSkill: string;
  transferabilityScore: number;
}

/**
 * Returns transferable skill rules for a target skill.
 * These rules define which candidate skills can transfer to the target skill
 * and what the transferability score is (0-1).
 */
function getTransferableSkillRules(toSkill: string): TransferRule[] {
  const TRANSFER_RULES: Record<string, TransferRule[]> = {
    'react': [
      { fromSkill: 'vue.js', transferabilityScore: 0.75 },
      { fromSkill: 'angular', transferabilityScore: 0.65 },
    ],
    'vue.js': [
      { fromSkill: 'react', transferabilityScore: 0.75 },
      { fromSkill: 'angular', transferabilityScore: 0.65 },
    ],
    'kotlin': [{ fromSkill: 'java', transferabilityScore: 0.90 }],
    'java': [
      { fromSkill: 'kotlin', transferabilityScore: 0.85 },
      { fromSkill: 'c#', transferabilityScore: 0.70 },
    ],
    'typescript': [{ fromSkill: 'javascript', transferabilityScore: 0.95 }],
    'go': [
      { fromSkill: 'python', transferabilityScore: 0.60 },
      { fromSkill: 'java', transferabilityScore: 0.65 },
    ],
    'aws': [
      { fromSkill: 'google cloud', transferabilityScore: 0.70 },
      { fromSkill: 'azure', transferabilityScore: 0.70 },
    ],
    'postgresql': [
      { fromSkill: 'mysql', transferabilityScore: 0.85 },
      { fromSkill: 'sql server', transferabilityScore: 0.80 },
    ],
    'django': [
      { fromSkill: 'flask', transferabilityScore: 0.85 },
      { fromSkill: 'fastapi', transferabilityScore: 0.80 },
    ],
  };

  return TRANSFER_RULES[toSkill] || [];
}

/**
 * SCOR-03: Calculate inferred skill match score.
 *
 * Returns 0-1 score based on transferable/related skills the candidate has.
 * For example, if a role requires React and the candidate has Vue.js,
 * they get partial credit based on transferability.
 *
 * Score formula: (avg transferability) * (coverage ratio)
 * - avg transferability: mean of matched transfer scores
 * - coverage ratio: inferred matches / total required skills
 *
 * @param candidateSkills - Skills extracted from candidate profile
 * @param context - Required and preferred skills from search query
 * @returns 0.0 (no match) to 1.0 (perfect match), 0.5 if no required skills
 */
export function calculateSkillsInferred(
  candidateSkills: string[],
  context: SkillMatchContext
): number {
  if (!context.requiredSkills || context.requiredSkills.length === 0) {
    return 0.5; // Neutral score when no required skills specified
  }
  if (!candidateSkills || candidateSkills.length === 0) {
    return 0.0; // No skills means no match
  }

  const normalizedCandidateSkills = new Set(
    candidateSkills.map(s => s.toLowerCase().trim())
  );

  let totalTransferScore = 0;
  let inferredMatches = 0;

  for (const required of context.requiredSkills) {
    const normalizedRequired = required.toLowerCase().trim();
    const aliases = [normalizedRequired, ...getCommonAliases(normalizedRequired)];

    // Skip if this is an exact match (handled by calculateSkillsExactMatch)
    if (aliases.some(a => normalizedCandidateSkills.has(a))) {
      continue;
    }

    // Check for transferable skill matches
    const transferRules = getTransferableSkillRules(normalizedRequired);
    for (const rule of transferRules) {
      const fromAliases = [rule.fromSkill, ...getCommonAliases(rule.fromSkill)];
      if (fromAliases.some(a => normalizedCandidateSkills.has(a))) {
        totalTransferScore += rule.transferabilityScore;
        inferredMatches++;
        break; // Only count first matching transferable skill per required skill
      }
    }
  }

  if (inferredMatches === 0) {
    return 0.0; // No transferable skills found
  }

  // Formula: (avg transferability) * (coverage ratio)
  const avgTransferability = totalTransferScore / inferredMatches;
  const coverage = inferredMatches / context.requiredSkills.length;
  return avgTransferability * coverage;
}
