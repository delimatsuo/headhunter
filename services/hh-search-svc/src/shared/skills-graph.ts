/**
 * Skills Graph - BFS-Based Skill Expansion
 *
 * Provides graph traversal of the skill taxonomy to find related skills.
 * Uses BFS with bidirectional relationship support for comprehensive expansion.
 *
 * Key Features:
 * - BFS traversal with configurable max depth
 * - Confidence scoring that decays with graph distance
 * - Bidirectional relationships (Python -> Django AND Django -> Python)
 * - LRU caching for hot path performance
 *
 * Usage:
 * ```typescript
 * import { expandSkills, getCachedSkillExpansion } from './skills-graph';
 *
 * // Find skills related to Python
 * const result = expandSkills('Python', 2, 10);
 * // Returns: { originalSkill: 'Python', relatedSkills: [{ skillName: 'Django', confidence: 0.9 }, ...] }
 *
 * // Use cached version for hot paths
 * const cached = getCachedSkillExpansion('Python', 2);
 * ```
 */

import {
    MASTER_SKILLS,
    getSkillByName,
    type Skill
} from './skills-master';

// ============================================================================
// TYPES
// ============================================================================

export interface SkillExpansionResult {
    originalSkill: string;
    originalSkillId: string | null;
    relatedSkills: Array<{
        skillId: string;
        skillName: string;
        relationshipType: 'direct' | 'indirect';
        distance: number;  // Graph hops from original skill
        confidence: number; // 1.0 for direct, decays with distance
    }>;
}

// ============================================================================
// BIDIRECTIONAL RELATIONSHIP INDEX
// ============================================================================

/**
 * Build reverse relationships at module load.
 * If skill A lists skill B in relatedSkillIds, then REVERSE_RELATIONSHIPS[B] includes A.
 * This enables bidirectional traversal (Django -> Python, not just Python -> Django).
 */
const REVERSE_RELATIONSHIPS = new Map<string, Set<string>>();

// Track counts for logging (suppressed in production)
let forwardRelationshipCount = 0;
let reverseRelationshipCount = 0;

// Build the reverse index
for (const skill of MASTER_SKILLS) {
    if (skill.relatedSkillIds && skill.relatedSkillIds.length > 0) {
        forwardRelationshipCount += skill.relatedSkillIds.length;

        for (const relatedId of skill.relatedSkillIds) {
            if (!REVERSE_RELATIONSHIPS.has(relatedId)) {
                REVERSE_RELATIONSHIPS.set(relatedId, new Set());
            }
            REVERSE_RELATIONSHIPS.get(relatedId)!.add(skill.id);
            reverseRelationshipCount++;
        }
    }
}

// Only log in development/test environments
if (process.env.NODE_ENV !== 'production' && process.env.NODE_ENV !== 'test') {
    console.log(`[skills-graph] Initialized: ${forwardRelationshipCount} forward relationships, ${reverseRelationshipCount} reverse relationships built`);
}

// ============================================================================
// SKILL LOOKUP INDEX
// ============================================================================

/**
 * Pre-built map from skill ID to skill object for O(1) lookups.
 */
const SKILL_BY_ID = new Map<string, Skill>();
for (const skill of MASTER_SKILLS) {
    SKILL_BY_ID.set(skill.id, skill);
}

// ============================================================================
// CONFIDENCE CALCULATION
// ============================================================================

/**
 * Calculate confidence score based on graph distance and market demand.
 *
 * - Direct relationships (distance=1): base confidence 0.9
 * - Indirect relationships (distance=2+): base confidence 0.6
 * - Boost 0.1 for 'critical' market demand skills
 * - Cap at 1.0
 */
function calculateConfidence(distance: number, marketDemand: string): number {
    // Base confidence based on distance
    let confidence = distance === 1 ? 0.9 : 0.6;

    // Boost for critical market demand
    if (marketDemand === 'critical') {
        confidence += 0.1;
    }

    // Cap at 1.0
    return Math.min(confidence, 1.0);
}

// ============================================================================
// BIDIRECTIONAL RELATIONSHIP LOOKUP
// ============================================================================

/**
 * Get all related skill IDs for a skill, including both forward and backward relationships.
 *
 * @example
 * getRelatedSkillIds('python') // => ['django', 'ml-fundamentals', 'data-analysis', ...plus skills that list Python as related]
 */
export function getRelatedSkillIds(skillId: string): string[] {
    const skill = SKILL_BY_ID.get(skillId);

    // Forward relationships (from the skill's relatedSkillIds)
    const forward = skill?.relatedSkillIds || [];

    // Backward relationships (skills that list this skill as related)
    const backward = REVERSE_RELATIONSHIPS.get(skillId);
    const backwardArray = backward ? Array.from(backward) : [];

    // Combine and deduplicate
    const combined = new Set([...forward, ...backwardArray]);
    return Array.from(combined);
}

// ============================================================================
// BFS EXPANSION
// ============================================================================

/**
 * Expand a skill to find semantically related skills using BFS traversal.
 *
 * Uses bidirectional relationship traversal:
 * - Forward: Python -> Django (Python lists Django as related)
 * - Backward: Django -> Python (Django is listed by Python, so we include Python)
 *
 * @param skillName - The skill name to expand (case-insensitive)
 * @param maxDepth - Maximum graph hops (default: 2)
 * @param maxResults - Maximum related skills to return (default: 10)
 * @returns SkillExpansionResult with related skills sorted by confidence
 */
export function expandSkills(
    skillName: string,
    maxDepth: number = 2,
    maxResults: number = 10
): SkillExpansionResult {
    // Lookup the skill
    const skill = getSkillByName(skillName);

    if (!skill) {
        // Unknown skill - return empty result
        return {
            originalSkill: skillName,
            originalSkillId: null,
            relatedSkills: []
        };
    }

    // BFS state
    const visited = new Set<string>();
    const queue: Array<{ skillId: string; distance: number }> = [];
    const relatedSkills: SkillExpansionResult['relatedSkills'] = [];

    // Initialize with the starting skill
    visited.add(skill.id);
    queue.push({ skillId: skill.id, distance: 0 });

    // BFS traversal
    while (queue.length > 0 && relatedSkills.length < maxResults) {
        const current = queue.shift()!;

        // Skip the original skill and respect max depth
        if (current.distance >= maxDepth) {
            continue;
        }

        // Get all related skills (bidirectional)
        const relatedIds = getRelatedSkillIds(current.skillId);

        for (const relatedId of relatedIds) {
            // Skip if already visited
            if (visited.has(relatedId)) {
                continue;
            }

            visited.add(relatedId);

            // Get the related skill
            const relatedSkill = SKILL_BY_ID.get(relatedId);
            if (!relatedSkill) {
                continue;
            }

            const distance = current.distance + 1;
            const confidence = calculateConfidence(distance, relatedSkill.marketDemand);

            // Add to results
            relatedSkills.push({
                skillId: relatedSkill.id,
                skillName: relatedSkill.name,
                relationshipType: distance === 1 ? 'direct' : 'indirect',
                distance,
                confidence
            });

            // Add to queue for further traversal (only if within max depth)
            if (distance < maxDepth) {
                queue.push({ skillId: relatedId, distance });
            }

            // Stop if we have enough results
            if (relatedSkills.length >= maxResults) {
                break;
            }
        }
    }

    // Sort by confidence (descending)
    relatedSkills.sort((a, b) => b.confidence - a.confidence);

    return {
        originalSkill: skill.name,
        originalSkillId: skill.id,
        relatedSkills
    };
}

// ============================================================================
// LRU CACHE
// ============================================================================

/**
 * Simple LRU cache with TTL support.
 * Uses Map ordering for LRU behavior.
 */
interface CacheEntry {
    result: SkillExpansionResult;
    timestamp: number;
}

const CACHE_MAX_SIZE = 500;
const CACHE_TTL_MS = 3600000; // 1 hour

const expansionCache = new Map<string, CacheEntry>();

/**
 * Get a cached skill expansion result, or compute and cache it.
 *
 * @param skillName - The skill name to expand
 * @param maxDepth - Maximum graph hops (default: 2)
 * @returns Cached or freshly computed SkillExpansionResult
 */
export function getCachedSkillExpansion(
    skillName: string,
    maxDepth: number = 2
): SkillExpansionResult {
    const cacheKey = `${skillName.toLowerCase()}:${maxDepth}`;
    const now = Date.now();

    // Check cache
    const cached = expansionCache.get(cacheKey);
    if (cached && (now - cached.timestamp) < CACHE_TTL_MS) {
        // Move to end for LRU (delete and re-add)
        expansionCache.delete(cacheKey);
        expansionCache.set(cacheKey, cached);
        return cached.result;
    }

    // Compute the expansion
    const result = expandSkills(skillName, maxDepth);

    // Enforce max size (remove oldest entries)
    while (expansionCache.size >= CACHE_MAX_SIZE) {
        // Map iterates in insertion order, so first key is oldest
        const oldestKey = expansionCache.keys().next().value;
        if (oldestKey !== undefined) {
            expansionCache.delete(oldestKey);
        } else {
            break;
        }
    }

    // Cache the result
    expansionCache.set(cacheKey, {
        result,
        timestamp: now
    });

    return result;
}

/**
 * Clear the skill expansion cache.
 * Useful for testing.
 */
export function clearSkillExpansionCache(): void {
    expansionCache.clear();
    // Only log in development/test environments
    if (process.env.NODE_ENV !== 'production' && process.env.NODE_ENV !== 'test') {
        console.log('[skills-graph] Cache cleared');
    }
}

// Log cache initialization only in development
if (process.env.NODE_ENV !== 'production' && process.env.NODE_ENV !== 'test') {
    console.log(`[skills-graph] LRU cache initialized (max size: ${CACHE_MAX_SIZE}, TTL: ${CACHE_TTL_MS}ms)`);
}
