/**
 * Query Parser - NLP Pipeline Orchestrator
 *
 * Coordinates IntentRouter, EntityExtractor, and QueryExpander into a unified
 * NLP pipeline for natural language search queries.
 *
 * Key Features:
 * - Single entry point for query parsing
 * - In-memory cache for extraction results (5-min TTL, 500 max entries)
 * - Timing tracking for each pipeline stage
 * - Graceful fallback for low-confidence or failed parsing
 * - Latency budget enforcement (50ms intent + 100ms extraction + 5ms expansion)
 *
 * Usage:
 * ```typescript
 * import { QueryParser } from './query-parser';
 *
 * const parser = new QueryParser({
 *   generateEmbedding,
 *   logger,
 *   togetherApiKey: process.env.TOGETHER_API_KEY
 * });
 *
 * await parser.initialize();
 * const result = await parser.parse('senior python developer in NYC');
 * ```
 *
 * @module nlp/query-parser
 * @see NLNG-04: Query parser orchestrator
 */

import type { Logger } from 'pino';
import { createHash } from 'crypto';
import type { ParsedQuery, NLPConfig, IntentType, ExtractedEntities } from './types';
import { IntentRouter } from './intent-router';
import { createEntityExtractor, type EntityExtractor } from './entity-extractor';
import { QueryExpander } from './query-expander';
import { expandSemanticSynonyms } from './semantic-synonyms';

// ============================================================================
// CONFIGURATION
// ============================================================================

const DEFAULT_NLP_CONFIG: NLPConfig = {
  enabled: true,
  intentConfidenceThreshold: 0.6,
  extractionTimeoutMs: 100,
  cacheExtractionResults: true,
  enableQueryExpansion: true,
  expansionDepth: 1,
  expansionConfidenceThreshold: 0.8
};

// ============================================================================
// TYPES
// ============================================================================

export interface QueryParserDeps {
  generateEmbedding: (text: string) => Promise<number[]>;
  logger: Logger;
  config?: Partial<NLPConfig>;
  togetherApiKey?: string;
}

/**
 * Simple in-memory cache entry for extraction results.
 */
interface CacheEntry {
  entities: ExtractedEntities;
  timestamp: number;
}

// ============================================================================
// CACHE CONFIGURATION
// ============================================================================

const EXTRACTION_CACHE = new Map<string, CacheEntry>();
const CACHE_TTL_MS = 300_000;  // 5 minutes
const CACHE_MAX_SIZE = 500;

// ============================================================================
// QUERY PARSER CLASS
// ============================================================================

export class QueryParser {
  private readonly config: NLPConfig;
  private readonly logger: Logger;
  private readonly intentRouter: IntentRouter;
  private readonly entityExtractor: EntityExtractor;
  private readonly queryExpander: QueryExpander;
  private readonly generateEmbedding: (text: string) => Promise<number[]>;
  private initialized = false;
  private initPromise: Promise<void> | null = null;

  constructor(deps: QueryParserDeps) {
    this.config = { ...DEFAULT_NLP_CONFIG, ...deps.config };
    this.logger = deps.logger.child({ module: 'query-parser' });
    this.generateEmbedding = deps.generateEmbedding;

    // Initialize components
    this.intentRouter = new IntentRouter(
      { generateEmbedding: deps.generateEmbedding, logger: deps.logger },
      this.config.intentConfidenceThreshold
    );

    this.entityExtractor = createEntityExtractor(deps.logger, {
      apiKey: deps.togetherApiKey,
      timeoutMs: this.config.extractionTimeoutMs
    });

    this.queryExpander = new QueryExpander(deps.logger, {
      enabled: this.config.enableQueryExpansion,
      maxDepth: this.config.expansionDepth,
      confidenceThreshold: this.config.expansionConfidenceThreshold
    });
  }

  /**
   * Initialize the parser (precomputes intent route embeddings).
   * Safe to call multiple times - idempotent.
   */
  async initialize(): Promise<void> {
    if (this.initialized) return;

    if (this.initPromise) {
      return this.initPromise;
    }

    this.initPromise = this.doInitialize();
    await this.initPromise;
  }

  private async doInitialize(): Promise<void> {
    this.logger.info('Initializing query parser...');
    const start = Date.now();

    await this.intentRouter.initialize();

    this.initialized = true;
    this.logger.info(
      { durationMs: Date.now() - start },
      'Query parser initialization complete'
    );
  }

  /**
   * Parse a natural language query.
   *
   * Pipeline:
   * 1. Generate query embedding (reused for search)
   * 2. Classify intent using embedding similarity
   * 3. If structured_search intent with sufficient confidence:
   *    a. Extract entities using LLM (with caching)
   *    b. Expand skills using ontology
   * 4. Return ParsedQuery with all extracted data
   *
   * @param query - Natural language search query
   * @param queryEmbedding - Optional pre-computed embedding (saves ~50ms)
   */
  async parse(query: string, queryEmbedding?: number[]): Promise<ParsedQuery> {
    const totalStart = Date.now();
    const timings = {
      intentMs: 0,
      extractionMs: 0,
      expansionMs: 0,
      totalMs: 0
    };

    // Ensure initialized
    if (!this.initialized) {
      await this.initialize();
    }

    const trimmedQuery = query.trim();

    // Quick bypass for very short queries
    if (trimmedQuery.length < 3) {
      return this.createFallbackResult(trimmedQuery, timings, totalStart);
    }

    // Step 1: Get or generate embedding
    let embedding = queryEmbedding;
    if (!embedding) {
      try {
        embedding = await this.generateEmbedding(trimmedQuery);
      } catch (error) {
        this.logger.warn({ error }, 'Failed to generate query embedding');
        return this.createFallbackResult(trimmedQuery, timings, totalStart);
      }
    }

    // Step 2: Classify intent
    const intentStart = Date.now();
    const classification = this.intentRouter.classifyIntent(embedding);
    timings.intentMs = Date.now() - intentStart;

    this.logger.debug(
      {
        intent: classification.intent,
        confidence: classification.confidence.toFixed(3),
        intentMs: timings.intentMs
      },
      'Intent classified'
    );

    // Step 3: If not structured search or low confidence, return fallback
    if (
      classification.intent === 'keyword_fallback' ||
      classification.intent === 'similarity_search' ||
      classification.confidence < this.config.intentConfidenceThreshold
    ) {
      return this.createFallbackResult(
        trimmedQuery,
        timings,
        totalStart,
        classification.intent,
        classification.confidence
      );
    }

    // Step 4: Extract entities (with caching)
    const extractionStart = Date.now();
    let entities: ExtractedEntities;
    let fromCache = false;

    if (this.config.cacheExtractionResults) {
      const cached = this.getFromCache(trimmedQuery);
      if (cached) {
        entities = cached;
        fromCache = true;
        this.logger.debug({ query: trimmedQuery }, 'Entity extraction cache hit');
      } else {
        const extractionResult = await this.entityExtractor.extractEntities(trimmedQuery);
        entities = extractionResult.entities;
        this.addToCache(trimmedQuery, entities);
      }
    } else {
      const extractionResult = await this.entityExtractor.extractEntities(trimmedQuery);
      entities = extractionResult.entities;
    }

    timings.extractionMs = Date.now() - extractionStart;

    this.logger.debug(
      {
        entities: {
          role: entities.role,
          skillCount: entities.skills.length,
          seniority: entities.seniority,
          location: entities.location,
          remote: entities.remote
        },
        extractionMs: timings.extractionMs,
        fromCache
      },
      'Entities extracted'
    );

    // Step 5: Expand skills using ontology
    const expansionStart = Date.now();
    const expansion = this.queryExpander.expandSkills(entities.skills);
    timings.expansionMs = Date.now() - expansionStart;

    this.logger.debug(
      {
        explicit: expansion.explicitSkills.length,
        expanded: expansion.expandedSkills.length - expansion.explicitSkills.length,
        expansionMs: timings.expansionMs
      },
      'Skills expanded'
    );

    // Step 6: Expand semantic synonyms for seniority and roles
    const semanticExpansion = expandSemanticSynonyms({
      role: entities.role,
      seniority: entities.seniority
    });

    this.logger.debug(
      {
        originalSeniority: entities.seniority,
        expandedSeniorities: semanticExpansion.expandedSeniorities,
        originalRole: entities.role,
        expandedRoles: semanticExpansion.expandedRoles
      },
      'Semantic synonyms expanded'
    );

    timings.totalMs = Date.now() - totalStart;

    const result: ParsedQuery = {
      originalQuery: trimmedQuery,
      parseMethod: 'nlp',
      confidence: classification.confidence,
      intent: classification.intent,
      entities: {
        ...entities,
        expandedSkills: expansion.allSkills.filter(
          s => !entities.skills.map(sk => sk.toLowerCase()).includes(s.toLowerCase())
        )
      },
      semanticExpansion,
      timings
    };

    this.logger.info(
      {
        query: trimmedQuery.slice(0, 50),
        parseMethod: result.parseMethod,
        confidence: result.confidence.toFixed(3),
        intent: result.intent,
        totalMs: timings.totalMs
      },
      'Query parsing complete'
    );

    return result;
  }

  /**
   * Create a fallback result for queries that can't be NLP-parsed.
   */
  private createFallbackResult(
    query: string,
    timings: ParsedQuery['timings'],
    startTime: number,
    intent: IntentType = 'keyword_fallback',
    confidence = 0
  ): ParsedQuery {
    timings.totalMs = Date.now() - startTime;

    return {
      originalQuery: query,
      parseMethod: 'keyword_fallback',
      confidence,
      intent,
      entities: {
        skills: [],
        expandedSkills: []
      },
      timings
    };
  }

  /**
   * Get cached extraction result.
   */
  private getFromCache(query: string): ExtractedEntities | null {
    const key = this.getCacheKey(query);
    const entry = EXTRACTION_CACHE.get(key);

    if (!entry) return null;

    // Check TTL
    if (Date.now() - entry.timestamp > CACHE_TTL_MS) {
      EXTRACTION_CACHE.delete(key);
      return null;
    }

    return entry.entities;
  }

  /**
   * Add extraction result to cache.
   */
  private addToCache(query: string, entities: ExtractedEntities): void {
    const key = this.getCacheKey(query);

    // Enforce max size (simple LRU: remove oldest)
    if (EXTRACTION_CACHE.size >= CACHE_MAX_SIZE) {
      const firstKey = EXTRACTION_CACHE.keys().next().value;
      if (firstKey !== undefined) {
        EXTRACTION_CACHE.delete(firstKey);
      }
    }

    EXTRACTION_CACHE.set(key, {
      entities,
      timestamp: Date.now()
    });
  }

  /**
   * Generate cache key from query.
   */
  private getCacheKey(query: string): string {
    return createHash('sha256')
      .update(query.toLowerCase().trim())
      .digest('hex')
      .slice(0, 16);
  }

  /**
   * Check if parser is initialized.
   */
  isInitialized(): boolean {
    return this.initialized;
  }

  /**
   * Get current NLP configuration.
   */
  getConfig(): NLPConfig {
    return { ...this.config };
  }

  /**
   * Clear extraction cache (for testing).
   */
  static clearCache(): void {
    EXTRACTION_CACHE.clear();
  }
}

// ============================================================================
// CONVENIENCE FUNCTION
// ============================================================================

/**
 * Convenience function for one-off parsing.
 * Creates a new parser instance each time - prefer using QueryParser class
 * for production usage to benefit from initialization and caching.
 */
export async function parseNaturalLanguageQuery(
  query: string,
  deps: QueryParserDeps,
  queryEmbedding?: number[]
): Promise<ParsedQuery> {
  const parser = new QueryParser(deps);
  return parser.parse(query, queryEmbedding);
}
