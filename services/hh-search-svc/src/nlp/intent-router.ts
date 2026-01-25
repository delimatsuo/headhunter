/**
 * Intent Router for Phase 12: Natural Language Search
 * @see NLNG-01: Semantic router lite for intent classification
 *
 * Uses embedding-based semantic routing to classify queries into:
 * - structured_search: Role/skill/location queries
 * - similarity_search: "Candidates like X" queries
 * - keyword_fallback: Unrecognized or gibberish queries
 */

import type { Logger } from 'pino';
import type { IntentType, IntentRoute, IntentClassification } from './types';
import { cosineSimilarity, averageEmbeddings } from './vector-utils';

/**
 * Route definitions with sample utterances.
 * Route embeddings are computed lazily on first use.
 */
const INTENT_ROUTES: IntentRoute[] = [
  {
    name: 'structured_search',
    utterances: [
      // English structured queries
      'senior python developer in NYC',
      'ML engineers with 5 years experience',
      'remote frontend developers',
      'backend engineer in San Francisco',
      'data scientist with tensorflow experience',
      'product manager in fintech',
      'full stack developer javascript react',
      'devops engineer AWS kubernetes',
      'iOS developer swift objective-c',
      'android developer kotlin java',
      'senior software engineer at startups',
      'machine learning engineer remote',
      'staff engineer distributed systems',
      'principal engineer cloud architecture',
      'engineering manager with 10+ years',
      // Portuguese support for Brazilian recruiters
      'desenvolvedor python em Sao Paulo',
      'engenheiro de software senior',
      'desenvolvedor full stack remoto',
      'cientista de dados com experiencia em machine learning',
      'gerente de engenharia em fintech'
    ]
  },
  {
    name: 'similarity_search',
    utterances: [
      'candidates like John Smith',
      'similar profiles to this candidate',
      'more like this person',
      'find similar candidates',
      'profiles similar to candidate-123',
      'more candidates like her',
      'similar background to this engineer',
      'profiles matching this one',
      'find more people like this',
      'show me similar profiles'
    ]
  },
  {
    name: 'keyword_fallback',
    utterances: [
      'asdfasdf',
      'xyz123',
      'test query',
      '!!!',
      '...',
      'aaa bbb ccc',
      'random text here',
      '12345'
    ]
  }
];

interface IntentRouterDeps {
  generateEmbedding: (text: string) => Promise<number[]>;
  logger: Logger;
}

export class IntentRouter {
  private routeEmbeddings: Map<IntentType, number[]> = new Map();
  private initialized = false;
  private initPromise: Promise<void> | null = null;
  private readonly logger: Logger;
  private readonly generateEmbedding: (text: string) => Promise<number[]>;
  private readonly confidenceThreshold: number;

  constructor(deps: IntentRouterDeps, confidenceThreshold = 0.6) {
    this.logger = deps.logger.child({ module: 'intent-router' });
    this.generateEmbedding = deps.generateEmbedding;
    this.confidenceThreshold = confidenceThreshold;
  }

  /**
   * Initialize route embeddings lazily on first use.
   * Computes average embedding for each route's utterances.
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
    this.logger.info('Initializing intent router embeddings...');
    const start = Date.now();

    for (const route of INTENT_ROUTES) {
      try {
        // Generate embeddings for all utterances in parallel
        const utteranceEmbeddings = await Promise.all(
          route.utterances.map(utterance => this.generateEmbedding(utterance))
        );

        // Compute average embedding for route
        const routeEmbedding = averageEmbeddings(utteranceEmbeddings);
        this.routeEmbeddings.set(route.name, routeEmbedding);

        this.logger.debug(
          { route: route.name, utteranceCount: route.utterances.length },
          'Route embedding computed'
        );
      } catch (error) {
        this.logger.error(
          { error, route: route.name },
          'Failed to compute route embedding'
        );
        throw error;
      }
    }

    this.initialized = true;
    this.logger.info(
      { durationMs: Date.now() - start, routeCount: this.routeEmbeddings.size },
      'Intent router initialization complete'
    );
  }

  /**
   * Classify a query's intent using cosine similarity.
   *
   * @param queryEmbedding - Pre-computed embedding for the query
   * @returns Intent classification with confidence score
   */
  classifyIntent(queryEmbedding: number[]): IntentClassification {
    if (!this.initialized) {
      throw new Error('IntentRouter not initialized. Call initialize() first.');
    }

    const start = Date.now();
    let bestIntent: IntentType = 'keyword_fallback';
    let bestSimilarity = -1;

    for (const [intentName, routeEmbedding] of this.routeEmbeddings) {
      const similarity = cosineSimilarity(queryEmbedding, routeEmbedding);

      this.logger.trace(
        { intent: intentName, similarity: similarity.toFixed(4) },
        'Intent similarity score'
      );

      if (similarity > bestSimilarity) {
        bestSimilarity = similarity;
        bestIntent = intentName;
      }
    }

    // Apply confidence threshold
    if (bestSimilarity < this.confidenceThreshold) {
      this.logger.debug(
        {
          bestIntent,
          bestSimilarity: bestSimilarity.toFixed(4),
          threshold: this.confidenceThreshold
        },
        'Below confidence threshold, falling back to keyword search'
      );
      bestIntent = 'keyword_fallback';
    }

    const timingMs = Date.now() - start;

    return {
      intent: bestIntent,
      confidence: Math.max(0, Math.min(1, bestSimilarity)),
      timingMs
    };
  }

  /**
   * Check if router is initialized.
   */
  isInitialized(): boolean {
    return this.initialized;
  }

  /**
   * Get route embedding for testing/debugging.
   */
  getRouteEmbedding(intent: IntentType): number[] | undefined {
    return this.routeEmbeddings.get(intent);
  }
}

/**
 * Convenience function for stateless intent classification.
 * Requires pre-initialized router instance.
 */
export function classifyIntent(
  router: IntentRouter,
  queryEmbedding: number[]
): IntentClassification {
  return router.classifyIntent(queryEmbedding);
}
