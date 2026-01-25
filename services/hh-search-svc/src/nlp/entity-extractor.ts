/**
 * Entity Extractor for Natural Language Search
 * Uses Together AI JSON mode for structured extraction of recruiting entities.
 * @module nlp/entity-extractor
 * @see NLNG-02: Entity extraction from natural language queries
 */

import Together from 'together-ai';
import type { Logger } from 'pino';
import type { ExtractedEntities } from './types';

/**
 * JSON schema for entity extraction.
 * Together AI will enforce this structure in the response.
 */
const ENTITY_SCHEMA = {
  type: 'object',
  properties: {
    role: {
      type: 'string',
      description: 'Job role or title mentioned (developer, engineer, manager, analyst, designer, etc.)'
    },
    skills: {
      type: 'array',
      items: { type: 'string' },
      description: 'Technical or soft skills explicitly mentioned in the query'
    },
    seniority: {
      type: 'string',
      enum: ['junior', 'mid', 'senior', 'staff', 'principal', 'lead', 'manager', 'director', 'vp', 'c-level'],
      description: 'Seniority or experience level mentioned'
    },
    location: {
      type: 'string',
      description: 'City, state, region, or country mentioned'
    },
    remote: {
      type: 'boolean',
      description: 'Whether remote work is mentioned or implied'
    },
    experienceYears: {
      type: 'object',
      properties: {
        min: { type: 'number', description: 'Minimum years of experience' },
        max: { type: 'number', description: 'Maximum years of experience' }
      },
      description: 'Years of experience if mentioned (e.g., "5+ years" -> min: 5, "3-5 years" -> min: 3, max: 5)'
    }
  },
  required: []  // All fields optional - only extract what's present
} as const;

/**
 * System prompt for entity extraction.
 * Emphasizes extracting ONLY what is explicitly mentioned.
 */
const SYSTEM_PROMPT = `You are a recruiting query parser. Extract structured entities from job search queries.

IMPORTANT RULES:
1. ONLY extract entities that are EXPLICITLY mentioned in the query
2. Do NOT infer or assume skills based on the role (e.g., don't add "Python" just because it says "developer")
3. If an entity is not mentioned, omit it from the response
4. For seniority, match common terms: "senior"/"sr." -> senior, "junior"/"jr." -> junior, "lead" -> lead
5. For experience years, extract ranges like "5+ years" -> min: 5, "3-5 years" -> min: 3, max: 5
6. For remote, detect "remote", "work from home", "wfh", "distributed", "anywhere"
7. Support Portuguese terms: "senior" or "senhor" -> senior, "pleno" -> mid, "junior" or "junior" -> junior, "remoto" -> remote: true

Respond ONLY with valid JSON matching the schema. No explanations.`;

/**
 * Configuration for EntityExtractor.
 */
export interface EntityExtractorConfig {
  apiKey: string;
  model: string;
  timeoutMs: number;
  maxRetries: number;
}

/**
 * Dependencies for EntityExtractor.
 */
export interface EntityExtractorDeps {
  config: EntityExtractorConfig;
  logger: Logger;
}

/**
 * Result of entity extraction.
 */
export interface EntityExtractionResult {
  entities: ExtractedEntities;
  timingMs: number;
  fromCache: boolean;
}

/**
 * EntityExtractor class that uses Together AI JSON mode for structured extraction.
 *
 * Features:
 * - LLM-based entity extraction with JSON schema enforcement
 * - Hallucination filtering (skills not in query are filtered out)
 * - Portuguese term normalization (senior, pleno -> mid, junior)
 * - Timeout and retry handling with graceful fallback
 */
export class EntityExtractor {
  private readonly client: Together;
  private readonly model: string;
  private readonly timeoutMs: number;
  private readonly maxRetries: number;
  private readonly logger: Logger;

  constructor(deps: EntityExtractorDeps) {
    this.client = new Together({ apiKey: deps.config.apiKey });
    this.model = deps.config.model;
    this.timeoutMs = deps.config.timeoutMs;
    this.maxRetries = deps.config.maxRetries;
    this.logger = deps.logger.child({ module: 'entity-extractor' });
  }

  /**
   * Extract entities from a natural language query.
   *
   * @param query - Natural language search query
   * @returns Extracted entities (may be partial if some fields not detected)
   */
  async extractEntities(query: string): Promise<EntityExtractionResult> {
    const start = Date.now();
    const trimmedQuery = query.trim();

    // Skip extraction for very short or obviously invalid queries
    if (trimmedQuery.length < 3 || !this.looksLikeNaturalLanguage(trimmedQuery)) {
      this.logger.debug({ query: trimmedQuery }, 'Skipping extraction for short/invalid query');
      return {
        entities: { skills: [] },
        timingMs: Date.now() - start,
        fromCache: false
      };
    }

    let lastError: Error | null = null;

    for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
      try {
        const entities = await this.doExtraction(trimmedQuery, attempt);
        return {
          entities,
          timingMs: Date.now() - start,
          fromCache: false
        };
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));
        this.logger.warn(
          { error: lastError.message, attempt, maxRetries: this.maxRetries },
          'Entity extraction attempt failed'
        );

        if (attempt < this.maxRetries) {
          // Brief backoff before retry
          await this.delay(100 * attempt);
        }
      }
    }

    // All retries failed - return empty entities
    this.logger.error(
      { error: lastError?.message, query: trimmedQuery },
      'Entity extraction failed after all retries'
    );

    return {
      entities: { skills: [] },
      timingMs: Date.now() - start,
      fromCache: false
    };
  }

  /**
   * Perform the actual extraction call to Together AI.
   */
  private async doExtraction(query: string, _attempt: number): Promise<ExtractedEntities> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await this.client.chat.completions.create({
        model: this.model,
        messages: [
          { role: 'system', content: SYSTEM_PROMPT },
          { role: 'user', content: `Extract entities from: "${query}"` }
        ],
        response_format: {
          type: 'json_schema',
          json_schema: {
            name: 'query_entities',
            schema: ENTITY_SCHEMA
          }
        },
        temperature: 0.1,  // Low temperature for consistent extraction
        max_tokens: 256    // Entities don't need many tokens
      }, {
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      const content = response.choices?.[0]?.message?.content;
      if (!content) {
        throw new Error('Empty response from Together AI');
      }

      const parsed = JSON.parse(content) as Partial<ExtractedEntities>;

      // Validate and normalize the response
      return this.normalizeEntities(parsed, query);
    } catch (error) {
      clearTimeout(timeoutId);

      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error(`Entity extraction timed out after ${this.timeoutMs}ms`);
      }
      throw error;
    }
  }

  /**
   * Normalize and validate extracted entities.
   * Ensures skills is always an array and validates seniority enum.
   */
  private normalizeEntities(
    parsed: Partial<ExtractedEntities>,
    originalQuery: string
  ): ExtractedEntities {
    const result: ExtractedEntities = {
      skills: []
    };

    // Role
    if (typeof parsed.role === 'string' && parsed.role.trim()) {
      result.role = parsed.role.trim().toLowerCase();
    }

    // Skills - filter out hallucinated skills
    if (Array.isArray(parsed.skills)) {
      const validSkills = parsed.skills
        .filter((s): s is string => typeof s === 'string' && s.trim().length > 0)
        .map(s => s.trim())
        .filter(s => this.isSkillMentioned(s, originalQuery));

      result.skills = validSkills;

      // Log if skills were filtered out
      if (validSkills.length < parsed.skills.length) {
        this.logger.debug(
          {
            original: parsed.skills,
            filtered: validSkills,
            query: originalQuery
          },
          'Filtered hallucinated skills'
        );
      }
    }

    // Seniority
    if (parsed.seniority) {
      const normalizedSeniority = this.normalizeSeniority(parsed.seniority);
      if (normalizedSeniority) {
        result.seniority = normalizedSeniority;
      }
    }

    // Location
    if (typeof parsed.location === 'string' && parsed.location.trim()) {
      result.location = parsed.location.trim();
    }

    // Remote
    if (typeof parsed.remote === 'boolean') {
      result.remote = parsed.remote;
    }

    // Experience years
    if (parsed.experienceYears) {
      const exp = parsed.experienceYears;
      if (typeof exp.min === 'number' || typeof exp.max === 'number') {
        result.experienceYears = {
          min: typeof exp.min === 'number' ? exp.min : undefined,
          max: typeof exp.max === 'number' ? exp.max : undefined
        };
      }
    }

    return result;
  }

  /**
   * Check if a skill appears to be mentioned in the original query.
   * Uses fuzzy matching to allow for minor variations.
   */
  private isSkillMentioned(skill: string, query: string): boolean {
    const skillLower = skill.toLowerCase();
    const queryLower = query.toLowerCase();

    // Direct mention
    if (queryLower.includes(skillLower)) {
      return true;
    }

    // Check for common abbreviations (both directions)
    const abbreviations: Record<string, string[]> = {
      'javascript': ['js', 'javascript'],
      'typescript': ['ts', 'typescript'],
      'kubernetes': ['k8s', 'kubernetes'],
      'postgresql': ['postgres', 'psql', 'postgresql'],
      'machine learning': ['ml', 'machine learning'],
      'artificial intelligence': ['ai', 'artificial intelligence'],
      'amazon web services': ['aws', 'amazon web services'],
      'google cloud platform': ['gcp', 'google cloud platform'],
      'continuous integration': ['ci', 'continuous integration'],
      'continuous deployment': ['cd', 'continuous deployment'],
      'react.js': ['react', 'reactjs', 'react.js'],
      'node.js': ['node', 'nodejs', 'node.js'],
      'vue.js': ['vue', 'vuejs', 'vue.js'],
      'angular.js': ['angular', 'angularjs', 'angular.js'],
      'next.js': ['next', 'nextjs', 'next.js'],
      'graphql': ['graphql', 'gql'],
      'mongodb': ['mongo', 'mongodb']
    };

    // Check if skill matches any abbreviation pattern
    for (const [full, variants] of Object.entries(abbreviations)) {
      // If the skill is the full name or a variant
      if (skillLower === full || variants.includes(skillLower)) {
        // Check if any variant is in the query
        for (const variant of variants) {
          // Use word boundary matching for short abbreviations
          if (variant.length <= 3) {
            const wordBoundaryRegex = new RegExp(`\\b${this.escapeRegex(variant)}\\b`, 'i');
            if (wordBoundaryRegex.test(query)) {
              return true;
            }
          } else if (queryLower.includes(variant)) {
            return true;
          }
        }
        // Also check the full name
        if (queryLower.includes(full)) {
          return true;
        }
      }
    }

    return false;
  }

  /**
   * Escape special regex characters in a string.
   */
  private escapeRegex(str: string): string {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  /**
   * Normalize seniority terms to standard enum values.
   */
  private normalizeSeniority(value: string): ExtractedEntities['seniority'] | null {
    const normalized = value.toLowerCase().trim();

    const mapping: Record<string, ExtractedEntities['seniority']> = {
      'junior': 'junior',
      'jr': 'junior',
      'jr.': 'junior',
      'entry': 'junior',
      'entry-level': 'junior',
      'estagiario': 'junior',

      'mid': 'mid',
      'mid-level': 'mid',
      'midlevel': 'mid',
      'intermediate': 'mid',
      'pleno': 'mid',

      'senior': 'senior',
      'sr': 'senior',
      'sr.': 'senior',
      'senhor': 'senior',

      'staff': 'staff',

      'principal': 'principal',

      'lead': 'lead',
      'tech lead': 'lead',
      'team lead': 'lead',

      'manager': 'manager',
      'mgr': 'manager',
      'gerente': 'manager',

      'director': 'director',
      'dir': 'director',
      'diretor': 'director',

      'vp': 'vp',
      'vice president': 'vp',

      'c-level': 'c-level',
      'cto': 'c-level',
      'ceo': 'c-level',
      'cfo': 'c-level',
      'cpo': 'c-level'
    };

    return mapping[normalized] ?? null;
  }

  /**
   * Quick check if input looks like natural language vs random characters.
   */
  private looksLikeNaturalLanguage(text: string): boolean {
    // Must have at least one letter
    if (!/[a-zA-Z]/.test(text)) {
      return false;
    }

    // Check for minimum word-like patterns
    const words = text.split(/\s+/).filter(w => w.length > 0);
    if (words.length === 0) {
      return false;
    }

    // At least one word should have multiple letters
    const hasRealWord = words.some(w => (w.match(/[a-zA-Z]/g) ?? []).length >= 2);
    return hasRealWord;
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

/**
 * Factory function to create EntityExtractor with default config.
 */
export function createEntityExtractor(
  logger: Logger,
  config?: Partial<EntityExtractorConfig>
): EntityExtractor {
  const apiKey = config?.apiKey ?? process.env.TOGETHER_API_KEY;
  if (!apiKey) {
    throw new Error('TOGETHER_API_KEY environment variable is required');
  }

  return new EntityExtractor({
    config: {
      apiKey,
      model: config?.model ?? 'meta-llama/Llama-3.3-70B-Instruct-Turbo',
      timeoutMs: config?.timeoutMs ?? 150,  // 150ms per RESEARCH.md latency budget
      maxRetries: config?.maxRetries ?? 2
    },
    logger
  });
}

/**
 * Convenience function for one-off extraction.
 */
export async function extractEntities(
  extractor: EntityExtractor,
  query: string
): Promise<ExtractedEntities> {
  const result = await extractor.extractEntities(query);
  return result.entities;
}
