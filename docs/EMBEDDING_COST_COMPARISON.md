# Embedding Provider Cost Comparison

**Date**: 2026-01-01
**Current Provider**: Vertex AI text-embedding-004
**Current Monthly Cost**: ~$206.29 (39% of total GCP bill)

---

## Pricing Comparison

### Per Million Tokens/Characters

| Provider | Model | Price/1M tokens | Price/1M chars* | Dimensions |
|----------|-------|-----------------|-----------------|------------|
| **Vertex AI** | text-embedding-004 | ~$0.10 | **$0.025** | 768 |
| **Together AI** | M2-BERT-80M-32k | $0.008 | **$0.002** | 768 |
| **Gemini API** | gemini-embedding-001 | $0.15 | **$0.038** | 768-3072 |
| **Gemini API** | gemini-embedding-001 | **FREE** | **FREE** | 768-3072 |

*Assuming ~4 characters per token

### Key Findings

| Provider | Relative Cost | Notes |
|----------|---------------|-------|
| **Together AI** | **12.5x cheaper** | $0.002 vs $0.025 per 1M chars |
| **Gemini API (Free)** | **FREE** | 1,500 requests/day limit |
| **Gemini API (Paid)** | 1.5x more expensive | But includes free tier |

---

## Your Current Usage Analysis

### What's in the $206.29 Vertex AI bill?

Based on your architecture, Vertex AI costs include:

| Usage Type | Estimated % | Notes |
|------------|-------------|-------|
| **Embeddings (text-embedding-004)** | ~60-70% | Search queries + candidate uploads |
| **Ranking API** | ~20-30% | Cross-encoder reranking (if used) |
| **Other Vertex services** | ~10% | Misc API calls |

### Estimated Embedding Volume

At $0.025/1M characters:
- $206/month ÷ $0.025 = **~8.2 billion characters/month**
- Or ~8.2M searches with average 1K char queries

**More likely breakdown:**
- ~29K candidates × 3K chars = 87M chars (one-time, already done)
- Search queries: ~100-500/day × 1-2K chars = ~3-30M chars/month
- **Ranking API is likely the bigger cost driver**

---

## Cost Projection by Provider

### Scenario: 500 searches/day + 100 new candidates/month

| Provider | Embedding Cost | Notes |
|----------|----------------|-------|
| **Current (Vertex AI)** | ~$150-200/mo | Includes ranking API |
| **Together AI** | ~$5-15/mo | **92-97% savings** |
| **Gemini Free Tier** | ~$0/mo | If under 1,500 req/day |
| **Gemini Paid** | ~$20-40/mo | If over free tier |

### Break-Even Analysis

| Provider | Free Until | Then Costs |
|----------|------------|------------|
| **Gemini API** | 1,500 req/day (~45K/month) | $0.15/1M tokens |
| **Together AI** | No free tier | $0.008/1M tokens always |

---

## Recommendation

### Best Option: **Together AI Embeddings**

**Why:**
1. **92-97% cost reduction** ($200/mo → $5-15/mo)
2. **Already in your stack** - Together AI used for enrichment (Qwen 2.5 32B)
3. **PRD recommends it** - Lines 6, 28 mention evaluating Together AI embeddings
4. **Same 768 dimensions** - Compatible with existing pgvector setup
5. **High quality** - M2-BERT-80M performs well on retrieval benchmarks

### Migration Path

```
Current:  Vertex AI (text-embedding-004) → $200/mo
Target:   Together AI (M2-BERT-80M)      → $10-15/mo
Savings:  ~$185/mo (~$2,200/year)
```

### Implementation Effort

| Task | Effort | Risk |
|------|--------|------|
| Update embedding provider | Low | Low |
| Re-embed 29K candidates | Medium | None (one-time batch) |
| Test search quality | Low | Low |
| Monitor and adjust | Ongoing | Low |

---

## Alternative: Gemini Free Tier

If usage is under 1,500 requests/day:

**Pros:**
- Completely free
- Same Google ecosystem
- Higher dimension options (up to 3072)

**Cons:**
- Rate limited (may need throttling)
- Requires migration to newer model (text-embedding-004 deprecated Nov 2025)
- Less cost-predictable at scale

---

## Action Items

### Immediate (This Week)
1. ✅ Increase cache TTLs (already done) - reduces embedding calls
2. [ ] Audit actual Vertex AI usage breakdown in Cloud Console
3. [ ] Test Together AI embedding quality with sample queries

### Short-Term (This Month)
4. [ ] Implement Together AI embedding provider
5. [ ] Run parallel comparison (Vertex vs Together) on 100 searches
6. [ ] If quality acceptable, migrate to Together AI

### Code Change Required

Update `functions/src/embedding-provider.ts`:

```typescript
class TogetherProvider implements EmbeddingProvider {
  name = "together";

  async generateEmbedding(text: string): Promise<number[]> {
    const response = await fetch("https://api.together.xyz/v1/embeddings", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${process.env.TOGETHER_API_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: "togethercomputer/m2-bert-80M-32k-retrieval",
        input: text.substring(0, 32000) // 32k context
      })
    });

    const data = await response.json();
    return data.data[0].embedding;
  }
}
```

---

## Summary

| Metric | Vertex AI | Together AI | Savings |
|--------|-----------|-------------|---------|
| Monthly Cost | ~$200 | ~$10-15 | **$185-190** |
| Annual Cost | ~$2,400 | ~$120-180 | **~$2,200** |
| Quality | Excellent | Very Good | Minimal loss |
| Migration Effort | N/A | 1-2 days | One-time |

**Bottom Line**: Switching to Together AI embeddings could save **~$185/month (~$2,200/year)** with minimal quality impact and low migration effort.

---

## Sources

- [Vertex AI Pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)
- [Together AI Pricing](https://www.together.ai/pricing)
- [Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Together AI Embedding Models](https://blog.llmradar.ai/together-ai-together-ai-embedding-up-to-150m/)
