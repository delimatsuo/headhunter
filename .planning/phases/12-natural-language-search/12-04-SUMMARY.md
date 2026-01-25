---
phase: 12
plan: 04
subsystem: nlp
tags: [query-parser, nlp-pipeline, orchestration, caching]
requires: [12-01, 12-02, 12-03]
provides: [query-parser, nlp-barrel-export, nlp-config]
affects: [12-05]
tech-stack:
  added: []
  patterns: [orchestration, in-memory-caching, graceful-fallback, timing-tracking]
key-files:
  created:
    - services/hh-search-svc/src/nlp/query-parser.ts
    - services/hh-search-svc/src/nlp/index.ts
    - services/hh-search-svc/src/nlp/__tests__/query-parser.spec.ts
  modified:
    - services/hh-search-svc/src/config.ts
decisions:
  - id: DEC-12-04-01
    title: In-memory cache for extraction results
    rationale: LLM extraction is expensive (~100ms); cache avoids repeated calls for same query
  - id: DEC-12-04-02
    title: SHA256-based cache keys with lowercase normalization
    rationale: Case-insensitive matching for cache hits
  - id: DEC-12-04-03
    title: Graceful fallback to keyword_fallback on failures
    rationale: System should degrade gracefully, not fail completely
metrics:
  duration: ~5 minutes
  completed: 2026-01-25
---

# Phase 12 Plan 04: Query Parser Orchestrator Summary

NLP pipeline orchestrator that coordinates IntentRouter, EntityExtractor, and QueryExpander into a unified query parsing system.

## One-Liner

QueryParser orchestrates 3 NLP components (intent, entity, expansion) with 5-min extraction cache and graceful fallback.

## What Was Built

### 1. QueryParser Class (Task 1)

**File**: `services/hh-search-svc/src/nlp/query-parser.ts`

**Responsibilities**:
- Coordinates IntentRouter, EntityExtractor, QueryExpander
- Manages initialization lifecycle
- Caches extraction results (5-min TTL, 500 max entries)
- Tracks timing for each pipeline stage
- Provides graceful fallback for errors and low-confidence queries

**Pipeline Flow**:
```
Query -> Generate Embedding -> Classify Intent -> Extract Entities -> Expand Skills -> ParsedQuery
                                     |                    |                |
                                     v                    v                v
                              (IntentRouter)       (EntityExtractor)  (QueryExpander)
                                     |                    |                |
                                     v                    v                v
                              timing: ~5ms          timing: ~100ms    timing: ~1ms
```

**Key Methods**:
```typescript
class QueryParser {
  async initialize(): Promise<void>;     // Precompute intent route embeddings
  async parse(query: string, embedding?: number[]): Promise<ParsedQuery>;
  isInitialized(): boolean;
  getConfig(): NLPConfig;
  static clearCache(): void;
}
```

**Configuration**:
```typescript
interface NLPConfig {
  enabled: boolean;                    // Default: true
  intentConfidenceThreshold: number;   // Default: 0.6
  extractionTimeoutMs: number;         // Default: 100ms
  cacheExtractionResults: boolean;     // Default: true
  enableQueryExpansion: boolean;       // Default: true
  expansionDepth: number;              // Default: 1
  expansionConfidenceThreshold: number; // Default: 0.8
}
```

### 2. NLP Module Barrel Export (Task 2)

**File**: `services/hh-search-svc/src/nlp/index.ts`

**Exports**:
- Types: `IntentType`, `ParsedQuery`, `ExtractedEntities`, `NLPConfig`, etc.
- Classes: `IntentRouter`, `EntityExtractor`, `QueryExpander`, `QueryParser`
- Functions: `classifyIntent`, `extractEntities`, `expandQuerySkills`, `parseNaturalLanguageQuery`
- Utilities: `cosineSimilarity`, `averageEmbeddings`

**Usage**:
```typescript
import { QueryParser, type ParsedQuery } from './nlp';
```

### 3. NLP Configuration & Tests (Task 3)

**Config additions to** `config.ts`:
```typescript
interface NLPSearchConfig {
  enabled: boolean;
  intentConfidenceThreshold: number;
  extractionTimeoutMs: number;
  cacheExtractionResults: boolean;
  enableQueryExpansion: boolean;
  expansionDepth: number;
  expansionConfidenceThreshold: number;
}
```

**Environment Variables**:
| Variable | Default | Description |
|----------|---------|-------------|
| `NLP_SEARCH_ENABLED` | `true` | Enable/disable NLP parsing |
| `NLP_INTENT_CONFIDENCE_THRESHOLD` | `0.6` | Min confidence for structured search |
| `NLP_EXTRACTION_TIMEOUT_MS` | `100` | LLM extraction timeout |
| `NLP_CACHE_EXTRACTION` | `true` | Enable extraction caching |
| `NLP_QUERY_EXPANSION_ENABLED` | `true` | Enable skill expansion |
| `NLP_EXPANSION_DEPTH` | `1` | Graph traversal depth |
| `NLP_EXPANSION_CONFIDENCE_THRESHOLD` | `0.8` | Min confidence for expanded skills |

**Test Coverage**: 25 test cases covering:
- Initialization (idempotent, concurrent)
- Parsing (all fields, timings, fallback)
- Caching (cache hits, case normalization, clearing)
- Configuration (defaults, partial overrides)
- Pipeline integration (component orchestration)

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| In-memory cache with 5-min TTL | LLM calls are expensive (~100ms); cache avoids repeats for common queries |
| SHA256 hash for cache keys | Fast, deterministic, case-insensitive after lowercase normalization |
| Cache max 500 entries | Balance memory usage vs hit rate; LRU eviction on overflow |
| Fallback on low confidence | Intent classification <0.6 should use keyword search |
| Similarity_search triggers fallback | Not yet implemented; degrade gracefully to keyword |
| Pre-computed embedding support | Save ~50ms when embedding already generated for vector search |

## Key Integration Points

### Input
```typescript
const parser = new QueryParser({
  generateEmbedding,  // Function to generate embeddings
  logger,             // Pino logger
  togetherApiKey,     // For EntityExtractor LLM calls
  config              // Optional NLPConfig overrides
});
```

### Output
```typescript
interface ParsedQuery {
  originalQuery: string;
  parseMethod: 'nlp' | 'keyword_fallback';
  confidence: number;
  intent: IntentType;
  entities: ExtractedEntities & {
    expandedSkills: string[];
  };
  timings: {
    intentMs: number;
    extractionMs: number;
    expansionMs: number;
    totalMs: number;
  };
}
```

### Usage in Search Pipeline
```typescript
// 1. Initialize once at service startup
const queryParser = new QueryParser({
  generateEmbedding: async (text) => embedService.embed(text),
  logger,
  togetherApiKey: config.togetherApiKey,
  config: searchConfig.nlp
});
await queryParser.initialize();

// 2. Parse incoming search queries
const parsed = await queryParser.parse(query);

if (parsed.parseMethod === 'nlp') {
  // Use structured search with extracted entities
  const results = await structuredSearch({
    role: parsed.entities.role,
    skills: [...parsed.entities.skills, ...parsed.entities.expandedSkills],
    seniority: parsed.entities.seniority,
    location: parsed.entities.location
  });
} else {
  // Fallback to keyword search
  const results = await keywordSearch(query);
}
```

## Commits

| Hash | Description |
|------|-------------|
| 1f5ba8d | feat(12-04): implement QueryParser NLP pipeline orchestrator |
| f6eaaea | feat(12-04): add NLP module barrel export |
| be87951 | feat(12-04): add NLP configuration and QueryParser tests |

## Verification Results

| Check | Status |
|-------|--------|
| TypeScript compiles | Pass |
| QueryParser tests pass (25/25) | Pass |
| All NLP tests pass (100/100) | Pass |
| Barrel export works | Pass |
| Config parsing works | Pass |
| Cache behavior verified | Pass |

## Deviations from Plan

None - plan executed exactly as written.

## Performance

- **Intent classification**: ~5ms (embedding similarity)
- **Entity extraction**: ~100ms (LLM call, cached after first call)
- **Skill expansion**: <1ms (in-memory graph)
- **Total pipeline**: ~106ms first call, <10ms cached
- **Cache hit rate**: Expected high for repeated queries

## Test Summary

Phase 12 NLP module now has 100 passing tests:
- Intent Router: 19 tests
- Entity Extractor: 33 tests
- Query Expander: 23 tests
- Query Parser: 25 tests

## Next Phase Readiness

Plan 12-05 (Verification & Tuning) can now:
- Use `QueryParser` as the single entry point for NLP
- Access all NLP components via barrel export
- Configure via environment variables
- Test with different confidence thresholds
- Measure end-to-end latency
