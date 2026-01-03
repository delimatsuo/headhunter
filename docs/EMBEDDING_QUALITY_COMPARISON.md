# Embedding Model Quality Comparison

**Date**: 2026-01-01
**Current Setup**: Vertex AI text-embedding-004 + Gemini 2.5 Flash (reranking)

---

## Important Distinction

Your system uses **two different AI components**:

| Component | Current Model | Purpose |
|-----------|---------------|---------|
| **Embeddings** | text-embedding-004 | Vector search (finding candidates) |
| **Reranking** | Gemini 2.5 Flash | LLM scoring (ranking top candidates) |

**Gemini 2.5 Flash is NOT an embedding model** - it's a generative model used for reranking. For embeddings, the comparison should be between:
- Vertex AI text-embedding-004 (current)
- Gemini gemini-embedding-001 (Google's newer embedding model)
- Together AI embeddings (BGE, M2-BERT, etc.)
- Other providers (OpenAI, Voyage, Cohere)

---

## MTEB Benchmark Scores (Retrieval Focus)

### Tier 1: State-of-the-Art (2025)

| Model | Provider | MTEB Overall | Retrieval | Dimensions | Cost |
|-------|----------|--------------|-----------|------------|------|
| **voyage-3-large** | Voyage AI | ~69% | **#1** | 1024 | $0.12/1M |
| **NV-Embed-v2** | NVIDIA | ~69% | Top | 4096 | Self-host |
| **gemini-embedding-001** | Google | ~68% | Top 5 | 768-3072 | $0.15/1M |
| **Qwen3-Embedding-8B** | Alibaba | ~67% | Top 10 | 4096 | Self-host |

### Tier 2: Strong Performers

| Model | Provider | MTEB Overall | Retrieval | Dimensions | Cost |
|-------|----------|--------------|-----------|------------|------|
| **text-embedding-004** | Google/Vertex | **66.31%** | Good | 768 | $0.025/1M |
| **text-embedding-3-large** | OpenAI | 64.6% | Good | 3072 | $0.13/1M |
| **BGE-M3** | BAAI | ~64% | Good | 1024 | Free (OSS) |
| **Cohere embed-v3** | Cohere | ~62% | Average | 1024 | $0.10/1M |

### Tier 3: Budget/Specialized

| Model | Provider | MTEB Overall | Retrieval | Dimensions | Cost |
|-------|----------|--------------|-----------|------------|------|
| **M2-BERT-80M-32k** | Together AI | ~58%* | Long-context | 768 | **$0.008/1M** |
| **BGE-large-en-v1.5** | BAAI | ~54% | Average | 1024 | Free (OSS) |
| **text-embedding-3-small** | OpenAI | ~62% | Average | 1536 | $0.02/1M |

*M2-BERT excels at long-context (32k tokens) but scores lower on short-text benchmarks

---

## Quality vs Cost Analysis

### Your Current Setup: text-embedding-004

| Metric | Score | Notes |
|--------|-------|-------|
| MTEB Overall | 66.31% | #1 among 768-dim models |
| Retrieval | Good | Strong for recruitment use case |
| Dimensions | 768 | Matches your pgvector setup |
| Cost | $0.025/1M chars | ~$200/month for your usage |

### Option 1: gemini-embedding-001 (Google's Newer Model)

| Metric | Score | Notes |
|--------|-------|-------|
| MTEB Overall | ~68% | **+2.5% improvement** |
| Retrieval | #1 on MTEB multilingual | Excellent |
| Dimensions | 768-3072 | Flexible |
| Cost | **$0.15/1M tokens** | ~$50-100/month (6x cheaper than Vertex) |
| Free Tier | 1,500 req/day | Could be **$0** |

**Verdict**: Better quality AND cheaper than text-embedding-004

### Option 2: Together AI M2-BERT-80M-32k

| Metric | Score | Notes |
|--------|-------|-------|
| MTEB Overall | ~58% | **-8% quality drop** |
| Retrieval | Excellent for long docs | #1 on LoCoV1 benchmark |
| Dimensions | 768 | Matches your pgvector |
| Cost | **$0.008/1M tokens** | ~$5-15/month |

**Verdict**: Significant cost savings but quality tradeoff

### Option 3: voyage-3-large (Premium)

| Metric | Score | Notes |
|--------|-------|-------|
| MTEB Overall | ~69% | **+4% improvement** |
| Retrieval | #1 overall | Best in class |
| Dimensions | 1024 | Would need pgvector migration |
| Cost | $0.12/1M tokens | ~$40-80/month |

**Verdict**: Best quality, moderate cost, requires dimension change

---

## Recruitment-Specific Considerations

### What Matters for Candidate Search

| Factor | Importance | Best Option |
|--------|------------|-------------|
| **Semantic similarity** | Critical | voyage-3-large, gemini-embedding-001 |
| **Title/role matching** | High | All models perform similarly |
| **Skill extraction** | High | Gemini or Voyage (instruction-tuned) |
| **Long resume handling** | Medium | M2-BERT-32k (32k context) |
| **Multilingual** | Low (PT-BR) | gemini-embedding-001, BGE-M3 |

### Your Reranking Compensates for Embedding Gaps

Your current architecture uses **Gemini 2.5 Flash for reranking**, which:
- Re-scores top 50 candidates with full context
- Catches semantic matches that embeddings miss
- Adds reasoning/rationale

**This means**: You can use a slightly weaker embedding model (like M2-BERT) because reranking will fix ranking errors in the top results.

---

## Recommendation Matrix

### If Quality is Priority (Budget: Flexible)

| Choice | Model | Quality | Cost/Month |
|--------|-------|---------|------------|
| **Best** | voyage-3-large | 69% | ~$60 |
| **Great** | gemini-embedding-001 | 68% | ~$0-50 |
| **Current** | text-embedding-004 | 66% | ~$200 |

### If Cost is Priority (Quality: Acceptable)

| Choice | Model | Quality | Cost/Month |
|--------|-------|---------|------------|
| **Cheapest** | M2-BERT-80M-32k | 58% | ~$10 |
| **Best Value** | gemini-embedding-001 (free) | 68% | **$0** |
| **Balanced** | BGE-M3 (self-host) | 64% | ~$0 |

### Recommended Path

**Switch to gemini-embedding-001:**
- ✅ **Better quality** (+2.5% MTEB)
- ✅ **Lower cost** (Free tier or $0.15/1M vs $0.025/1M)
- ✅ **Same ecosystem** (Google)
- ✅ **768 dimensions** (compatible with pgvector)
- ⚠️ Note: text-embedding-004 deprecated Nov 2025

---

## Quality Testing Protocol

Before switching, run this comparison:

### Test Dataset
1. Select 50 diverse job descriptions (mix of roles/levels)
2. For each JD, identify 10 "known good" candidates manually
3. Run search with current model and candidate model

### Metrics to Compare
```
Recall@10:   How many of the 10 "good" candidates appear in top 10?
Recall@20:   How many appear in top 20?
Recall@50:   How many appear in top 50 (before rerank)?
MRR:         Mean Reciprocal Rank of first "good" candidate
```

### Acceptable Thresholds
- Recall@50 drop < 5% is acceptable (reranking compensates)
- Recall@10 drop < 10% is acceptable
- If MRR drops significantly, reject the model

---

## Summary Table

| Model | Quality (MTEB) | Cost/Month | Migration Effort | Recommendation |
|-------|----------------|------------|------------------|----------------|
| **text-embedding-004** | 66.3% | ~$200 | Current | Baseline |
| **gemini-embedding-001** | 68% | $0-50 | Low | ⭐ **Best Choice** |
| **voyage-3-large** | 69% | ~$60 | Medium | Premium option |
| **M2-BERT-80M-32k** | 58% | ~$10 | Low | Budget option |
| **BGE-M3** | 64% | ~$0 | High (self-host) | DIY option |

---

## Action Plan

1. **Immediate**: Test gemini-embedding-001 with 50 sample searches
2. **If quality acceptable**: Migrate to Gemini (free tier first)
3. **Monitor**: Track search quality metrics post-migration
4. **Fallback**: Keep Vertex AI as backup for 1 month

---

## Sources

- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard)
- [Google Cloud - text-embedding-004 announcement](https://cloud.google.com/blog/products/ai-machine-learning/google-cloud-announces-new-text-embedding-models)
- [Gemini Embedding GA announcement](https://developers.googleblog.com/gemini-embedding-available-gemini-api/)
- [Voyage AI - voyage-3-large](https://blog.voyageai.com/2025/01/07/voyage-3-large/)
- [Together AI - M2-BERT](https://www.together.ai/blog/long-context-retrieval-models-with-monarch-mixer)
- [Top Embedding Models 2025](https://artsmart.ai/blog/top-embedding-models-in-2025/)
