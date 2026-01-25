/**
 * NLP Module - Natural Language Search Pipeline
 *
 * This module provides natural language processing capabilities for search queries.
 * It includes intent classification, entity extraction, and query expansion.
 *
 * Main Entry Points:
 * - QueryParser: Orchestrates the full NLP pipeline
 * - IntentRouter: Classifies query intent using semantic similarity
 * - EntityExtractor: Extracts structured entities from queries
 * - QueryExpander: Expands skills using ontology
 *
 * Quick Start:
 * ```typescript
 * import { QueryParser, type ParsedQuery } from './nlp';
 *
 * const parser = new QueryParser({
 *   generateEmbedding,
 *   logger,
 *   togetherApiKey: process.env.TOGETHER_API_KEY
 * });
 *
 * await parser.initialize();
 * const result: ParsedQuery = await parser.parse('senior python developer in NYC');
 * ```
 *
 * @module nlp
 * @see Phase 12: Natural Language Search
 */

// ============================================================================
// TYPES
// ============================================================================

export type {
  IntentType,
  IntentRoute,
  IntentClassification,
  ExtractedEntities,
  ParsedQuery,
  NLPConfig
} from './types';

// ============================================================================
// INTENT ROUTER
// ============================================================================

export {
  IntentRouter,
  classifyIntent
} from './intent-router';

// ============================================================================
// ENTITY EXTRACTOR
// ============================================================================

export {
  EntityExtractor,
  createEntityExtractor,
  extractEntities,
  type EntityExtractorConfig,
  type EntityExtractionResult
} from './entity-extractor';

// ============================================================================
// QUERY EXPANDER
// ============================================================================

export {
  QueryExpander,
  expandQuerySkills,
  type ExpandedSkill,
  type QueryExpansionResult,
  type QueryExpanderConfig
} from './query-expander';

// ============================================================================
// QUERY PARSER (MAIN ORCHESTRATOR)
// ============================================================================

export {
  QueryParser,
  parseNaturalLanguageQuery,
  type QueryParserDeps
} from './query-parser';

// ============================================================================
// VECTOR UTILITIES
// ============================================================================

export {
  cosineSimilarity,
  averageEmbeddings
} from './vector-utils';

// ============================================================================
// SEMANTIC SYNONYMS
// ============================================================================

export {
  expandSenioritySynonyms,
  expandRoleSynonyms,
  expandSemanticSynonyms,
  matchesSeniorityLevel,
  getSeniorityIndex,
  compareSeniorityLevels,
  SENIORITY_SYNONYMS,
  ROLE_SYNONYMS,
  SENIORITY_HIERARCHY,
  type SemanticExpansionResult
} from './semantic-synonyms';
