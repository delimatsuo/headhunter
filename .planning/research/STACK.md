# Technology Stack: Leader-Level Search Capabilities

**Project:** Headhunter AI - Leader Search Milestone
**Researched:** 2026-01-24
**Existing Stack:** PostgreSQL + pgvector, Redis, Together AI, Gemini embeddings, 8 Fastify microservices

---

## Executive Summary

The existing Headhunter stack is well-positioned for leader-level search enhancements. The core infrastructure (pgvector, Redis, Together AI, Fastify) is current and production-proven. This research identifies **additions** to enable multi-signal scoring, career trajectory prediction, skills inference, and hybrid search improvements.

**Key Findings:**
- Hybrid search with RRF fusion is implementable in pure PostgreSQL + pgvector (no new database needed)
- LLM-based reranking is already in place; enhancement via structured prompts is the path forward
- Skills inference requires enrichment-time extraction, not runtime inference
- Career trajectory is a feature engineering problem, not a separate ML model
- Multi-signal scoring can be achieved through weighted combination in SQL/TypeScript

---

## Recommended Additions to Existing Stack

### 1. Enhanced Embedding Model (MEDIUM Confidence)

**Current:** Gemini `gemini-embedding-001` (768 dimensions)
**Recommendation:** Keep Gemini as primary, add dimension flexibility

| Setting | Current | Recommended | Rationale |
|---------|---------|-------------|-----------|
| Provider | Gemini | Gemini (keep) | #1 on MTEB, 68% quality, 100+ languages |
| Dimensions | 768 | 768 (keep) | pgvector index already configured |
| Fallback | Vertex AI | OpenAI text-embedding-3-large | Better tooling ecosystem for debugging |

**Sources:**
- [Embedding Models Comparison 2026](https://research.aimultiple.com/embedding-models/)
- [VentureBeat: Google Takes #1](https://venturebeat.com/ai/new-embedding-model-leaderboard-shakeup-google-takes-1-while-alibabas-open-source-alternative-closes-gap/)

**Why NOT change:**
Gemini leads MTEB benchmarks by ~6% over OpenAI. The existing 768-dimension vectors work well with pgvector HNSW indexes. Migration cost exceeds benefit.

---

### 2. Hybrid Search with RRF Fusion (HIGH Confidence)

**Current:** pgvector cosine similarity + PostgreSQL FTS (parallel queries)
**Recommendation:** Implement Reciprocal Rank Fusion (RRF) in SQL

```sql
-- RRF implementation pattern (already compatible with pgvector)
WITH vector_results AS (
  SELECT candidate_id, ROW_NUMBER() OVER (ORDER BY embedding <=> $1) as vrank
  FROM candidate_embeddings
  WHERE 1 - (embedding <=> $1) >= 0.45
  LIMIT 200
),
text_results AS (
  SELECT candidate_id, ROW_NUMBER() OVER (ORDER BY ts_rank DESC) as trank
  FROM candidate_profiles
  WHERE search_vector @@ plainto_tsquery($2)
  LIMIT 200
),
rrf_combined AS (
  SELECT
    COALESCE(v.candidate_id, t.candidate_id) as candidate_id,
    (1.0 / (60 + COALESCE(v.vrank, 1000))) * 0.65 +
    (1.0 / (60 + COALESCE(t.trank, 1000))) * 0.35 as rrf_score
  FROM vector_results v
  FULL OUTER JOIN text_results t ON v.candidate_id = t.candidate_id
)
SELECT * FROM rrf_combined ORDER BY rrf_score DESC LIMIT 50;
```

**Key Parameters:**
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| k constant | 60 | Industry standard, proven across datasets |
| Vector weight | 0.65 | Semantic understanding prioritized |
| Text weight | 0.35 | Keyword precision for exact matches |

**No new library needed.** This is pure SQL implementable with existing pg and pgvector packages.

**Sources:**
- [ParadeDB: Hybrid Search Missing Manual](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual)
- [ParadeDB: What is RRF](https://www.paradedb.com/learn/search-concepts/reciprocal-rank-fusion)
- [Jonathan Katz: Hybrid Search with pgvector](https://jkatz05.com/post/postgres/hybrid-search-postgres-pgvector/)

---

### 3. Multi-Signal Scoring (HIGH Confidence)

**Current:** Composite score combining vector_score, text_score, skill_match
**Recommendation:** Extend with structured signal weights and normalization

```typescript
// Multi-signal scoring structure
interface CandidateSignals {
  // Stage 1: Retrieval signals (from pgvector/FTS)
  vectorScore: number;      // 0-1, semantic similarity
  textScore: number;        // 0-1, BM25/FTS rank normalized

  // Stage 2: Profile signals (from enrichment)
  skillCoverage: number;    // 0-1, required skills matched / total required
  experienceMatch: number;  // 0-1, years in range
  seniorityMatch: number;   // 0-1, level alignment

  // Stage 3: Career trajectory signals (computed)
  promotionVelocity: number;    // 0-1, normalized promotion speed
  tenureStability: number;      // 0-1, average tenure normalized
  companyPedigree: number;      // 0-1, company tier scoring
  leadershipScope: number;      // 0-1, team size / org level

  // Stage 4: Confidence signals
  profileConfidence: number;    // 0-1, analysis_confidence from enrichment
  dataFreshness: number;        // 0-1, decay function on resume_updated_at
}

// Weighted combination (tunable per query type)
function computeCompositeScore(
  signals: CandidateSignals,
  weights: SignalWeights
): number {
  return Object.entries(weights).reduce((sum, [key, weight]) => {
    return sum + (signals[key as keyof CandidateSignals] ?? 0) * weight;
  }, 0);
}
```

**No new library needed.** This is feature engineering in TypeScript using existing data.

**Weight Profiles (recommended):**
| Query Type | Vector | Text | Skills | Experience | Trajectory |
|------------|--------|------|--------|------------|------------|
| Technical IC | 0.30 | 0.15 | 0.35 | 0.15 | 0.05 |
| Engineering Manager | 0.25 | 0.10 | 0.25 | 0.20 | 0.20 |
| Executive/C-Level | 0.20 | 0.05 | 0.15 | 0.25 | 0.35 |

---

### 4. Reranker Enhancement (HIGH Confidence)

**Current:** Together AI (Qwen 2.5 32B) + Gemini fallback for LLM reranking
**Recommendation:** Keep current stack, add structured prompt engineering

**Option A: Keep LLM Reranking (RECOMMENDED)**
The existing Together AI + Gemini setup is effective. Enhance with:

1. **Structured output schema** for consistent scoring
2. **Chain-of-thought prompts** for explainable rankings
3. **Query-type-aware prompts** (IC vs Manager vs Executive)

**Option B: Add API-based Reranker (ALTERNATIVE)**

| Reranker | Latency | Quality | Integration |
|----------|---------|---------|-------------|
| Cohere Rerank 3.5 | ~600ms | HIGH | API, npm: `cohere-ai` |
| Jina Reranker v2 | ~400ms | HIGH | API or self-host, npm: `jina-ai` |
| Voyage Rerank 2.5 | ~600ms | HIGH | API |

**If adding cross-encoder reranking:**

```bash
# API-based (recommended for production)
npm install cohere-ai@^7.0.0
# OR
npm install jina-ai@^1.0.0
```

**Sources:**
- [ZeroEntropy: Best Reranking Model 2025](https://www.zeroentropy.dev/articles/ultimate-guide-to-choosing-the-best-reranking-model-in-2025)
- [Agentset Reranker Leaderboard](https://agentset.ai/rerankers)
- [LlamaIndex: Picking Reranker Models](https://www.llamaindex.ai/blog/boosting-rag-picking-the-best-embedding-reranker-models-42d079022e83)

**Why not switch completely:** Existing LLM reranking provides explainability ("Why matched") that cross-encoder rerankers do not. Hybrid approach (cross-encoder for speed, LLM for top-N explanation) is optimal.

---

### 5. Skills Inference at Enrichment Time (HIGH Confidence)

**Current:** Together AI single-pass enrichment extracts explicit + inferred skills
**Recommendation:** Enhance enrichment prompts, add ESCO taxonomy mapping

**Skill Extraction Enhancement:**

```typescript
// Enhanced skill extraction schema
interface SkillExtraction {
  explicit: Array<{
    skill: string;
    confidence: 1.0;
    evidence: string;
    escoUri?: string;  // ESCO taxonomy mapping
  }>;
  inferred: Array<{
    skill: string;
    confidence: number;  // 0.5-0.99
    evidence: string;
    inferenceType: 'adjacent' | 'implied' | 'contextual';
    escoUri?: string;
  }>;
  techStack: Array<{
    technology: string;
    proficiency: 'learning' | 'working' | 'expert';
    recency: 'current' | 'recent' | 'historical';
  }>;
}
```

**ESCO Integration (Optional Enhancement):**
- Download ESCO v1.2.0 taxonomy (released May 2024)
- Load into PostgreSQL as reference table
- Map extracted skills to ESCO URIs during enrichment

**Sources:**
- [ESCO Download](https://esco.ec.europa.eu/en/use-esco/download)
- [Skill-LLM Research](https://arxiv.org/html/2410.12052v1)
- [AI Hiring Framework](https://arxiv.org/html/2504.02870v1)

**No new library needed for basic implementation.** ESCO is a data asset, not a library.

---

### 6. Career Trajectory Scoring (MEDIUM Confidence)

**Current:** Basic experience analysis in enrichment
**Recommendation:** Feature engineering during enrichment, no separate ML model

**Trajectory Signals to Compute:**

```typescript
interface CareerTrajectory {
  // Promotion velocity
  promotionVelocity: number;  // promotions / years_in_career
  averageTenure: number;      // months per role
  tenurePattern: 'job-hopper' | 'stable' | 'long-tenure';

  // Company progression
  companyTierProgression: 'ascending' | 'lateral' | 'descending';
  companyTiers: Array<{
    company: string;
    tier: 'startup' | 'scaleup' | 'enterprise' | 'faang' | 'unknown';
    duration: number;
  }>;

  // Leadership growth
  leadershipProgression: Array<{
    title: string;
    teamSize?: number;
    scope: 'ic' | 'lead' | 'manager' | 'director' | 'vp' | 'c-level';
    startDate: string;
  }>;

  // Pattern detection
  industryFocus: string[];     // consistent vs diverse
  functionProgression: string; // linear vs pivot
  geographyPattern: string;    // local vs global
}
```

**Implementation approach:**
1. Compute during Together AI enrichment (single pass)
2. Store in Firestore candidate profile
3. Use as scoring signals at search time

**No ML model needed.** Rule-based computation from timeline analysis is sufficient and more explainable.

---

### 7. Redis Enhancements (MEDIUM Confidence)

**Current:** ioredis for caching embedding results and rerank scores
**Recommendation:** Add Bloom filters for deduplication, keep current setup

**Already available in Redis Stack:**
- Bloom filters for seen-candidate deduplication
- Sorted sets for ranking caches
- JSON for structured cache entries

```typescript
// Bloom filter usage with ioredis (RedisBloom commands)
const redis = new Redis();

// Check if candidate was shown in session
async function wasShown(sessionId: string, candidateId: string): Promise<boolean> {
  const key = `bloom:shown:${sessionId}`;
  const exists = await redis.call('BF.EXISTS', key, candidateId);
  return exists === 1;
}

// Mark candidate as shown
async function markShown(sessionId: string, candidateId: string): Promise<void> {
  const key = `bloom:shown:${sessionId}`;
  await redis.call('BF.ADD', key, candidateId);
}
```

**Sources:**
- [Redis Bloom Filter Docs](https://redis.io/docs/latest/develop/data-types/probabilistic/bloom-filter/)
- [RedisBloom GitHub](https://github.com/RedisBloom/RedisBloom)

**Note:** RedisBloom requires Redis Stack or the RedisBloom module. Verify deployment configuration supports this.

---

### 8. Node.js SDK Updates (HIGH Confidence)

**Current versions in package.json should be verified/updated:**

| Package | Current | Recommended | Purpose |
|---------|---------|-------------|---------|
| `pg` | ^8.11.3 | ^8.13.0 | PostgreSQL client |
| `pgvector` | ^0.2.1 | ^0.2.1 | pgvector support (current) |
| `ioredis` | ^5.3.2 | ^5.4.1 | Redis client |
| `@google-cloud/vertexai` | latest | ^1.9.0 | Pin version for stability |
| `together-ai` | (via axios) | ^0.9.0 | Official Together AI SDK |
| `@ai-sdk/togetherai` | - | ^1.0.30 | Vercel AI SDK provider (optional) |
| `@google/genai` | - | ^1.37.0 | Gemini API (if using directly) |

**Installation:**
```bash
npm install together-ai@^0.9.0 --prefix services
npm install @google/genai@^1.37.0 --prefix services
npm update pg@^8.13.0 ioredis@^5.4.1 --prefix services
```

**Sources:**
- [together-ai npm](https://www.npmjs.com/package/together-ai)
- [@ai-sdk/togetherai npm](https://www.npmjs.com/package/@ai-sdk/togetherai)
- [@google/genai npm](https://www.npmjs.com/package/@google/genai)

---

## Alternatives Considered and Rejected

| Technology | Why Considered | Why Rejected |
|------------|----------------|--------------|
| **Elasticsearch** | Native hybrid search | Adds operational complexity; pgvector sufficient |
| **Pinecone/Weaviate** | Managed vector DB | Constraint: must use existing PostgreSQL |
| **LightGBM Ranker** | Learning-to-rank | Requires training data; LLM reranking sufficient |
| **Neo4j** | Skills graph | Constraint: no new databases; ESCO in PostgreSQL |
| **Transformers.js** | Local cross-encoder | Latency concerns in Node.js; API rerankers better |
| **OpenAI embeddings** | Proven ecosystem | Gemini outperforms on benchmarks |

---

## Architecture Integration

```
                          Existing Stack (Keep)
                          ====================

[Job Description] --> [Gemini Embeddings] --> [pgvector HNSW]
                                                    |
                                                    v
                          +-----------------------------+
                          |     RRF Fusion (NEW)        |
                          |  Vector + FTS + Signals     |
                          +-----------------------------+
                                    |
                                    v
                          +-----------------------------+
                          |   Multi-Signal Scoring      |
                          |   (Enhanced TypeScript)     |
                          +-----------------------------+
                                    |
                                    v
                          +-----------------------------+
                          |   LLM Reranking (Existing)  |
                          |   Together AI + Gemini      |
                          |   + Enhanced Prompts (NEW)  |
                          +-----------------------------+
                                    |
                                    v
                          [Ranked Results with Evidence]
```

---

## Confidence Assessment

| Recommendation | Confidence | Reason |
|----------------|------------|--------|
| RRF Fusion | HIGH | Proven pattern, pure SQL, no dependencies |
| Multi-Signal Scoring | HIGH | Feature engineering, uses existing data |
| Skills Inference Enhancement | HIGH | Prompt engineering, existing Together AI |
| Career Trajectory | MEDIUM | Rule-based feasible, ML deferred |
| Reranker APIs (optional) | MEDIUM | Current LLM approach works; APIs are additive |
| Redis Bloom Filters | MEDIUM | Requires Redis Stack verification |
| Package Updates | HIGH | Standard maintenance, verified versions |

---

## Implementation Priority

**Phase 1 (Immediate):**
1. RRF fusion in pgvector queries
2. Multi-signal scoring in TypeScript
3. Enhanced enrichment prompts for skills/trajectory

**Phase 2 (After Validation):**
4. ESCO taxonomy integration
5. Redis Bloom filters (if Redis Stack available)
6. Query-type-aware reranking prompts

**Phase 3 (If Needed):**
7. Cohere/Jina reranker API for speed-critical paths
8. Learning-to-rank if labeled feedback data accumulates

---

## Summary

The existing Headhunter stack requires **zero new databases** and **minimal new libraries** to support leader-level search. The path forward is:

1. **SQL enhancements** (RRF, multi-signal)
2. **Prompt engineering** (skills inference, trajectory)
3. **TypeScript feature engineering** (signal computation)
4. **Optional API additions** (Cohere/Jina rerankers if latency demands)

Total estimated new npm dependencies: 2-3 packages
Total new infrastructure: None
Compatibility with existing pgvector + Redis + Together AI: Full
