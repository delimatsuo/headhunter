/**
 * Query Expander - Skills Ontology-Based Query Expansion
 *
 * Expands user search queries with related skills from the skills ontology.
 * When a user searches for "Python developer", this module automatically
 * includes Django, Flask, FastAPI as related skills to improve recall
 * while weighting them lower than explicit skills.
 *
 * Key Features:
 * - Configurable expansion depth (default: 1 hop)
 * - Confidence threshold filtering (default: >= 0.8)
 * - Max expansions per skill limit
 * - Explicit skills get weight 1.0, expanded skills get reduced weight (0.6x)
 * - In-memory graph lookup completes in under 5ms
 *
 * Usage:
 * ```typescript
 * import { QueryExpander } from './query-expander';
 *
 * const expander = new QueryExpander(logger);
 * const result = expander.expandSkills(['Python', 'React']);
 * // result.allSkills = ['Python', 'React', 'Django', 'Flask', 'JavaScript', ...]
 * ```
 */

import type { Logger } from 'pino';

// Import from the local shared directory (copied in Task 0)
import {
  getCachedSkillExpansion,
  type SkillExpansionResult
} from '../shared/skills-graph';

// Re-export for consumers
export type { SkillExpansionResult };

// ============================================================================
// TYPES
// ============================================================================

export interface ExpandedSkill {
  name: string;
  isExplicit: boolean;  // true if user mentioned it, false if expanded
  confidence: number;   // 1.0 for explicit, decay for expanded
  source?: string;      // which explicit skill it expanded from
}

export interface QueryExpansionResult {
  explicitSkills: string[];
  expandedSkills: ExpandedSkill[];
  allSkills: string[];  // Union for search queries
  timingMs: number;
}

export interface QueryExpanderConfig {
  enabled: boolean;
  maxDepth: number;           // Graph traversal depth (default: 1)
  confidenceThreshold: number; // Min confidence to include (default: 0.8)
  maxExpansionsPerSkill: number; // Limit expanded skills per input (default: 5)
  expandedSkillWeight: number;   // Weight multiplier for expanded skills (default: 0.6)
}

// ============================================================================
// DEFAULT CONFIG
// ============================================================================

const DEFAULT_CONFIG: QueryExpanderConfig = {
  enabled: true,
  maxDepth: 1,
  confidenceThreshold: 0.8,
  maxExpansionsPerSkill: 5,
  expandedSkillWeight: 0.6
};

// ============================================================================
// QUERY EXPANDER CLASS
// ============================================================================

export class QueryExpander {
  private readonly config: QueryExpanderConfig;
  private readonly logger: Logger;

  constructor(logger: Logger, config?: Partial<QueryExpanderConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.logger = logger.child({ module: 'query-expander' });
  }

  /**
   * Expand a list of skills using the skills ontology.
   *
   * @param skills - Explicit skills from user query
   * @returns Expansion result with explicit and expanded skills
   */
  expandSkills(skills: string[]): QueryExpansionResult {
    const start = Date.now();

    if (!this.config.enabled || skills.length === 0) {
      return {
        explicitSkills: skills,
        expandedSkills: skills.map(s => ({
          name: s,
          isExplicit: true,
          confidence: 1.0
        })),
        allSkills: skills,
        timingMs: Date.now() - start
      };
    }

    // Track all skills to avoid duplicates
    const seenSkills = new Set<string>(skills.map(s => s.toLowerCase()));
    const expandedSkills: ExpandedSkill[] = [];

    // Add explicit skills first
    for (const skill of skills) {
      expandedSkills.push({
        name: skill,
        isExplicit: true,
        confidence: 1.0
      });
    }

    // Expand each explicit skill
    for (const skill of skills) {
      try {
        const expansion = this.expandSingleSkill(skill, seenSkills);

        for (const expanded of expansion) {
          seenSkills.add(expanded.name.toLowerCase());
          expandedSkills.push(expanded);
        }
      } catch (error) {
        this.logger.warn(
          { error: error instanceof Error ? error.message : error, skill },
          'Failed to expand skill'
        );
      }
    }

    // Build allSkills list (for search queries)
    const allSkills = expandedSkills.map(s => s.name);

    const timingMs = Date.now() - start;

    this.logger.debug(
      {
        explicit: skills.length,
        expanded: expandedSkills.length - skills.length,
        total: allSkills.length,
        timingMs
      },
      'Query expansion complete'
    );

    return {
      explicitSkills: skills,
      expandedSkills,
      allSkills,
      timingMs
    };
  }

  /**
   * Expand a single skill using the skills graph.
   */
  private expandSingleSkill(
    skill: string,
    seenSkills: Set<string>
  ): ExpandedSkill[] {
    const result: ExpandedSkill[] = [];

    // Use cached skill expansion from skills-graph.ts
    let expansion: SkillExpansionResult;
    try {
      expansion = getCachedSkillExpansion(skill, this.config.maxDepth);
    } catch (error) {
      // Skill not found in ontology - that's OK, just don't expand
      this.logger.trace({ skill }, 'Skill not found in ontology');
      return result;
    }

    // If no related skills, return empty
    if (!expansion.relatedSkills || expansion.relatedSkills.length === 0) {
      return result;
    }

    // Filter and limit expansions
    let count = 0;
    for (const related of expansion.relatedSkills) {
      // Skip if already seen
      if (seenSkills.has(related.skillName.toLowerCase())) {
        continue;
      }

      // Skip if below confidence threshold
      if (related.confidence < this.config.confidenceThreshold) {
        continue;
      }

      // Only include direct relations for now (depth=1)
      if (related.relationshipType !== 'direct') {
        continue;
      }

      // Apply expansion limit
      if (count >= this.config.maxExpansionsPerSkill) {
        break;
      }

      result.push({
        name: related.skillName,
        isExplicit: false,
        confidence: related.confidence * this.config.expandedSkillWeight,
        source: skill
      });

      count++;
    }

    return result;
  }

  /**
   * Get expanded skills as a simple array for search queries.
   * Explicit skills appear first, then expanded skills.
   */
  getSearchSkills(skills: string[]): string[] {
    const result = this.expandSkills(skills);
    return result.allSkills;
  }

  /**
   * Get expanded skills with weights for scoring.
   * Returns map of skill name -> weight (1.0 for explicit, lower for expanded).
   */
  getSkillWeights(skills: string[]): Map<string, number> {
    const result = this.expandSkills(skills);
    const weights = new Map<string, number>();

    for (const expanded of result.expandedSkills) {
      weights.set(expanded.name.toLowerCase(), expanded.confidence);
    }

    return weights;
  }

  /**
   * Update configuration at runtime.
   */
  updateConfig(config: Partial<QueryExpanderConfig>): void {
    Object.assign(this.config, config);
    this.logger.info({ config: this.config }, 'Query expander config updated');
  }

  /**
   * Get current configuration.
   */
  getConfig(): QueryExpanderConfig {
    return { ...this.config };
  }
}

// ============================================================================
// CONVENIENCE FUNCTION
// ============================================================================

/**
 * Convenience function for one-off expansion.
 */
export function expandQuerySkills(
  skills: string[],
  logger: Logger,
  config?: Partial<QueryExpanderConfig>
): QueryExpansionResult {
  const expander = new QueryExpander(logger, config);
  return expander.expandSkills(skills);
}
