/**
 * Skills Service - Search-Optimized Wrapper
 *
 * Provides O(1) skill normalization and lookups for hot paths in search.
 * Built on top of skills-master.ts taxonomy.
 *
 * Key Features:
 * - O(1) alias-to-canonical mapping via pre-built Map
 * - Case-insensitive lookups
 * - Safe for use in search hot paths (no linear scans)
 *
 * Usage:
 * ```typescript
 * import { normalizeSkillName, skillsMatch } from './skills-service';
 *
 * normalizeSkillName('JS') // => 'JavaScript'
 * normalizeSkillName('K8s') // => 'Kubernetes'
 * skillsMatch('JavaScript', 'JS') // => true
 * ```
 */

import {
    MASTER_SKILLS,
    getSkillByName,
    matchSkillName,
    searchSkills,
    SKILL_CATEGORIES,
    type Skill,
    type SkillCategory
} from './skills-master';

// ============================================================================
// O(1) ALIAS MAPPING
// ============================================================================

/**
 * Pre-built map from aliases (lowercase) to canonical skill names.
 * Built once at module load for O(1) lookups.
 */
const ALIAS_TO_CANONICAL = new Map<string, string>();

// Build the map at module load
for (const skill of MASTER_SKILLS) {
    // Map canonical name to itself (lowercase)
    ALIAS_TO_CANONICAL.set(skill.name.toLowerCase(), skill.name);

    // Map all aliases to canonical name
    if (skill.aliases) {
        for (const alias of skill.aliases) {
            ALIAS_TO_CANONICAL.set(alias.toLowerCase(), skill.name);
        }
    }
}

// Log initialization for verification
console.log(`[skills-service] Initialized with ${ALIAS_TO_CANONICAL.size} skill mappings`);

// ============================================================================
// O(1) NORMALIZATION FUNCTIONS
// ============================================================================

/**
 * Normalize any skill name/alias to canonical form.
 * O(1) lookup - safe for hot paths in search.
 *
 * @example
 * normalizeSkillName('JS') // => 'JavaScript'
 * normalizeSkillName('k8s') // => 'Kubernetes'
 * normalizeSkillName('PYTHON') // => 'Python'
 * normalizeSkillName('UnknownSkill') // => 'UnknownSkill' (passthrough)
 */
export function normalizeSkillName(input: string): string {
    const normalized = input.toLowerCase().trim();
    return ALIAS_TO_CANONICAL.get(normalized) || input;
}

/**
 * Check if two skill names refer to the same skill.
 * Handles aliases and case differences.
 *
 * @example
 * skillsMatch('JavaScript', 'JS') // => true
 * skillsMatch('kubernetes', 'K8s') // => true
 * skillsMatch('Python', 'Java') // => false
 */
export function skillsMatch(skill1: string, skill2: string): boolean {
    return normalizeSkillName(skill1) === normalizeSkillName(skill2);
}

/**
 * Get all known aliases for a canonical skill name.
 *
 * @example
 * getSkillAliases('JavaScript') // => ['JS', 'ECMAScript']
 * getSkillAliases('Kubernetes') // => ['K8s']
 */
export function getSkillAliases(skillName: string): string[] {
    const skill = getSkillByName(skillName);
    return skill?.aliases || [];
}

/**
 * Get the canonical skill ID for storage/indexing.
 *
 * @example
 * getCanonicalSkillId('JS') // => 'javascript'
 * getCanonicalSkillId('K8s') // => 'kubernetes'
 */
export function getCanonicalSkillId(input: string): string {
    const canonicalName = normalizeSkillName(input);
    const skill = getSkillByName(canonicalName);
    return skill?.id || input.toLowerCase().replace(/[^a-z0-9]+/g, '-');
}

// ============================================================================
// RE-EXPORTS FROM SKILLS-MASTER
// ============================================================================

// Re-export from skills-master for convenience
export {
    MASTER_SKILLS,
    SKILL_CATEGORIES,
    getSkillByName,
    matchSkillName,
    searchSkills,
    type Skill,
    type SkillCategory
} from './skills-master';

// ============================================================================
// RE-EXPORTS FROM SKILLS-GRAPH
// ============================================================================

// Re-export skill expansion functions for graph-based skill lookups
export {
    expandSkills,
    getCachedSkillExpansion,
    getRelatedSkillIds,
    clearSkillExpansionCache,
    type SkillExpansionResult
} from './skills-graph';
