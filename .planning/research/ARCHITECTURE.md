# Architecture Patterns for Leader-Level Search Pipeline

**Domain:** AI-powered candidate search and talent matching
**Researched:** 2026-01-24
**Confidence:** HIGH (based on industry patterns and existing codebase analysis)

## Executive Summary

Modern talent matching systems use a multi-stage retrieval and ranking architecture that balances recall, precision, and latency. The dominant pattern is a 3-stage pipeline: (1) fast approximate retrieval, (2) multi-signal scoring/filtering, (3) LLM-powered reranking. This aligns with LinkedIn's documented architecture and industry best practices from Pinecone, Elastic, and Databricks.

The existing Headhunter architecture already implements most of this pattern. The enhancement opportunity lies in formalizing the scoring stage as a dedicated component and adding career trajectory prediction and skills inference capabilities.

## Recommended Architecture

### Current State Analysis

The existing architecture has these components:
- **hh-embed-svc** (7101): Embedding generation
- **hh-search-svc** (7102): Hybrid search orchestration
- **hh-rerank-svc** (7103): LLM-based reranking (Gemini/Together)
- **hh-enrich-svc** (7108): Profile enrichment
- PostgreSQL + pgvector for vector storage
- Redis for caching

The current `LegacyEngine` in functions/src/engines/ already implements a sophisticated 3-stage pipeline:
1. **Retrieval**: Firestore function queries + pgvector similarity
2. **Multi-signal scoring**: Function match, level match, company pedigree, vector similarity, specialty match
3. **LLM Reranking**: Gemini 2.0 Flash with batched processing

### Proposed Architecture Enhancement

```
                                  Job Description
                                        |
                                        v
                              +------------------+
                              |  Job Classifier  |
                              | (function/level) |
                              +------------------+
                                        |
        +-------------------------------+-------------------------------+
        |                               |                               |
        v                               v                               v
+----------------+            +------------------+            +------------------+
| Vector Search  |            | Deterministic    |            | Specialty Filter |
| (pgvector ANN) |            | Filters (PG)     |            | (pre-retrieval)  |
| 300-500 cands  |            | function/level   |            | backend/frontend |
+----------------+            +------------------+            +------------------+
        |                               |                               |
        +-------------------------------+-------------------------------+
                                        |
                                        v
                              +------------------+
                              |  MERGE & DEDUP   |
                              |  600-800 cands   |
                              +------------------+
                                        |
                                        v
     +------------------------------------------------------------------+
     |                     MULTI-SIGNAL SCORING SERVICE                  |
     |                                                                    |
     |  +--------------+  +---------------+  +------------------+        |
     |  | Career       |  | Skills        |  | Company Pedigree |        |
     |  | Trajectory   |  | Inference     |  | Scorer           |        |
     |  | Predictor    |  | Engine        |  |                  |        |
     |  +--------------+  +---------------+  +------------------+        |
     |         |                 |                    |                  |
     |         v                 v                    v                  |
     |  +--------------------------------------------------+            |
     |  |           Composite Score Calculator             |            |
     |  | (weighted combination with mode-specific tuning) |            |
     |  +--------------------------------------------------+            |
     +------------------------------------------------------------------+
                                        |
                                        v
                              +------------------+
                              | Top-K Selection  |
                              |   50-100 cands   |
                              +------------------+
                                        |
                                        v
     +------------------------------------------------------------------+
     |                    LLM RERANKING SERVICE                          |
     |                                                                    |
     |  - Career trajectory reasoning                                    |
     |  - Tech stack fit evaluation                                      |
     |  - Seniority reality check                                        |
     |  - Meaningful rationale generation                                |
     +------------------------------------------------------------------+
                                        |
                                        v
                              +------------------+
                              |  Final Results   |
                              |    20-50 cands   |
                              +------------------+
```

### Component Boundaries

| Component | Responsibility | Communicates With | Stateless? |
|-----------|---------------|-------------------|------------|
| **Job Classifier** | Parse JD into function/level/specialty | Search orchestrator | Yes |
| **Vector Retriever** | ANN search via pgvector | PostgreSQL | Yes |
| **Deterministic Filter** | Function/level/country filters | PostgreSQL | Yes |
| **Specialty Filter** | Backend/frontend/etc filtering | PostgreSQL | Yes |
| **Multi-Signal Scorer** | Composite scoring with multiple signals | Redis (cache) | Yes |
| **Career Trajectory Predictor** | Predict progression, interest, fit | Redis (models/cache) | Yes |
| **Skills Inference Engine** | Infer skills from context | Redis (cache) | Yes |
| **LLM Reranker** | Deep reasoning, rationale generation | Gemini/Together API | Yes |

### Data Flow

```
1. JOB INPUT
   - Raw job description text
   - Optional: required skills, target companies, experience level

2. CLASSIFICATION (5-20ms)
   - Function: engineering, product, data, sales, etc.
   - Level: c-level, vp, director, manager, senior, mid, junior
   - Specialty: backend, frontend, mobile, data, devops, etc.
   - Tech stack: Node.js, Python, Java, etc.

3. PARALLEL RETRIEVAL (30-100ms)
   - Vector search: cosine similarity via pgvector HNSW
   - Function query: Firestore/PG index on function field
   - Specialty filter: Pre-filter by engineering specialty

4. MERGE & DEDUP (5-10ms)
   - Union of retrieval results
   - Deduplicate by candidate_id
   - Preserve source attribution

5. MULTI-SIGNAL SCORING (20-50ms)
   Per candidate:
   - Function match score (0-60 pts)
   - Level match score (0-40 pts)
   - Company pedigree score (0-30 pts)
   - Vector similarity score (0-15 pts)
   - Specialty match score (0-25 pts)
   - Career trajectory prediction (0-20 pts) [NEW]
   - Skills inference confidence (0-15 pts) [NEW]

6. TOP-K SELECTION (1-5ms)
   - Sort by composite score
   - Select top 50-100 for reranking
   - Apply hard filters (career trajectory - won't step down)

7. LLM RERANKING (500-1500ms)
   - Batched processing (15 candidates per batch)
   - Tech stack fit reasoning
   - Seniority reality check
   - Rationale generation

8. FINAL RESULTS (1ms)
   - Return top 20-50 candidates
   - Include match rationale
   - Include score breakdown
```

## Patterns to Follow

### Pattern 1: Two-Stage Retrieval with Cross-Encoder Reranking

**What:** Use bi-encoders (embeddings) for broad recall, cross-encoders (LLM) for precision.

**When:** Always for search systems requiring both recall and precision.

**Why this works for talent matching:**
- Bi-encoders process query/candidate independently = fast
- Cross-encoders see query+candidate together = nuanced matching
- 10-15 point improvement in recall@10 is typical

**Evidence:** LinkedIn's documented architecture uses multi-aspect First Pass Ranker for recall (XGBoost/GBDT) and Second Pass Ranker for precision (neural nets).

### Pattern 2: Mode-Specific Scoring Weights

**What:** Adjust scoring weights based on search type (executive vs IC).

**When:** Search target varies significantly in what signals matter.

**Example:**
```typescript
const weights = isExecutiveSearch
  ? { function: 50, vector: 15, company: 25, level: 35, specialty: 0 }
  : { function: 25, vector: 25, company: 10, level: 15, specialty: 25 };
```

**Why:** For C-level searches, function alignment and company pedigree matter most. For IC searches, specialty (backend vs frontend) and vector similarity (semantic fit) matter more.

### Pattern 3: Career Trajectory as Filter, Not Just Score

**What:** Hard-filter candidates who would be stepping DOWN in their career.

**When:** The role is clearly below the candidate's current level.

**Example:**
```typescript
// A Principal engineer won't accept a Senior role
const levelsAbove = getLevelsAbove(targetLevel);
candidates = candidates.filter(c => !levelsAbove.includes(c.level));
```

**Why:** Even if a Principal is "technically qualified" for a Senior role, they won't take it. Showing them wastes recruiter time.

### Pattern 4: Effective Level Adjustment by Company Tier

**What:** Adjust perceived seniority based on company tier (FAANG+, Big Tech, Startup).

**When:** Comparing candidates across different company sizes.

**Example:**
```typescript
// FAANG Director = VP elsewhere
// Startup CTO = might be interested in VP at big company
const companyTier = getCompanyTier(candidate); // 0, 1, or 2
const effectiveLevel = adjustLevel(nominalLevel, companyTier);
```

**Why:** Title inflation varies by company size. A "CTO" at a 10-person startup is not equivalent to a CTO at Google.

### Pattern 5: Specialty Pre-Filtering for Engineering Roles

**What:** Filter by specialty (backend, frontend, etc.) BEFORE expensive scoring.

**When:** Job clearly specifies a specialty.

**Example:**
```
Job: "Senior Backend Engineer"
Filter: Keep backend, fullstack. Exclude pure frontend, mobile, QA.
```

**Why:** A frontend engineer scoring high on "general engineering" signals still shouldn't appear in a backend search.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Monolithic Scoring Logic

**What:** Putting all scoring logic in one giant function.

**Why bad:** Hard to test, hard to extend, impossible to A/B test individual signals.

**Instead:** Separate scoring into independent functions that can be composed. Each scorer should be unit-testable.

### Anti-Pattern 2: Over-relying on Vector Similarity

**What:** Using vector similarity as the primary (or only) signal.

**Why bad:** Embeddings capture semantic similarity but miss:
- Career trajectory (won't step down)
- Tech stack specificity (Node.js vs Java)
- Company tier effects on title meaning

**Instead:** Vector similarity is ONE signal among many. Weight it appropriately (15-25% depending on search mode).

### Anti-Pattern 3: LLM for Everything

**What:** Using LLM calls for every decision in the pipeline.

**Why bad:** Too slow, too expensive, inconsistent results.

**Instead:** Use deterministic rules where possible. Reserve LLM for final reranking where nuance matters.

### Anti-Pattern 4: Single Batch LLM Calls

**What:** Sending all candidates to LLM in one call.

**Why bad:** Token overflow, parse failures, timeout risk.

**Instead:** Batch into 15-candidate chunks. Process in parallel where possible.

### Anti-Pattern 5: Ignoring Unknown/Missing Data

**What:** Filtering out candidates with missing metadata.

**Why bad:** Loses potentially good candidates just because we don't have their level/specialty data.

**Instead:** Let candidates with unknown data pass through filters. Let LLM evaluate them with appropriate skepticism.

## Component Integration with Existing Services

### Integration Point 1: hh-search-svc (Port 7102)

The multi-signal scoring logic should be a module within `hh-search-svc`:

```
services/hh-search-svc/src/
  scoring/
    career-trajectory-scorer.ts    [NEW]
    skills-inference-scorer.ts     [NEW]
    company-pedigree-scorer.ts     [EXISTS - extract from search-service.ts]
    level-match-scorer.ts          [EXISTS - extract from search-service.ts]
    specialty-match-scorer.ts      [EXISTS - extract from legacy-engine.ts]
    composite-scorer.ts            [NEW - orchestrates all scorers]
```

**Rationale:** Scoring is tightly coupled with search. A separate microservice would add latency without benefit. However, the scorers should be independent modules for testing and A/B purposes.

### Integration Point 2: hh-rerank-svc (Port 7103)

Already handles LLM-based reranking. Enhancement:
- Add career trajectory context to rerank prompts
- Add tech stack fit evaluation
- Add seniority guidance specific to job level

### Integration Point 3: PostgreSQL (sourcing schema)

Extend `sourcing.candidates` table:
- `career_trajectory_signals` JSONB - precomputed trajectory indicators
- `inferred_skills` JSONB - skills inferred from context
- `effective_level` TEXT - adjusted for company tier

**Index strategy:**
```sql
CREATE INDEX idx_candidates_specialty ON sourcing.candidates USING GIN (specialties);
CREATE INDEX idx_candidates_effective_level ON sourcing.candidates (effective_level);
```

### Integration Point 4: Redis

Use for:
- Caching career trajectory predictions (TTL 24h)
- Caching skills inference results (TTL 24h)
- Company tier lookups (TTL 7d)

## Build Order (Dependencies)

### Phase 1: Foundation (Week 1-2)

**Goal:** Extract and formalize existing scoring logic.

1. Extract `company-pedigree-scorer.ts` from legacy-engine.ts
2. Extract `level-match-scorer.ts` from legacy-engine.ts
3. Extract `specialty-match-scorer.ts` from legacy-engine.ts
4. Create `composite-scorer.ts` that orchestrates existing scorers
5. Unit tests for each scorer

**Dependencies:** None (pure refactoring)

### Phase 2: Career Trajectory Predictor (Week 3-4)

**Goal:** Add career trajectory prediction as a scoring signal.

1. Define trajectory signal schema
2. Implement `career-trajectory-scorer.ts`:
   - Progression speed detection (job tenure analysis)
   - Career direction (IC vs management track)
   - Interest prediction (stepping up vs down)
3. Add PostgreSQL column for cached signals
4. Integration tests with real candidate data

**Dependencies:** Phase 1 (composite scorer infrastructure)

### Phase 3: Skills Inference Engine (Week 5-6)

**Goal:** Add skills inference from context.

1. Define inferred skills schema
2. Implement `skills-inference-scorer.ts`:
   - Technology co-occurrence patterns
   - Title-to-skills mapping
   - Confidence scoring
3. Add PostgreSQL column for inferred skills
4. Integration tests

**Dependencies:** Phase 1

### Phase 4: Enhanced LLM Reranking (Week 7-8)

**Goal:** Upgrade reranking with new signals.

1. Update rerank prompts with career trajectory context
2. Add tech stack fit evaluation to prompts
3. Add seniority guidance by job level
4. Add new signals to candidate context sent to LLM

**Dependencies:** Phase 2, Phase 3

### Phase 5: Performance Optimization (Week 9-10)

**Goal:** Ensure production performance targets are met.

1. Redis caching for trajectory and skills predictions
2. Batch precomputation for popular searches
3. Load testing with 29K+ candidates
4. Latency optimization (target: p95 < 1.2s)

**Dependencies:** Phase 1-4

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Total search latency (p95) | < 1.2s | ~1.0s |
| Retrieval stage | < 100ms | ~50ms |
| Scoring stage | < 50ms | ~30ms |
| Reranking stage | < 1000ms | ~800ms |
| Cache hit rate | > 50% | ~30% |

## Scalability Considerations

| Concern | At 30K candidates | At 100K candidates | At 1M candidates |
|---------|-------------------|--------------------|--------------------|
| Vector index | Single PG instance | Sharded by specialty | Dedicated vector DB |
| Scoring | In-memory | Redis-cached | Pre-computed batch |
| LLM calls | Per-request | Cached by JD hash | Tiered caching |
| Storage | Single schema | Partitioned tables | Time-series archival |

## Sources

- [LinkedIn: AI Behind Recruiter Search and Recommendation Systems](https://www.linkedin.com/blog/engineering/recommendations/ai-behind-linkedin-recruiter-search-and-recommendation-systems) - LinkedIn's multi-layer ranking architecture
- [LinkedIn: LiRank Industrial Large Scale Ranking Models](https://arxiv.org/html/2402.06859v1) - Multi-task learning and architecture details
- [Pinecone: Rerankers and Two-Stage Retrieval](https://www.pinecone.io/learn/series/rag/rerankers/) - Cross-encoder reranking best practices
- [Elastic: Ranking and Reranking](https://www.elastic.co/docs/solutions/search/ranking) - Production ranking patterns
- [Databricks: Reranking in Mosaic AI Vector Search](https://www.databricks.com/blog/reranking-mosaic-ai-vector-search-faster-smarter-retrieval-rag-agents) - Performance benchmarks
- [Redis: RAG at Scale](https://redis.io/blog/rag-at-scale/) - Production caching patterns
- [ZeroEntropy: Guide to Choosing Reranking Models in 2025](https://www.zeroentropy.dev/articles/ultimate-guide-to-choosing-the-best-reranking-model-in-2025) - Model selection criteria
- [System Overflow: Production Architecture for Two Stage Retrieval](https://www.systemoverflow.com/learn/ml-recommendation-systems/content-based-filtering/production-architecture-two-stage-retrieval-and-re-ranking-pipeline) - Latency budgets
- [GeeksforGeeks: Microservices Architecture Best Practices 2025](https://www.geeksforgeeks.org/blogs/best-practices-for-microservices-architecture/) - Service separation patterns
- [Medium: Microservices for AI Applications](https://medium.com/@meeran03/microservices-architecture-for-ai-applications-scalable-patterns-and-2025-trends-5ac273eac232) - AI-specific microservices patterns
