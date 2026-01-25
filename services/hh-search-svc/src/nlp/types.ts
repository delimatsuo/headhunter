/**
 * NLP types for Phase 12: Natural Language Search
 * @see NLNG-01: Semantic router lite for intent classification
 */

export type IntentType = 'structured_search' | 'similarity_search' | 'keyword_fallback';

export interface IntentRoute {
  name: IntentType;
  utterances: string[];
  embedding?: number[];  // Pre-computed average embedding
}

export interface IntentClassification {
  intent: IntentType;
  confidence: number;  // 0-1 cosine similarity
  timingMs: number;
}

export interface ExtractedEntities {
  role?: string;
  skills: string[];
  seniority?: 'junior' | 'mid' | 'senior' | 'staff' | 'principal' | 'lead' | 'manager' | 'director' | 'vp' | 'c-level';
  location?: string;
  remote?: boolean;
  experienceYears?: { min?: number; max?: number };
}

export interface ParsedQuery {
  originalQuery: string;
  parseMethod: 'nlp' | 'keyword_fallback';
  confidence: number;
  intent: IntentType;
  entities: ExtractedEntities & {
    expandedSkills: string[];  // After ontology expansion
  };
  /** Semantic expansions for role and seniority titles */
  semanticExpansion?: {
    expandedRoles: string[];
    expandedSeniorities: string[];
  };
  timings: {
    intentMs: number;
    extractionMs: number;
    expansionMs: number;
    totalMs: number;
  };
}

export interface NLPConfig {
  enabled: boolean;
  intentConfidenceThreshold: number;  // Below this, fall back to keyword
  extractionTimeoutMs: number;  // Max time for LLM extraction
  cacheExtractionResults: boolean;
  enableQueryExpansion: boolean;
  expansionDepth: number;  // Graph hops for skill expansion
  expansionConfidenceThreshold: number;  // Min confidence for expanded skills
}
