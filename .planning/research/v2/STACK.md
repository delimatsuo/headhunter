# Technology Stack: v2.0 Advanced Intelligence Features

**Project:** Headhunter AI - v2.0 Advanced Intelligence Milestone
**Researched:** 2026-01-25
**Focus:** RNN trajectory prediction, NLP search, bias/compliance tooling
**Constraint:** No new databases, Together AI for LLM, p95 target 500ms

---

## Executive Summary

The v2.0 Advanced Intelligence features require **targeted stack additions** rather than architectural overhaul. The existing infrastructure (PostgreSQL + pgvector, Redis, Together AI, Gemini embeddings, Fastify microservices) remains the foundation.

**Key Recommendations:**

1. **RNN Trajectory Prediction:** ONNX Runtime for inference, PyTorch for training (offline)
2. **Natural Language Search:** Semantic Router (Python) + Together AI JSON mode for intent classification
3. **Bias/Compliance:** Fairlearn for metrics, custom audit logging in PostgreSQL
4. **Performance (sub-500ms):** pgvectorscale extension, connection pooling, parallel queries

**Total new npm dependencies:** 2-3 packages (onnxruntime-node, optional SDKs)
**Total new Python dependencies:** 4-5 packages (semantic-router, fairlearn, torch, onnx)
**New infrastructure:** None (constraint: no new databases)

---

## 1. RNN-Based Career Trajectory Prediction

### Recommendation: ONNX Runtime for Inference

**Why RNN/LSTM for trajectory?** Career paths are sequential data with temporal dependencies. An LSTM can learn patterns like "Principal Engineer at FAANG for 3+ years often leads to VP Engineering at Series C startup" better than rule-based heuristics.

**Architecture Decision:**
- **Training:** PyTorch (offline, local or Cloud ML)
- **Inference:** ONNX Runtime (lightweight, sub-50ms inference)
- **No GPU required:** CPU inference is sufficient for trajectory prediction (small models)

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Training | PyTorch | ^2.5.0 | Train LSTM models locally/Cloud ML |
| Export | ONNX | ^1.17.0 | Model format for portable inference |
| Node.js Inference | onnxruntime-node | ^1.23.2 | Run models in Fastify services |
| Python Inference | onnxruntime | ^1.20.0 | Run models in Python enrichment |

**Python dependencies (training/export):**
```bash
# Training environment only (not Cloud Run)
pip install torch>=2.5.0 onnx>=1.17.0 onnxruntime>=1.20.0
```

**Node.js dependencies (inference):**
```bash
npm install onnxruntime-node@^1.23.2
```

### Model Design Considerations

```python
# Career trajectory LSTM - compact architecture for sub-50ms inference
class CareerTrajectoryLSTM(nn.Module):
    def __init__(self, vocab_size=5000, embed_dim=64, hidden_dim=128, num_layers=2):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim)  # Title/company encoding
        self.lstm = nn.LSTM(embed_dim, hidden_dim, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_dim, 3)  # Predict: direction, velocity, fit_score

    def forward(self, x):
        embedded = self.embedding(x)
        lstm_out, _ = self.lstm(embedded)
        return self.fc(lstm_out[:, -1, :])  # Last timestep output
```

**ONNX Export Pattern:**
```python
# Export with dynamo (recommended for PyTorch 2.5+)
import torch.onnx

# Trace with fixed batch size 1 for inference
dummy_input = torch.randint(0, 5000, (1, 20))  # 20 career events
torch.onnx.export(model, dummy_input, "trajectory.onnx", dynamo=True)
```

**Node.js Inference Pattern:**
```typescript
import * as ort from 'onnxruntime-node';

const session = await ort.InferenceSession.create('./models/trajectory.onnx');
const input = new ort.Tensor('int64', careerEventIds, [1, 20]);
const results = await session.run({ input });
// Results: { direction: 0.8, velocity: 0.6, fit_score: 0.75 }
```

### Why NOT use larger ML frameworks:

| Rejected | Why |
|----------|-----|
| TensorFlow/TF Lite | Package size 400MB+, overkill for single model |
| PyTorch in Cloud Run | Cold start 10-30s, memory 2GB+ |
| HuggingFace Transformers | Wrong tool for sequence prediction |
| Cloud ML APIs (Vertex) | Adds latency, cost, complexity |

**Source:** [ONNX Runtime Serverless Deployment](https://pyimagesearch.com/2025/11/03/introduction-to-serverless-model-deployment-with-aws-lambda-and-onnx/)

---

## 2. Natural Language Search Interface

### Recommendation: Semantic Router + Together AI JSON Mode

**Two-tier approach:**
1. **Fast routing (sub-20ms):** Semantic Router uses vector similarity for intent classification
2. **Complex parsing (100-300ms):** Together AI with JSON mode for entity extraction

### Tier 1: Semantic Router for Intent Classification

Semantic Router by [Aurelio Labs](https://github.com/aurelio-labs/semantic-router) provides **superfast AI decision making** using vector embeddings instead of LLM calls.

| Package | Version | Purpose |
|---------|---------|---------|
| semantic-router | ^0.1.12 | Intent routing via embedding similarity |
| fastembed | ^0.5.0 | Local embedding encoder (optional) |

**Installation:**
```bash
pip install "semantic-router[local]>=0.1.12"  # Includes fastembed for local embeddings
```

**Intent Routes for Headhunter:**
```python
from semantic_router import Route, SemanticRouter
from semantic_router.encoders import GeminiEncoder  # Use existing Gemini

# Define intent routes
search_people = Route(
    name="search_candidates",
    utterances=[
        "Find me a senior engineering manager",
        "Show candidates with Python experience",
        "Who has worked at FAANG companies?",
        "Search for product managers in fintech",
    ]
)

search_by_name = Route(
    name="lookup_person",
    utterances=[
        "Find John Smith",
        "Show me Maria Garcia's profile",
        "Look up candidate Alex Chen",
    ]
)

filter_query = Route(
    name="filter_results",
    utterances=[
        "Only show people in San Francisco",
        "Filter by 10+ years experience",
        "Exclude candidates from startups",
    ]
)

complex_query = Route(
    name="complex_jd_search",
    utterances=[
        "We need a VP of Engineering for our Series B...",
        "Looking for CTO with fintech background...",
        # Long JD pastes route here
    ]
)

# Initialize router with existing Gemini encoder
encoder = GeminiEncoder(api_key=os.environ["GEMINI_API_KEY"])
router = SemanticRouter(encoder=encoder, routes=[search_people, search_by_name, filter_query, complex_query])

# Route query - sub-20ms latency
result = router(query)  # Returns: RouteChoice(name="search_candidates", function_call=None)
```

**Why Semantic Router:**
- **Speed:** 5ms-100ms vs 500ms-2000ms for LLM-based classification
- **Cost:** Uses existing Gemini embeddings, no additional API calls
- **Accuracy:** 95%+ for well-defined intents with good utterance examples
- **Fallback:** Routes to LLM for ambiguous queries

**Source:** [Semantic Router GitHub](https://github.com/aurelio-labs/semantic-router)

### Tier 2: Together AI for Entity Extraction

For complex queries that need entity extraction (skills, years, locations, company tiers), use Together AI's JSON mode.

**Together AI JSON Mode:**
```typescript
import Together from 'together-ai';

const together = new Together({ apiKey: process.env.TOGETHER_API_KEY });

interface QueryEntities {
  skills: string[];
  minYears?: number;
  maxYears?: number;
  locations?: string[];
  seniorityLevel?: 'ic' | 'lead' | 'manager' | 'director' | 'vp' | 'c-level';
  companyTiers?: ('startup' | 'scaleup' | 'enterprise' | 'faang')[];
  excludePatterns?: string[];
}

const response = await together.chat.completions.create({
  model: 'meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo',
  messages: [
    { role: 'system', content: 'Extract search parameters from the query. Respond only in JSON.' },
    { role: 'user', content: query }
  ],
  response_format: {
    type: 'json_schema',
    schema: QueryEntitiesSchema  // Pydantic-style schema
  }
});
```

**Supported Models for JSON Mode:**
- `meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo` (fastest, 100-200ms)
- `meta-llama/Llama-3.3-70B-Instruct-Turbo` (higher quality)
- `deepseek-ai/DeepSeek-V3` (best reasoning)

**Source:** [Together AI Structured Outputs](https://docs.together.ai/docs/json-mode)

### Node.js SDK Update

```bash
npm install together-ai@^0.9.0  # Official SDK with JSON mode support
```

---

## 3. Bias Reduction and Compliance Tooling

### Recommendation: Fairlearn + Custom Audit Logging

**Regulatory Context (2025-2026):**
- EEOC maintains focus on AI algorithmic fairness
- California rules effective October 2025 require bias testing and 4-year records
- Colorado AI Act effective February 2026 mandates bias audits
- Illinois bans ZIP codes as proxies for protected characteristics

**Source:** [AI in Hiring Compliance 2026](https://www.hrdefenseblog.com/2025/11/ai-in-hiring-emerging-legal-developments-and-compliance-guidance-for-2026/)

### Fairlearn for Fairness Metrics

| Package | Version | Purpose |
|---------|---------|---------|
| fairlearn | ^0.13.0 | Fairness metrics and mitigation |

**Installation:**
```bash
pip install fairlearn>=0.13.0
```

**Key Metrics for Hiring:**
```python
from fairlearn.metrics import (
    demographic_parity_difference,
    equalized_odds_difference,
    selection_rate,
    MetricFrame
)

def audit_search_results(
    candidates: list,
    selected: list[bool],
    protected_attribute: list  # e.g., age_group, inferred_gender
):
    """
    Compute fairness metrics for a search result set.
    Four-fifths rule: selection_rate(minority) / selection_rate(majority) >= 0.8
    """
    mf = MetricFrame(
        metrics={'selection_rate': selection_rate},
        y_true=[1] * len(candidates),  # All eligible
        y_pred=selected,
        sensitive_features=protected_attribute
    )

    # Four-fifths (80%) rule check
    rates = mf.by_group['selection_rate']
    min_rate = rates.min()
    max_rate = rates.max()
    four_fifths_ratio = min_rate / max_rate if max_rate > 0 else 1.0

    return {
        'selection_rates': rates.to_dict(),
        'demographic_parity_diff': demographic_parity_difference(
            y_true=[1] * len(candidates),
            y_pred=selected,
            sensitive_features=protected_attribute
        ),
        'four_fifths_ratio': four_fifths_ratio,
        'passes_four_fifths': four_fifths_ratio >= 0.8
    }
```

**Why Fairlearn over AI Fairness 360:**
- More active development (v0.13.0 Oct 2025 vs AIF360 v0.6.1 Apr 2024)
- Simpler API for common metrics
- Better integration with scikit-learn pipeline
- AIF360 can be added later for advanced mitigation algorithms

### PostgreSQL Audit Logging

**Schema for Compliance Records (4-year retention per California):**
```sql
CREATE TABLE search_audit_log (
    id BIGSERIAL PRIMARY KEY,
    search_id UUID NOT NULL,
    tenant_id VARCHAR(50) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    query_text TEXT NOT NULL,
    query_embedding VECTOR(768),

    -- Results metadata
    total_candidates_eligible INT NOT NULL,
    candidates_returned INT NOT NULL,
    candidates_selected INT[] DEFAULT '{}',

    -- Fairness metrics (computed async)
    fairness_metrics JSONB,
    four_fifths_passed BOOLEAN,

    -- Timing
    search_latency_ms INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Retention policy
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '4 years'
);

CREATE INDEX idx_audit_tenant_date ON search_audit_log(tenant_id, created_at);
CREATE INDEX idx_audit_fairness ON search_audit_log(four_fifths_passed) WHERE four_fifths_passed = false;
```

**Audit Trigger Pattern:**
```typescript
// After search completion, async fairness audit
async function auditSearchResults(searchId: string, results: Candidate[], query: string) {
  // Queue fairness computation (don't block response)
  await pubsub.publish('fairness-audit', {
    searchId,
    candidateIds: results.map(c => c.id),
    timestamp: Date.now()
  });
}
```

### What NOT to Build:

| Anti-Pattern | Why Avoid |
|--------------|-----------|
| Real-time bias blocking | Legal gray area, may cause more harm |
| Demographic inference | Privacy risk, often inaccurate |
| Automated mitigation | Requires human oversight per regulations |
| Shadow banning flagged candidates | Discrimination risk |

**Recommended Approach:** Compute metrics for **monitoring and reporting**, not real-time blocking. Alert humans when patterns emerge.

---

## 4. Performance Optimization (Sub-500ms Target)

### Current State
- PRD target: p95 <= 1.2s (current baseline)
- New target: p95 <= 500ms (60% reduction)

### pgvectorscale for Vector Search Optimization

pgvectorscale provides **28x lower p95 latency** compared to standard pgvector for large datasets.

| Extension | Version | Purpose |
|-----------|---------|---------|
| pgvector | ^0.8.0 | Base vector operations |
| pgvectorscale | ^0.5.0 | StreamingDiskANN index, quantization |

**Installation (Cloud SQL or self-managed):**
```sql
-- Requires pgvector first
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS vectorscale CASCADE;
```

**StreamingDiskANN Index:**
```sql
-- Replace HNSW with StreamingDiskANN for better performance at scale
DROP INDEX IF EXISTS idx_candidate_embeddings_hnsw;

CREATE INDEX idx_candidate_embeddings_diskann
ON candidate_embeddings
USING diskann (embedding vector_cosine_ops)
WITH (num_neighbors = 50, search_list_size = 100);
```

**Query Optimization:**
```sql
-- Enable relaxed ordering for 2x faster queries with 95%+ quality
SET vectorscale.relaxed_order = true;

-- Combined vector + filter query
SELECT c.candidate_id, 1 - (e.embedding <=> $1) as score
FROM candidate_embeddings e
JOIN candidates c ON e.candidate_id = c.id
WHERE c.specialty = $2
  AND 1 - (e.embedding <=> $1) >= 0.45
ORDER BY e.embedding <=> $1
LIMIT 50;
```

**Source:** [pgvectorscale GitHub](https://github.com/timescale/pgvectorscale)

### Connection Pooling Optimization

**Node.js pg pool settings for low latency:**
```typescript
import { Pool } from 'pg';

const pool = new Pool({
  connectionString: process.env.POSTGRES_URL,

  // Aggressive pooling for sub-500ms
  max: 20,                    // Match expected concurrency
  min: 5,                     // Keep connections warm
  idleTimeoutMillis: 30000,   // 30s idle timeout
  connectionTimeoutMillis: 5000,  // 5s connection timeout

  // Statement caching
  statement_timeout: 10000,   // 10s max query time
});

// Pre-warm connections on startup
await Promise.all(Array(5).fill(null).map(() => pool.query('SELECT 1')));
```

### Parallel Query Execution

```typescript
// Execute retrieval stages in parallel
const [vectorResults, ftsResults, trajectoryScores] = await Promise.all([
  vectorSearch(queryEmbedding, filters),      // pgvector
  fullTextSearch(queryText, filters),          // PostgreSQL FTS
  trajectoryInference(candidateIds)            // ONNX LSTM
]);

// Fuse results with RRF
const fusedResults = reciprocalRankFusion(vectorResults, ftsResults, {
  vectorWeight: 0.65,
  textWeight: 0.35,
  k: 60
});
```

### Redis Query Caching

```typescript
// Cache search result signatures for repeated queries
const cacheKey = `search:${hash(queryEmbedding)}:${hash(filters)}`;
const cached = await redis.get(cacheKey);
if (cached) {
  return JSON.parse(cached);  // Cache hit: 1-5ms
}

// Execute search, cache for 5 minutes
const results = await executeSearch(queryEmbedding, filters);
await redis.setex(cacheKey, 300, JSON.stringify(results));
```

### Latency Budget (500ms target)

| Stage | Target | Optimization |
|-------|--------|--------------|
| Query embedding | 50ms | Gemini API (already fast) |
| Intent routing | 10ms | Semantic Router (local) |
| Vector search | 100ms | pgvectorscale DiskANN |
| FTS search | 50ms | Parallel with vector |
| RRF fusion | 10ms | In-memory computation |
| Trajectory scoring | 30ms | ONNX CPU inference |
| Signal computation | 20ms | Pre-computed during enrichment |
| LLM rerank (top-20) | 200ms | Together AI Turbo model |
| Serialization | 30ms | Buffer |
| **Total** | **500ms** | |

---

## 5. Complete Dependency Summary

### Node.js Additions

```json
{
  "dependencies": {
    "together-ai": "^0.9.0",
    "onnxruntime-node": "^1.23.2"
  }
}
```

**Installation:**
```bash
npm install together-ai@^0.9.0 onnxruntime-node@^1.23.2 --prefix services
```

### Python Additions

**requirements-v2.txt:**
```
# Trajectory prediction
torch>=2.5.0
onnx>=1.17.0
onnxruntime>=1.20.0

# NLP intent routing
semantic-router[local]>=0.1.12

# Bias/compliance
fairlearn>=0.13.0
```

**Installation:**
```bash
pip install -r requirements-v2.txt
```

### PostgreSQL Extensions

```sql
-- Verify/install extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS vectorscale CASCADE;
```

---

## 6. What NOT to Add

| Technology | Why Rejected |
|------------|--------------|
| **Elasticsearch** | No new databases constraint; pgvectorscale sufficient |
| **Pinecone/Weaviate** | No new databases constraint |
| **TensorFlow Serving** | ONNX Runtime simpler, smaller footprint |
| **AI Fairness 360 (AIF360)** | Fairlearn more actively maintained, simpler API |
| **LangChain** | Overkill for intent routing; Semantic Router lighter |
| **OpenAI embeddings** | Gemini already in stack, outperforms OpenAI |
| **Cohere Rerank** | Keep Together AI for LLM reranking (explainability) |
| **Neo4j** | No new databases; ESCO taxonomy fits in PostgreSQL |

---

## 7. Integration Points with Existing Stack

| Existing Component | Integration |
|--------------------|-------------|
| **Together AI (Qwen)** | Add JSON mode for entity extraction |
| **Gemini Embeddings** | Use for Semantic Router encoder |
| **PostgreSQL + pgvector** | Add pgvectorscale extension |
| **Redis** | Cache intent routing, search results |
| **Fastify services** | Add ONNX inference to hh-search-svc |
| **Python enrichment** | Add trajectory training, fairness metrics |

---

## 8. Confidence Assessment

| Component | Confidence | Rationale |
|-----------|------------|-----------|
| ONNX Runtime inference | HIGH | Proven in serverless, 1.23.2 stable |
| Semantic Router | MEDIUM | v0.1.12 recent, may need fallbacks |
| Together AI JSON mode | HIGH | Official docs, multiple models support |
| Fairlearn | HIGH | v0.13.0 mature, active development |
| pgvectorscale | MEDIUM | Requires Cloud SQL configuration verification |
| Sub-500ms latency | MEDIUM | Requires parallel optimization, testing |

---

## 9. Sources

### RNN/ONNX Deployment
- [ONNX Serverless Deployment (PyImageSearch)](https://pyimagesearch.com/2025/11/03/introduction-to-serverless-model-deployment-with-aws-lambda-and-onnx/)
- [PyTorch ONNX Export Tutorial](https://docs.pytorch.org/tutorials/beginner/onnx/export_simple_model_to_onnx_tutorial.html)
- [ONNX Runtime Node.js](https://www.npmjs.com/package/onnxruntime-node)

### Natural Language Search
- [Semantic Router (Aurelio Labs)](https://github.com/aurelio-labs/semantic-router)
- [Together AI Structured Outputs](https://docs.together.ai/docs/json-mode)
- [Intent Classification 2026](https://research.aimultiple.com/intent-classification/)

### Bias/Compliance
- [Fairlearn](https://fairlearn.org/)
- [AI in Hiring Compliance 2026](https://www.hrdefenseblog.com/2025/11/ai-in-hiring-emerging-legal-developments-and-compliance-guidance-for-2026/)
- [EEOC AI Initiative](https://www.eeoc.gov/newsroom/eeoc-launches-initiative-artificial-intelligence-and-algorithmic-fairness)

### Performance Optimization
- [pgvectorscale (Timescale)](https://github.com/timescale/pgvectorscale)
- [pgvector 0.8.0 on Aurora (AWS)](https://aws.amazon.com/blogs/database/supercharging-vector-search-performance-and-relevance-with-pgvector-0-8-0-on-amazon-aurora-postgresql/)
- [pgvector Performance (Crunchy Data)](https://www.crunchydata.com/blog/pgvector-performance-for-developers)

---

## 10. Next Steps for Roadmap

Based on this stack research, the recommended phase structure:

1. **Phase 1: Performance Foundation** - pgvectorscale, connection pooling, caching
2. **Phase 2: NLP Search** - Semantic Router, Together AI JSON mode
3. **Phase 3: Trajectory Prediction** - ONNX model training/deployment
4. **Phase 4: Compliance Tooling** - Fairlearn metrics, audit logging

This ordering addresses dependencies: performance must improve before adding new features that add latency.
