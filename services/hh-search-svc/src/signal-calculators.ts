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

/**
 * SCOR-04: Calculate seniority alignment score.
 *
 * Returns 0-1 score based on how well candidate seniority matches target level,
 * accounting for company tier (FAANG candidates are effectively +1 level).
 *
 * Distance-based scoring:
 * - 0 levels apart: 1.0
 * - 1 level apart: 0.8
 * - 2 levels apart: 0.6
 * - 3 levels apart: 0.4
 * - 4+ levels apart: 0.2
 *
 * Company tier adjustment:
 * - FAANG (tier 2): +1 effective level
 * - Unicorn (tier 1): no adjustment
 * - Startup (tier 0): -1 effective level
 *
 * @param candidateLevel - Candidate's seniority level
 * @param companyTier - Company tier: 0=startup, 1=unicorn, 2=FAANG
 * @param context - Target level and role type
 * @returns 0.0 (far apart) to 1.0 (perfect match), 0.5 if unknown
 */
export function calculateSeniorityAlignment(
  candidateLevel: string | null | undefined,
  companyTier: number,
  context: SeniorityContext
): number {
  if (!candidateLevel || candidateLevel === 'unknown' || candidateLevel.trim() === '') {
    return 0.5; // Neutral score when level is unknown
  }

  const normalizedCandidate = candidateLevel.toLowerCase().trim();
  const normalizedTarget = context.targetLevel.toLowerCase().trim();

  // Map common variations to canonical level names
  const levelMap: Record<string, string> = {
    'entry': 'junior',
    'associate': 'junior',
    'intermediate': 'mid',
    'sr': 'senior',
    'lead': 'staff',
    'distinguished': 'principal',
    'em': 'manager',
    'engineering manager': 'manager',
    'cto': 'c-level',
  };

  const candidateMapped = levelMap[normalizedCandidate] || normalizedCandidate;
  const targetMapped = levelMap[normalizedTarget] || normalizedTarget;

  const candidateIndex = LEVEL_ORDER.indexOf(candidateMapped);
  const targetIndex = LEVEL_ORDER.indexOf(targetMapped);

  if (candidateIndex === -1 || targetIndex === -1) {
    return 0.5; // Neutral score when level not in LEVEL_ORDER
  }

  // Apply company tier adjustment: FAANG +1, Startup -1
  const tierAdjustment = companyTier - 1;
  const effectiveIndex = Math.min(
    Math.max(0, candidateIndex + tierAdjustment),
    LEVEL_ORDER.length - 1
  );

  const distance = Math.abs(effectiveIndex - targetIndex);

  if (distance === 0) return 1.0;
  if (distance === 1) return 0.8;
  if (distance === 2) return 0.6;
  if (distance === 3) return 0.4;
  return 0.2;
}

/**
 * SCOR-05: Calculate recency boost score.
 *
 * Returns 0-1 score based on how recently the candidate used required skills.
 * Current role = 1.0, decays to 0.2 for 5+ years ago.
 *
 * Decay formula: 1.0 - (years_since * 0.16)
 * - 0 years (current): 1.0
 * - 1 year ago: 0.84
 * - 2 years ago: 0.68
 * - 3 years ago: 0.52
 * - 4 years ago: 0.36
 * - 5+ years ago: 0.2 (floor)
 *
 * @param candidateExperience - Candidate's work history
 * @param requiredSkills - Skills being searched for
 * @returns Score 0-1 based on skill recency, 0.5 if no context
 */
export function calculateRecencyBoost(
  candidateExperience: CandidateExperience[],
  requiredSkills: string[]
): number {
  if (!requiredSkills || requiredSkills.length === 0) {
    return 0.5; // Neutral score when no required skills
  }
  if (!candidateExperience || candidateExperience.length === 0) {
    return 0.5; // Neutral score when no experience data
  }

  const now = new Date();
  const normalizedRequired = requiredSkills.map(s => s.toLowerCase().trim());
  let totalRecencyScore = 0;
  let skillsWithData = 0;

  for (const requiredSkill of normalizedRequired) {
    const aliases = [requiredSkill, ...getCommonAliases(requiredSkill)];
    let bestRecency = 0;

    for (const exp of candidateExperience) {
      const expSkills = (exp.skills || []).map(s => s.toLowerCase().trim());
      const hasSkill = aliases.some(alias =>
        expSkills.some(es => es.includes(alias) || alias.includes(es))
      );

      if (!hasSkill) continue;

      if (exp.isCurrent) {
        bestRecency = 1.0;
        break;
      }

      if (exp.endDate) {
        const endDate = typeof exp.endDate === 'string' ? new Date(exp.endDate) : exp.endDate;
        if (!isNaN(endDate.getTime())) {
          const yearsSince = (now.getTime() - endDate.getTime()) / (365.25 * 24 * 60 * 60 * 1000);
          const recency = Math.max(0.2, 1.0 - yearsSince * 0.16);
          bestRecency = Math.max(bestRecency, recency);
        }
      }
    }

    if (bestRecency > 0) {
      totalRecencyScore += bestRecency;
      skillsWithData++;
    }
  }

  if (skillsWithData === 0) {
    return 0.3; // Low score when no skill data found (not neutral)
  }

  return totalRecencyScore / normalizedRequired.length;
}

/**
 * Helper: Detect company tier from company names.
 *
 * @param companyNames - List of company names from candidate's experience
 * @returns 0=startup, 1=unicorn, 2=FAANG
 */
export function detectCompanyTier(companyNames: string[]): number {
  if (!companyNames || companyNames.length === 0) {
    return 0;
  }

  for (const company of companyNames) {
    const lower = company.toLowerCase().trim();
    if (FAANG_COMPANIES.some(f => lower.includes(f) || f.includes(lower))) {
      return 2;
    }
    if (UNICORN_COMPANIES.some(u => lower.includes(u) || u.includes(lower))) {
      return 1;
    }
  }
  return 0;
}

/**
 * Helper: Check if two industries are related based on domain knowledge.
 */
function areIndustriesRelated(industry1: string, industry2: string): boolean {
  const RELATED_INDUSTRIES: Record<string, string[]> = {
    'fintech': ['financial services', 'banking', 'payments'],
    'e-commerce': ['retail', 'marketplace'],
    'healthtech': ['healthcare', 'medical'],
    'edtech': ['education', 'learning'],
    'saas': ['software', 'enterprise software'],
  };

  const related1 = RELATED_INDUSTRIES[industry1] || [];
  const related2 = RELATED_INDUSTRIES[industry2] || [];

  return related1.includes(industry2) || related2.includes(industry1);
}

/**
 * SCOR-06: Calculate company relevance score.
 *
 * Returns 0-1 score combining:
 * - Target company match: 1.0 if match, 0.0 if not
 * - Company tier: 1.0 (FAANG), 0.7 (unicorn), 0.4 (startup)
 * - Industry alignment: 1.0 if match/related, 0.3 if not
 *
 * Final score is average of available signals.
 *
 * @param candidateCompanies - Companies from candidate's experience
 * @param candidateIndustries - Industries from candidate's experience
 * @param companyTier - Pre-computed company tier (0-2)
 * @param context - Target companies and industries
 * @returns Score 0-1 combining tier, target, and industry signals
 */
export function calculateCompanyRelevance(
  candidateCompanies: string[],
  candidateIndustries: string[],
  companyTier: number,
  context: CompanyContext
): number {
  let score = 0;
  let signals = 0;

  // Signal 1: Target company match
  if (context.targetCompanies && context.targetCompanies.length > 0) {
    const normalizedCompanies = (candidateCompanies || []).map(c => c.toLowerCase().trim());
    const hasTargetCompany = context.targetCompanies.some(target => {
      const normalizedTarget = target.toLowerCase().trim();
      return normalizedCompanies.some(
        cc => cc.includes(normalizedTarget) || normalizedTarget.includes(cc)
      );
    });
    score += hasTargetCompany ? 1.0 : 0.0;
    signals++;
  }

  // Signal 2: Company tier score
  const tierScore = companyTier >= 2 ? 1.0 : companyTier >= 1 ? 0.7 : 0.4;
  score += tierScore;
  signals++;

  // Signal 3: Industry alignment
  if (context.targetIndustries && context.targetIndustries.length > 0) {
    const normalizedIndustries = (candidateIndustries || []).map(i => i.toLowerCase().trim());
    const hasMatchingIndustry = context.targetIndustries.some(target => {
      const normalizedTarget = target.toLowerCase().trim();
      return normalizedIndustries.some(
        ci =>
          ci.includes(normalizedTarget) ||
          normalizedTarget.includes(ci) ||
          areIndustriesRelated(ci, normalizedTarget)
      );
    });
    score += hasMatchingIndustry ? 1.0 : 0.3;
    signals++;
  }

  return signals > 0 ? score / signals : 0.5;
}
