# Phase 12: Natural Language Search - Research

**Researched:** 2026-01-25
**Domain:** Natural Language Processing, Intent Classification, Entity Extraction
**Confidence:** MEDIUM-HIGH

## Summary

Phase 12 adds natural language search to Headhunter, enabling recruiters to type queries like "senior python developer in NYC" instead of using structured filters. Research identified three key components: (1) intent classification using embedding-based semantic routing, (2) entity extraction for recruiting-domain entities, and (3) query expansion using the existing skills ontology.

The ROADMAP specifies Semantic Router for intent classification (5-100ms vector similarity) and Together AI JSON mode for entity extraction. Research validates this approach but identifies a critical gap: **Semantic Router is Python-only** with no official TypeScript/JavaScript support. For a Node.js/TypeScript codebase, this requires either a Python sidecar service, an LLM-based approach, or a custom embedding-based router.

**Primary recommendation:** Build a lightweight TypeScript "semantic router lite" using the existing Gemini embedding service for intent classification, combined with Together AI JSON mode for entity extraction. This keeps NLP within the 50ms latency budget allocated for query processing while avoiding Python service complexity.

## Standard Stack

The established libraries/tools for this domain:

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Together AI JSON Mode | API | Entity extraction from natural language | Already integrated in hh-rerank-svc, supports Llama 3.3 and DeepSeek |
| Gemini Embeddings | API | Intent vector generation for routing | Already used for candidate embeddings (gemini-embedding-001) |
| winkNLP | ^2.3.0 | Lightweight tokenization and NER | Native TypeScript, 650K tokens/sec, no Python dependency |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| NLP.js | ^4.27.0 | Pre-built intent classification | When predefined intents with training utterances needed |
| node-nlp-typescript | ^0.2.0 | TypeScript-first NLP.js fork | Alternative to NLP.js with better TS types |
| @xenova/transformers | ^2.17.0 | Browser/Node sentence transformers | When local embeddings preferred over API |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom semantic router | Python Semantic Router via sidecar | Higher latency (network hop), deployment complexity |
| Together AI extraction | Gemini JSON mode | Both work, but Together already integrated |
| winkNLP tokenization | spaCy via Python sidecar | spaCy has better Portuguese support but adds latency |
| LLM entity extraction | Rule-based regex | Regex is faster but misses semantic variations |

**Installation:**
```bash
npm install wink-nlp wink-eng-lite-web-model
```

## Architecture Patterns

### Recommended Project Structure
```
services/hh-search-svc/src/
├── nlp/                      # Natural language processing module
│   ├── intent-router.ts      # Embedding-based intent classification
│   ├── entity-extractor.ts   # Together AI JSON mode extraction
│   ├── query-expander.ts     # Skills ontology integration
│   ├── query-parser.ts       # Orchestrator combining all components
│   └── types.ts              # NLP-specific types
├── nlp/__tests__/
│   ├── intent-router.spec.ts
│   ├── entity-extractor.spec.ts
│   └── query-parser.spec.ts
```

### Pattern 1: Embedding-Based Intent Router

**What:** Use cosine similarity between query embeddings and pre-computed route embeddings to classify intent without LLM calls.

**When to use:** For fast (5-20ms) intent classification with known intent categories.

**Example:**
```typescript
// Source: Based on Semantic Router pattern from aurelio-labs/semantic-router
interface Route {
  name: string;
  utterances: string[];
  embedding?: number[]; // Pre-computed average embedding
}

const ROUTES: Route[] = [
  {
    name: 'structured_search',
    utterances: [
      'senior python developer in NYC',
      'ML engineers with 5 years experience',
      'remote frontend developers'
    ]
  },
  {
    name: 'similarity_search',
    utterances: [
      'candidates like John Smith',
      'similar profiles to candidate-123',
      'more like this candidate'
    ]
  },
  {
    name: 'keyword_fallback',
    utterances: [
      'asdfasdf',
      'xyz123',
      'test query'
    ]
  }
];

async function classifyIntent(
  query: string,
  queryEmbedding: number[],
  routeEmbeddings: Map<string, number[]>
): Promise<{ route: string; confidence: number }> {
  let bestRoute = 'keyword_fallback';
  let bestSimilarity = 0;

  for (const [routeName, routeEmbedding] of routeEmbeddings) {
    const similarity = cosineSimilarity(queryEmbedding, routeEmbedding);
    if (similarity > bestSimilarity) {
      bestSimilarity = similarity;
      bestRoute = routeName;
    }
  }

  // Confidence threshold - below 0.6, fall back to keyword search
  if (bestSimilarity < 0.6) {
    return { route: 'keyword_fallback', confidence: bestSimilarity };
  }

  return { route: bestRoute, confidence: bestSimilarity };
}
```

### Pattern 2: LLM JSON Mode Entity Extraction

**What:** Use Together AI's structured output mode to extract entities with a defined schema.

**When to use:** For complex entity extraction requiring semantic understanding (role, skills, location, experience).

**Example:**
```typescript
// Source: https://docs.together.ai/docs/json-mode
import Together from 'together-ai';

const ENTITY_SCHEMA = {
  type: 'object',
  properties: {
    role: {
      type: 'string',
      description: 'Job role/title mentioned (developer, engineer, manager, etc.)'
    },
    skills: {
      type: 'array',
      items: { type: 'string' },
      description: 'Technical or soft skills mentioned'
    },
    seniority: {
      type: 'string',
      enum: ['junior', 'mid', 'senior', 'staff', 'principal', 'lead', 'manager', 'director', 'vp', 'c-level'],
      description: 'Seniority level mentioned'
    },
    location: {
      type: 'string',
      description: 'City, state, region, or country mentioned'
    },
    remote: {
      type: 'boolean',
      description: 'Whether remote work is mentioned'
    },
    experience_years: {
      type: 'object',
      properties: {
        min: { type: 'number' },
        max: { type: 'number' }
      },
      description: 'Years of experience if mentioned (e.g., "5+ years" -> min: 5)'
    }
  },
  required: ['role']
};

async function extractEntities(query: string): Promise<ParsedQuery> {
  const client = new Together();

  const response = await client.chat.completions.create({
    model: 'meta-llama/Llama-3.3-70B-Instruct-Turbo',
    messages: [
      {
        role: 'system',
        content: `You are a recruiting query parser. Extract structured entities from job search queries.
Only respond in JSON format matching the provided schema. If an entity is not mentioned, omit it.`
      },
      {
        role: 'user',
        content: `Extract entities from: "${query}"`
      }
    ],
    response_format: {
      type: 'json_schema',
      json_schema: {
        name: 'query_entities',
        schema: ENTITY_SCHEMA
      }
    }
  });

  return JSON.parse(response.choices[0].message.content);
}
```

### Pattern 3: Ontology-Based Query Expansion

**What:** Use the existing skills graph to expand queries with related skills.

**When to use:** When user mentions a skill that has known related skills in the ontology.

**Example:**
```typescript
// Source: Existing skills-graph.ts in functions/src/shared/
import { getCachedSkillExpansion } from '../../../functions/src/shared/skills-graph';

function expandQuerySkills(extractedSkills: string[]): string[] {
  const expandedSkills = new Set(extractedSkills);

  for (const skill of extractedSkills) {
    const expansion = getCachedSkillExpansion(skill, 1); // depth=1 for direct relations
    for (const related of expansion.relatedSkills) {
      // Only include high-confidence related skills
      if (related.confidence >= 0.8 && related.relationshipType === 'direct') {
        expandedSkills.add(related.skillName);
      }
    }
  }

  return Array.from(expandedSkills);
}
```

### Anti-Patterns to Avoid

- **LLM-first intent classification:** Calling LLM for every query classification is slow (200-500ms). Use embedding similarity first, LLM only for entity extraction.
- **Synchronous NLP pipeline:** Running intent -> extraction -> expansion sequentially. Intent classification can be parallel with query embedding.
- **Hardcoded synonyms:** Maintaining manual synonym lists ("senior" -> "lead"). Use embedding similarity for semantic matching instead.
- **No confidence thresholds:** Accepting NLP results without confidence scoring leads to bad fallback behavior.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tokenization | Custom regex tokenizer | winkNLP tokenizer | Handles edge cases (contractions, hyphenation, URLs) |
| Cosine similarity | Manual dot product | Vector utility function | Numerical precision, SIMD optimization |
| Seniority synonyms | Manual mapping dict | Embedding similarity | "Senior", "Sr.", "Lead", "Principal" - too many variations |
| Location normalization | Manual city/state mapping | LLM extraction | "NYC", "New York City", "New York, NY" - endless variations |
| Skill synonyms | Manual skill alias map | Existing MASTER_SKILLS aliases | Already has 200+ skills with aliases |

**Key insight:** Recruiting domain has high lexical variation. "Python developer", "Python dev", "Python engineer", "Pythonista" all mean the same thing. Embedding-based matching handles this naturally; rule-based matching requires endless maintenance.

## Common Pitfalls

### Pitfall 1: Latency Budget Violation

**What goes wrong:** NLP parsing adds 200-400ms, breaking the 500ms total search budget.
**Why it happens:** Entity extraction via LLM call plus embedding generation plus routing logic.
**How to avoid:**
- Cache intent route embeddings at startup (compute once)
- Reuse the query embedding (already computed for vector search)
- Set strict timeout on LLM extraction (50ms, fail fast to fallback)
**Warning signs:** Server-Timing header shows `nlp-parse` exceeding 100ms.

### Pitfall 2: Language Detection Failure

**What goes wrong:** Portuguese queries get parsed as English, extracting wrong entities.
**Why it happens:** LLM defaults to English, doesn't detect "desenvolvedor Python em São Paulo".
**How to avoid:**
- Add explicit language detection step using character analysis
- Include Portuguese examples in LLM prompt
- Support mixed language queries ("Python developer em São Paulo")
**Warning signs:** Brazilian users report location extraction failures.

### Pitfall 3: Overly Aggressive Query Expansion

**What goes wrong:** Search for "Python" returns candidates with only "Django" (no explicit Python mention).
**Why it happens:** Ontology expansion includes all related skills without confidence weighting.
**How to avoid:**
- Only expand with high-confidence direct relations (confidence >= 0.8)
- Limit expansion depth to 1 hop
- Weight expanded skills lower than explicit skills in scoring
**Warning signs:** Users complain "I searched for X but got Y candidates".

### Pitfall 4: Silent Fallback Without Feedback

**What goes wrong:** User types query, gets results, but doesn't know NLP failed and fell back to keyword search.
**Why it happens:** Graceful fallback hides NLP failures from user.
**How to avoid:**
- Return `parseConfidence` in response metadata
- Show UI indicator when using fallback mode
- Log all fallback events for analysis
**Warning signs:** High fallback rate in logs, users re-typing queries with more specific terms.

### Pitfall 5: Entity Extraction Hallucination

**What goes wrong:** LLM extracts entities that weren't in the query ("Senior Python developer" -> extracts "AWS" skill).
**Why it happens:** LLM training data associates Python developers with AWS.
**How to avoid:**
- Add constraint in prompt: "Only extract entities explicitly mentioned in query"
- Validate extracted skills against query text (fuzzy match)
- Log extraction/input pairs for hallucination detection
**Warning signs:** Users report search results don't match their query.

## Code Examples

Verified patterns from official sources:

### Cosine Similarity Utility
```typescript
// Source: Standard vector math implementation
export function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length !== b.length) {
    throw new Error('Vectors must have same length');
  }

  let dotProduct = 0;
  let normA = 0;
  let normB = 0;

  for (let i = 0; i < a.length; i++) {
    dotProduct += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }

  const denominator = Math.sqrt(normA) * Math.sqrt(normB);
  if (denominator === 0) return 0;

  return dotProduct / denominator;
}
```

### Query Parser Orchestrator
```typescript
// Source: Pattern from search-service.ts existing architecture
export interface ParsedQuery {
  originalQuery: string;
  parseMethod: 'nlp' | 'keyword_fallback';
  confidence: number;
  entities: {
    role?: string;
    skills: string[];
    expandedSkills: string[];
    seniority?: string;
    location?: string;
    remote?: boolean;
    experienceYears?: { min?: number; max?: number };
  };
  timings: {
    intentMs: number;
    extractionMs: number;
    expansionMs: number;
    totalMs: number;
  };
}

export async function parseNaturalLanguageQuery(
  query: string,
  embedClient: EmbedClient,
  context: SearchContext
): Promise<ParsedQuery> {
  const start = Date.now();
  const timings = { intentMs: 0, extractionMs: 0, expansionMs: 0, totalMs: 0 };

  // Step 1: Generate query embedding (reuse for search)
  const intentStart = Date.now();
  const embedding = await embedClient.generateEmbedding({
    tenantId: context.tenant.id,
    requestId: context.requestId,
    query
  });

  // Step 2: Classify intent using cached route embeddings
  const intent = classifyIntent(query, embedding.embedding, ROUTE_EMBEDDINGS);
  timings.intentMs = Date.now() - intentStart;

  // Step 3: If low confidence, fall back to keyword search
  if (intent.confidence < 0.6 || intent.route === 'keyword_fallback') {
    timings.totalMs = Date.now() - start;
    return {
      originalQuery: query,
      parseMethod: 'keyword_fallback',
      confidence: intent.confidence,
      entities: { skills: [], expandedSkills: [] },
      timings
    };
  }

  // Step 4: Extract entities via LLM
  const extractStart = Date.now();
  const entities = await extractEntities(query);
  timings.extractionMs = Date.now() - extractStart;

  // Step 5: Expand skills using ontology
  const expansionStart = Date.now();
  const expandedSkills = expandQuerySkills(entities.skills || []);
  timings.expansionMs = Date.now() - expansionStart;

  timings.totalMs = Date.now() - start;

  return {
    originalQuery: query,
    parseMethod: 'nlp',
    confidence: intent.confidence,
    entities: {
      ...entities,
      skills: entities.skills || [],
      expandedSkills
    },
    timings
  };
}
```

### Portuguese-English Mixed Query Support
```typescript
// Source: Research on multilingual NER patterns
const PORTUGUESE_LOCATION_INDICATORS = [
  'em', 'de', 'no', 'na', 'para', // Portuguese prepositions
  'são paulo', 'rio de janeiro', 'belo horizonte', 'curitiba',
  'porto alegre', 'brasília', 'recife', 'salvador', 'fortaleza'
];

const PORTUGUESE_SENIORITY_TERMS: Record<string, string> = {
  'sênior': 'senior',
  'pleno': 'mid',
  'junior': 'junior',
  'júnior': 'junior',
  'estagiário': 'intern',
  'gerente': 'manager',
  'diretor': 'director'
};

function normalizePortugueseTerms(query: string): string {
  let normalized = query.toLowerCase();

  // Replace Portuguese seniority terms with English equivalents
  for (const [pt, en] of Object.entries(PORTUGUESE_SENIORITY_TERMS)) {
    normalized = normalized.replace(new RegExp(`\\b${pt}\\b`, 'gi'), en);
  }

  return normalized;
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Regex-based parsing | LLM structured output | 2024 | Much higher accuracy, handles variations |
| Rule-based synonyms | Embedding similarity | 2023 | No maintenance of synonym lists |
| Python NLP libraries | TypeScript/JS or API | 2024-2025 | Reduced deployment complexity |
| Fixed entity types | Schema-driven extraction | 2025 | Flexible, domain-specific entities |

**Deprecated/outdated:**
- **Semantic Router Python-only:** The primary library has no TypeScript port. For Node.js, must either run Python sidecar or implement pattern directly.
- **BERT-based NER:** Transformer models now preferred over BERT for NER due to context length and speed.
- **Static synonym dictionaries:** Embedding-based similarity has replaced manual synonym management for most use cases.

## Latency Impact Analysis

**500ms Total Budget (Phase 11):**

| Stage | Budget | NLP Addition | New Total | Notes |
|-------|--------|--------------|-----------|-------|
| Query embedding | 50ms | 0ms | 50ms | Already needed for search |
| **Intent classification** | - | +5ms | 5ms | Cosine similarity is O(1) |
| **Entity extraction (LLM)** | - | +80-150ms | 130ms | Main latency cost |
| **Skill expansion** | - | +2ms | 2ms | In-memory graph lookup |
| Vector search | 100ms | 0ms | 100ms | Unchanged |
| Text search | 50ms | 0ms | 50ms | Unchanged |
| Scoring/filtering | 100ms | 0ms | 100ms | Unchanged |
| Reranking | 200ms | 0ms | 200ms | Unchanged |
| **TOTAL** | 500ms | +87-157ms | **587-657ms** | Exceeds budget |

**Mitigation Strategies:**
1. **Cache LLM extraction results** by query hash (repeated queries skip extraction) - saves 80-150ms
2. **Run intent classification parallel** with embedding generation - no additional latency
3. **Set extraction timeout at 100ms** with fallback to simple parsing
4. **Reduce rerank budget** from 200ms to 150ms for NLP headroom
5. **Skip extraction for keyword-only queries** (detected by intent router)

**Revised Budget with NLP:**
- Query preprocessing (embed + intent): 50ms
- Entity extraction (LLM, cached): 0-100ms
- Vector search: 100ms
- Text search: 50ms
- Scoring/filtering: 100ms
- Reranking: 150ms
- **Total: 450-550ms** (acceptable)

## Open Questions

Things that couldn't be fully resolved:

1. **Portuguese-English Language Detection**
   - What we know: Multilingual models exist (XLM-RoBERTa, mBERT), Together AI supports multilingual
   - What's unclear: Performance of Together AI Llama models on Portuguese entity extraction
   - Recommendation: Test with Brazilian recruiter queries, may need Portuguese-specific prompt

2. **Semantic Router TypeScript Port**
   - What we know: @malipetek/semantic-router exists on npm but is unmaintained (0.0.5, 2 years old)
   - What's unclear: Whether to use community port, build custom, or accept Python sidecar
   - Recommendation: Build custom "semantic router lite" - it's just cosine similarity with route embeddings

3. **Confidence Threshold Calibration**
   - What we know: 0.6 is commonly used as minimum confidence threshold
   - What's unclear: Optimal threshold for recruiting domain queries
   - Recommendation: Start with 0.6, log all classifications, tune based on fallback rate data

4. **Entity Extraction Model Selection**
   - What we know: Llama 3.3-70B and DeepSeek V3 both support JSON mode
   - What's unclear: Which model performs better on short query extraction
   - Recommendation: A/B test both in shadow mode, measure extraction accuracy

## Sources

### Primary (HIGH confidence)
- [Together AI JSON Mode Documentation](https://docs.together.ai/docs/json-mode) - Structured output API patterns
- [Existing skills-graph.ts](/Volumes/Extreme Pro/myprojects/headhunter/functions/src/shared/skills-graph.ts) - Skill expansion implementation
- [Existing search-service.ts](/Volumes/Extreme Pro/myprojects/headhunter/services/hh-search-svc/src/search-service.ts) - Current search pipeline architecture

### Secondary (MEDIUM confidence)
- [Semantic Router GitHub](https://github.com/aurelio-labs/semantic-router) - Pattern for embedding-based intent classification
- [winkNLP Documentation](https://winkjs.org/wink-nlp/) - TypeScript NLP library
- [ZipRecruiter NER Article](https://medium.com/@ziprecruiter.engineering/named-entity-recognition-ner-of-short-unstructured-job-search-queries-6b265ec0fb) - Domain-specific NER for recruiting

### Tertiary (LOW confidence - needs validation)
- [@malipetek/semantic-router npm](https://www.npmjs.com/package/@malipetek/semantic-router) - Unmaintained TypeScript port
- Various multilingual NER models on HuggingFace - Portuguese support claims need testing

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM-HIGH - Together AI integration verified, TypeScript options available
- Architecture: HIGH - Patterns well-established, existing infrastructure supports them
- Pitfalls: MEDIUM - Portuguese support needs validation, latency impact requires tuning
- Latency budget: MEDIUM - Exceeds baseline, mitigation strategies documented but untested

**Research date:** 2026-01-25
**Valid until:** 30 days (stable domain, but LLM API capabilities evolving rapidly)
