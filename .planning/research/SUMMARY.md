# Research Summary: Leader-Level Search Capabilities

**Domain:** AI-powered candidate matching and talent search
**Researched:** 2026-01-24
**Overall Confidence:** HIGH

---

## Executive Summary

This research investigates the 2025/2026 state-of-the-art for AI-powered candidate matching to inform adding leader-level search capabilities to the Headhunter platform. The existing stack (PostgreSQL + pgvector, Redis, Together AI, Gemini embeddings, Fastify microservices) is already well-aligned with industry best practices.

**Key finding:** The path to leader-level search is **enhancement, not replacement**. The core technologies are correct; improvements come from better fusion algorithms, structured signal scoring, and prompt engineering rather than new infrastructure.

The 3-stage pipeline (retrieval, scoring, reranking) architecture already in place matches industry patterns. Enhancements focus on:
1. **Hybrid search with RRF fusion** - combining vector and text retrieval
2. **Multi-signal scoring** - weighted combination of 10+ candidate signals
3. **Career trajectory features** - computed during enrichment
4. **Skills inference enhancement** - better prompts, optional ESCO taxonomy

---

## Key Findings

**Stack:** Keep Gemini embeddings + pgvector + Together AI. Add RRF fusion in SQL, multi-signal scoring in TypeScript.

**Architecture:** 3-stage pipeline is correct. Enhancement is vertical (better at each stage) not horizontal (more stages).

**Critical pitfall:** Do not add new databases. pgvector handles hybrid search natively; adding Elasticsearch or dedicated vector DBs increases complexity without proportional benefit.

---

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Hybrid Search Foundation
- **Implement RRF fusion** in pgvector queries
- **Multi-signal scoring** framework in TypeScript
- **Signal normalization** for consistent 0-1 scales

**Rationale:** RRF is proven, pure SQL, zero new dependencies. Establishes measurement baseline before adding complexity.

### Phase 2: Career Intelligence
- **Career trajectory computation** during enrichment
- **Promotion velocity, tenure patterns, company pedigree** signals
- **Leadership scope** extraction from titles/descriptions

**Rationale:** Feature engineering in existing Together AI enrichment. No new ML models; rule-based computation is explainable and sufficient.

### Phase 3: Skills Enhancement
- **Enhanced skill extraction prompts** for Together AI
- **Inferred skills with confidence scores**
- **Optional ESCO taxonomy mapping** for standardization

**Rationale:** Skills graph at enrichment time, not search time. Inference during indexing avoids runtime latency.

### Phase 4: Query-Aware Ranking
- **Query type detection** (IC vs Manager vs Executive)
- **Dynamic weight profiles** per query type
- **Enhanced LLM reranking prompts** with chain-of-thought

**Rationale:** Different search intents need different signal weights. Existing LLM reranking can be enhanced with structured prompts.

### Phase 5: Performance Optimization (If Needed)
- **API-based rerankers** (Cohere/Jina) for latency-critical paths
- **Redis Bloom filters** for deduplication
- **Caching strategies** for repeated queries

**Rationale:** Only add if Phase 1-4 reveal latency issues. Current architecture handles p95 < 1.2s target.

---

## Phase Ordering Rationale

1. **RRF First:** Establishes hybrid search baseline, enables A/B testing of signal weights
2. **Trajectory Second:** Most valuable for leader-level search, differentiates from keyword matching
3. **Skills Third:** Enhances existing enrichment, builds on trajectory foundation
4. **Query-Aware Fourth:** Requires signals from phases 2-3 to tune weights effectively
5. **Optimization Fifth:** Only after functional requirements met

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack recommendations | HIGH | Verified with current sources, compatible with constraints |
| RRF implementation | HIGH | Pure SQL, proven pattern, multiple authoritative sources |
| Multi-signal scoring | HIGH | Feature engineering, no external dependencies |
| Career trajectory | MEDIUM | Rule-based feasible; ML alternative deferred |
| Skills inference | MEDIUM | Depends on prompt engineering effectiveness |
| ESCO integration | MEDIUM | Data asset available, integration complexity unknown |
| Reranker APIs | MEDIUM | Additive option if latency demands |

---

## Gaps to Address

1. **ESCO taxonomy complexity** - Need to evaluate size/query patterns before committing
2. **Company pedigree scoring** - Requires company database or API for tier classification
3. **Learning-to-rank feasibility** - Deferred until labeled feedback data accumulates
4. **Redis Stack availability** - Verify Memorystore supports RedisBloom in production

---

## Research Flags for Phases

| Phase | Research Needed? | Reason |
|-------|-----------------|--------|
| Phase 1 (RRF) | LOW | Standard patterns, well-documented |
| Phase 2 (Trajectory) | LOW | Rule-based, internal data |
| Phase 3 (Skills) | MEDIUM | Prompt engineering requires iteration |
| Phase 4 (Query-Aware) | MEDIUM | Weight tuning needs experimentation |
| Phase 5 (Optimization) | DEPENDS | Only if latency issues surface |

---

## Files Created

| File | Purpose |
|------|---------|
| `.planning/research/STACK.md` | Detailed technology recommendations with rationale |
| `.planning/research/SUMMARY.md` | Executive summary with roadmap implications |

---

## Ready for Roadmap

Research complete. The existing stack is sound; enhancements are additive. Recommend proceeding with phase structure outlined above.

**Total new npm dependencies estimated:** 2-3 packages (together-ai SDK, optional @google/genai update)
**Total new infrastructure:** None
**Breaking changes:** None
**Migration required:** None

---

## Sources

**Hybrid Search & RRF:**
- [ParadeDB: Hybrid Search Manual](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual)
- [Jonathan Katz: pgvector Hybrid Search](https://jkatz05.com/post/postgres/hybrid-search-postgres-pgvector/)

**Reranking:**
- [ZeroEntropy: Best Reranking Models 2025](https://www.zeroentropy.dev/articles/ultimate-guide-to-choosing-the-best-reranking-model-in-2025)
- [Databricks: Mosaic AI Reranking](https://www.databricks.com/blog/reranking-mosaic-ai-vector-search-faster-smarter-retrieval-rag-agents)

**Embeddings:**
- [AI Multiple: Embedding Models 2026](https://research.aimultiple.com/embedding-models/)
- [VentureBeat: Google #1 on Leaderboard](https://venturebeat.com/ai/new-embedding-model-leaderboard-shakeup-google-takes-1-while-alibabas-open-source-alternative-closes-gap/)

**Skills & Career:**
- [Skill-LLM Research](https://arxiv.org/html/2410.12052v1)
- [Career Path Prediction Research](https://www.frontiersin.org/journals/big-data/articles/10.3389/fdata.2025.1564521/full)
- [ESCO Taxonomy](https://esco.ec.europa.eu/en/use-esco/download)

**Multi-Signal Ranking:**
- [Algolia: Multi-Signal Ranking](https://www.algolia.com/blog/product/multi-signal-ranking)
- [Google ML: Recommendation Scoring](https://developers.google.com/machine-learning/recommendation/dnn/scoring)
