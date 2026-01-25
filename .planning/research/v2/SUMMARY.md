# Research Summary: Headhunter v2.0 Advanced Intelligence

**Project:** Headhunter AI - v2.0 Advanced Intelligence Milestone
**Research Date:** 2026-01-25
**Status:** Research Complete, Ready for Roadmap

---

## Executive Summary

Headhunter v2.0 adds RNN-based career trajectory prediction, natural language search, bias reduction, and compliance tooling to the existing leader-level search platform. Based on comprehensive research across stack, features, architecture, and pitfalls, we recommend a **targeted enhancement strategy** rather than architectural overhaul.

The core finding: **All v2.0 features can be built on existing infrastructure** (PostgreSQL + pgvector, Redis, Together AI, Gemini embeddings, Fastify services) with strategic additions. Success depends on three critical decisions: (1) maintaining baseline parity during rule-to-ML migration, (2) allocating latency budget to hit 500ms target, and (3) building compliance for both NYC Local Law 144 and EU AI Act simultaneously.

**Confidence Level:** MEDIUM-HIGH
- Stack recommendations are proven (ONNX Runtime, Semantic Router, Fairlearn)
- Feature requirements are well-documented through regulatory mandates
- Architecture patterns follow established ML serving best practices
- Pitfalls are drawn from production failures in similar domains

**Key Risk:** The tight latency budget (500ms target vs. 1.2s baseline) requires parallel execution and aggressive optimization. This constrains technology choices and demands upfront performance engineering, not post-launch optimization.

---

## Key Findings by Research Dimension

### Stack (Technology Choices)

**Core Recommendation: Minimal new dependencies, maximum leverage of existing infrastructure**

**RNN Trajectory Prediction:**
- **Training:** PyTorch 2.5.0+ (offline, not in Cloud Run)
- **Inference:** ONNX Runtime (onnxruntime-node ^1.23.2) for sub-50ms CPU inference
- **Rationale:** LSTM models capture sequential career patterns better than rules. ONNX Runtime provides portable, lightweight inference without GPU dependency or cold start penalties.

**Natural Language Search:**
- **Intent Routing:** Semantic Router ^0.1.12 (5-100ms via vector similarity, not LLM)
- **Entity Extraction:** Together AI JSON mode (meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo)
- **Rationale:** Two-tier approach balances speed and accuracy. Fast routing handles 80% of queries; complex parsing for long job descriptions.

**Bias Reduction & Compliance:**
- **Fairness Metrics:** Fairlearn ^0.13.0 (demographic parity, equalized odds, four-fifths rule)
- **Audit Logging:** PostgreSQL extension to existing schema (4-year retention per California regs)
- **Rationale:** Fairlearn is actively maintained (v0.13.0 Oct 2025) with simpler API than AIF360. SQL-based audit logs avoid adding new databases.

**Performance (Sub-500ms Target):**
- **pgvectorscale ^0.5.0:** StreamingDiskANN provides 28x lower p95 latency vs. standard pgvector
- **Connection pooling:** Aggressive pg pool settings (max: 20, min: 5, pre-warmed)
- **Parallel execution:** Vector search + FTS + trajectory scoring in Promise.all()
- **Rationale:** Cannot hit 500ms target without database-level optimization. Network I/O reduction critical.

**What NOT to Add:**
- Elasticsearch/Pinecone (violates "no new databases" constraint)
- TensorFlow Serving (ONNX Runtime simpler, smaller)
- LangChain (overkill for intent routing)
- AI Fairness 360 (Fairlearn sufficient for v2.0 scope)

**Confidence:** HIGH on core stack, MEDIUM on pgvectorscale (requires Cloud SQL configuration verification)

---

### Features (What to Build)

**Table Stakes (Must Have):**

1. **Next role prediction** - Core value prop of "predictive intelligence"
2. **Intent parsing** - Extract role/skills/location from natural language
3. **Resume anonymization toggle** - Core blind hiring capability
4. **Audit logging** - Required for NYC LL144 and EU AI Act
5. **Bias metrics dashboard** - Selection rates by demographic group
6. **Decision explanation storage** - EU AI Act transparency requirement

**Differentiators (Should Have):**

7. **Career path visualization** - Interactive timeline showing trajectory
8. **"Rising star" detection** - Find high-potential candidates early
9. **Multi-turn query refinement** - "Show me more junior ones"
10. **Real-time bias monitoring** - Alert when selection rates drift
11. **Automated compliance reporting** - One-click NYC LL144 audit reports

**Anti-Features (Explicitly NOT Build):**

- **Auto-reject candidates** - EU AI Act prohibits fully automated high-risk decisions
- **Opaque ranking algorithms** - Violates transparency requirements
- **Scraping social media without consent** - GDPR violation
- **Presenting predictions as facts** - Must show confidence intervals
- **Simple demographic parity quotas** - Legally risky; focus on fair processes

**MVP Recommendation:**

**Phase 1 (Must Have):**
- Natural language intent parsing (builds on existing embeddings)
- Audit logging infrastructure (enables all compliance features)
- Resume anonymization toggle (quick win for bias reduction)
- Basic bias metrics (selection rates, impact ratios)

**Phase 2 (Should Have):**
- Career trajectory prediction (heuristic-based first, then RNN)
- Decision explanation storage
- Candidate notification system (NYC LL144)

**Defer to Post-MVP:**
- Full RNN/Transformer trajectory model
- Multi-turn conversational search
- SHAP-based explanations
- Real-time bias monitoring

**Confidence:** HIGH - Regulatory requirements explicit; research validates technical feasibility

---

### Architecture (How to Build)

**Integration Strategy: Extend existing microservices, add one new service**

**Component 1: RNN Trajectory Model**
- **New service:** `hh-trajectory-svc` (port 7109) - TensorFlow Serving or TorchServe on Cloud Run
- **Integration:** Inline scoring in `LegacyEngine` - replace `_trajectory_score` heuristic with ML prediction
- **Latency budget:** 50-75ms (batch prediction for top 100 candidates)
- **Training data:** PostgreSQL `sourcing.candidates.intelligent_analysis.work_history`
- **Deployment:** Model-as-Service pattern with Redis caching (1hr TTL)

**Component 2: NLP Query Parsing**
- **Location:** Embedded in `hh-search-svc` (no separate service)
- **Model:** Fine-tuned DistilBERT with multi-task head (intent + entities)
- **Latency target:** <50ms (quantized model, loaded at service startup)
- **Integration:** Pre-processing before existing `JobClassificationService`
- **Fallback:** Graceful degradation to existing classification if parsing fails

**Component 3: Anonymization Layer**
- **Location:** Cloud Functions middleware (in `engine-search.ts`)
- **Pattern:** Transform results before response based on org settings
- **Levels:** NONE (admin) → PARTIAL → STANDARD → STRICT
- **Reversibility:** Hash-based pseudonyms with admin reveal flow
- **Audit:** Log every anonymization and identity reveal event

**Component 4: Compliance Audit Logging**
- **Extension:** Existing `AuditLogger` class with new event types
- **Storage:** Firestore batch writes (existing), BigQuery export (new for long-term)
- **Retention:** 90 days Firestore, 4-7 years BigQuery (regulatory requirement)
- **New events:** SEARCH_ANONYMIZED, IDENTITY_REVEALED, BIAS_FLAG_TRIGGERED, TRAJECTORY_PREDICTION

**Data Flow (Combined):**
```
Search Request
    ↓
1. Query Parsing (NLP Parser in hh-search-svc) → Extract entities
    ↓
2. Retrieval (pgvector + Firestore) → ~200-500 candidates
    ↓
3. Scoring (8 signals + ML trajectory from hh-trajectory-svc) → Parallel execution
    ↓
4. Reranking (Gemini 2-pass) → Top 50
    ↓
5. Anonymization (Middleware) → Pseudonymized results
    ↓
6. Audit Logging (ComplianceAuditLogger) → Firestore + BigQuery
    ↓
Search Response (anonymized)
```

**Suggested Build Order:**

1. **Phase 1: Foundation (Weeks 1-2)** - Audit logging + Anonymization middleware
2. **Phase 2: NLP Search (Weeks 3-4)** - Query parser training + integration
3. **Phase 3: Trajectory Model (Weeks 5-8)** - Training pipeline + hh-trajectory-svc + integration
4. **Phase 4: Testing (Weeks 9-10)** - End-to-end validation, A/B testing

**Confidence:** MEDIUM - Patterns are proven but integration complexity high. Shadow mode testing essential before production rollout.

---

### Pitfalls (What to Avoid)

**Critical Pitfalls (Cause Rewrites or Legal Issues):**

**1. Rule-to-ML Migration Without Baseline Parity**
- **Risk:** ML trajectory model performs worse on edge cases the v1.0 rules handled
- **Impact:** User trust destroyed, 3-6 months wasted, potential rollback
- **Prevention:** Document rule behavior exhaustively; ML must match 100% of documented scenarios before deployment; shadow mode for 4-6 weeks
- **Phase:** Phase 1 (ML Trajectory)

**2. Sequence Model Mistraining (One-Step Lag Problem)**
- **Risk:** LSTM learns to predict "next job = current job" due to improper unrolling
- **Impact:** Model achieves high accuracy but provides zero actual prediction value
- **Prevention:** Test on career changers explicitly; ensure sequences are 3+ jobs; compare against baseline; use scheduled sampling
- **Phase:** Phase 1 (ML Trajectory)

**3. NYC Local Law 144 Compliance Theater**
- **Risk:** Bias audit uses test data, internal auditor, or no action on adverse findings
- **Impact:** $500-$1500 fines per violation; private litigation; reputational damage
- **Prevention:** Independent auditor; actual historical data (6+ months); impact ratio tracking; 10-day notice timing automation
- **Phase:** Phase 3 (Compliance)

**4. EU AI Act High-Risk Misclassification**
- **Risk:** Assuming features aren't "high-risk" when recruitment AI is explicitly high-risk
- **Impact:** Fines up to 35M EUR or 7% global turnover; EU market ban
- **Prevention:** Document risk management NOW; build human oversight into every AI decision; per-decision logging for post-market monitoring
- **Phase:** Phase 3 (Compliance)

**Moderate Pitfalls (Cause Delays or Technical Debt):**

**5. NLP Query Parsing Brittleness**
- **Risk:** Parser fails on real queries with typos, slang, mixed PT-BR/EN
- **Prevention:** Test on production logs; graceful fallback to keyword search; confidence thresholds
- **Phase:** Phase 2 (NLP Search)

**6. Latency Budget Exhaustion**
- **Risk:** Adding ML trajectory + NLP pushes latency from 1.2s to 2-3s (vs. 500ms target)
- **Prevention:** Allocate explicit ms budgets BEFORE implementation; parallel execution; model quantization; precomputation at enrichment time
- **Phase:** Phase 4 (Performance) but design in Phases 1-2

**7. Anonymization Proxy Leakage**
- **Risk:** University name reveals race, employment gaps reveal parenting status
- **Prevention:** Proxy variable audit; disparate impact testing AFTER anonymization; fairness-aware training
- **Phase:** Phase 3 (Compliance)

**8. Training Data Drift from Production**
- **Risk:** Model trained on 2020-era careers predicts outdated paths in 2026 market
- **Prevention:** Continuous evaluation; automated retraining triggers; concept drift detection; recruiter feedback loop
- **Phase:** Phase 1 (ML Trajectory) - MLOps design

**Minor Pitfalls (Annoyances, Fixable):**

9. Career taxonomy mismatch (O*NET vs. internal categories)
10. Test data contamination (same candidates in train/test)
11. Compliance documentation rot (v1.0 docs for v2.3 system)
12. Human oversight checkbox (100% approval without review)

**Confidence:** HIGH - Pitfalls drawn from production failures, regulatory guidance, and academic research

---

## Implications for Roadmap

### Recommended Phase Structure

Based on dependencies, latency constraints, and regulatory timelines:

**Phase 1: Performance Foundation + Compliance Infrastructure (4-6 weeks)**
- **Rationale:** Must establish performance baseline and audit logging before adding latency-heavy ML features
- **Delivers:**
  - pgvectorscale migration (28x latency improvement)
  - Connection pooling optimization
  - ComplianceAuditLogger with new event types
  - PostgreSQL audit schema (4-year retention)
- **Features from FEATURES.md:** Audit logging (table stakes)
- **Pitfalls to avoid:** Latency budget exhaustion (allocate budgets now)
- **Research needed:** None - well-documented patterns

**Phase 2: Natural Language Search (3-4 weeks)**
- **Rationale:** Builds on existing embeddings; lower risk than ML trajectory; immediate user value
- **Delivers:**
  - Semantic Router intent classification
  - Together AI JSON mode entity extraction
  - Query parser integration in hh-search-svc
  - Graceful fallback to existing search
- **Features from FEATURES.md:** Intent parsing, semantic query understanding, query expansion (all table stakes)
- **Pitfalls to avoid:** NLP brittleness (test on production logs, handle PT-BR/EN)
- **Research needed:** Low - validate Semantic Router performance on PT-BR queries

**Phase 3: ML Trajectory Prediction (6-8 weeks)**
- **Rationale:** Most complex feature; requires training pipeline, new service, integration testing
- **Delivers:**
  - Training data extraction from PostgreSQL
  - LSTM model training (PyTorch → ONNX)
  - hh-trajectory-svc deployment (Cloud Run)
  - Integration with LegacyEngine scoring
  - Shadow mode A/B testing framework
- **Features from FEATURES.md:** Next role prediction, tenure prediction, progression velocity (all table stakes)
- **Pitfalls to avoid:** Rule parity regression, sequence mistraining, training drift
- **Research needed:** HIGH - `/gsd:research-phase` for training data labeling strategy, LSTM architecture tuning

**Phase 4: Bias Reduction & Compliance (4-5 weeks)**
- **Rationale:** Builds on Phase 1 audit infrastructure; addresses both NYC LL144 and EU AI Act
- **Delivers:**
  - Anonymization middleware with 4 levels
  - Fairlearn bias metrics (demographic parity, four-fifths rule)
  - NYC LL144 notification system
  - Bias metrics dashboard
  - Automated bias audit report generation
- **Features from FEATURES.md:** Resume anonymization, bias metrics, impact ratio calculation, candidate notification (all table stakes)
- **Pitfalls to avoid:** LL144 compliance theater, proxy leakage, EU misclassification
- **Research needed:** MEDIUM - independent auditor selection, GDPR retention policies

**Phase 5: Integration & Optimization (2-3 weeks)**
- **Rationale:** Final performance tuning to hit 500ms target; end-to-end testing
- **Delivers:**
  - Parallel execution optimization
  - Redis caching for trajectory + NLP results
  - Latency profiling and bottleneck elimination
  - Load testing at production scale
  - Decision explanation UI
- **Features from FEATURES.md:** Decision explanation storage (table stakes), career path visualization (differentiator)
- **Pitfalls to avoid:** Cumulative latency, cold start spikes
- **Research needed:** None - performance engineering

### Total Timeline: 19-26 weeks (5-6 months)

### Research Flags

**Phases requiring `/gsd:research-phase` during planning:**

- **Phase 3 (ML Trajectory):** Training data labeling strategy, LSTM vs. GRU architecture choice, ONNX export patterns
- **Phase 4 (Compliance):** Independent auditor RFP, multi-jurisdiction compliance engine design

**Phases with well-documented patterns (skip research):**

- **Phase 1 (Performance):** pgvectorscale migration is well-documented
- **Phase 2 (NLP Search):** Semantic Router has clear implementation guides
- **Phase 5 (Integration):** Standard performance engineering

---

## Confidence Assessment

| Research Area | Confidence Level | Evidence Quality | Gaps to Address |
|---------------|------------------|------------------|-----------------|
| **Stack** | HIGH | Official docs, npm/pypi packages, version compatibility confirmed | pgvectorscale Cloud SQL setup needs verification |
| **Features** | HIGH | Regulatory requirements explicit (NYC LL144, EU AI Act); research validates technical feasibility | SHAP/LIME bias risks need deeper investigation |
| **Architecture** | MEDIUM | Patterns proven in production ML systems; integration points clear | Shadow mode A/B testing framework design needed |
| **Pitfalls** | HIGH | Drawn from production failures, regulatory guidance, academic research | Specific PT-BR/EN query brittleness needs validation |

**Overall Confidence: MEDIUM-HIGH**

### Key Gaps Identified

1. **pgvectorscale Configuration:** Cloud SQL requires extension enablement; verify compatibility with existing pgvector indices
2. **Training Data Quality:** Historical career outcomes may be sparse; synthetic data generation strategy needed
3. **PT-BR Language Support:** Semantic Router trained on English; may need fine-tuning for Portuguese-English mixed queries
4. **Independent Auditor Selection:** NYC LL144 requires independence; need RFP process and vendor vetting
5. **EU Geographical Scope:** Confirm whether "Ella recruiters" or candidates are EU-based; triggers extraterritorial compliance

These gaps are **addressable during roadmap execution** and do not block initial planning.

---

## Sources

### Stack Research
- [ONNX Serverless Deployment (PyImageSearch)](https://pyimagesearch.com/2025/11/03/introduction-to-serverless-model-deployment-with-aws-lambda-and-onnx/)
- [Semantic Router (Aurelio Labs)](https://github.com/aurelio-labs/semantic-router)
- [Together AI Structured Outputs](https://docs.together.ai/docs/json-mode)
- [Fairlearn](https://fairlearn.org/)
- [pgvectorscale (Timescale)](https://github.com/timescale/pgvectorscale)

### Feature Research
- [NYC Local Law 144 Official](https://www.nyc.gov/site/dca/about/automated-employment-decision-tools.page)
- [EU AI Act Framework](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai)
- [AI in Hiring Compliance 2026](https://www.hrdefenseblog.com/2025/11/ai-in-hiring-emerging-legal-developments-and-compliance-guidance-for-2026/)
- [CAREER Foundation Model](https://arxiv.org/pdf/2202.08370)
- [Resume2Vec for ATS](https://www.mdpi.com/2079-9292/14/4/794)

### Architecture Research
- [NEMO: Next Career Move Prediction](http://team-net-work.org/pdfs/LiJTYHC_WWW17.pdf)
- [Intent Classification 2026](https://research.aimultiple.com/intent-classification/)
- [Model Serving Patterns](https://www.anyscale.com/blog/serving-ml-models-in-production-common-patterns)
- [AI Bias Reduction in Recruitment](https://www.tandfonline.com/doi/full/10.1080/09585192.2025.2480617)

### Pitfalls Research
- [Frontiers - Career Path Prediction Evaluation](https://www.frontiersin.org/journals/big-data/articles/10.3389/fdata.2025.1564521/full)
- [NYC Comptroller LL144 Audit](https://www.osc.ny.gov/state-agencies/audits/2025/12/02/enforcement-local-law-144-automated-employment-decision-tools)
- [MIT Sloan - AI Hiring Bias](https://mitsloan.mit.edu/ideas-made-to-matter/ai-reinventing-hiring-same-old-biases-heres-how-to-avoid-trap)
- [Google Cloud ML Serving Latency](https://cloud.google.com/architecture/minimizing-predictive-serving-latency-in-machine-learning)
- [Folio3 MLOps Best Practices](https://cloud.folio3.com/blog/mlops-best-practices/)

---

## Ready for Requirements Definition

**Status:** SYNTHESIS COMPLETE

This research synthesis provides sufficient foundation for the roadmapper to:
1. Structure v2.0 into 5 executable phases
2. Allocate features to appropriate phases based on dependencies
3. Identify critical risks requiring mitigation strategies
4. Flag phases needing deeper research during execution
5. Set realistic timelines (19-26 weeks total)

**Next Steps:**
1. Roadmapper creates phase-by-phase implementation roadmap
2. Requirements definition for Phase 1 (Performance Foundation + Compliance Infrastructure)
3. Technical design for pgvectorscale migration
4. Independent auditor RFP preparation (parallel to Phase 1-2)

**Critical Path Items:**
- pgvectorscale Cloud SQL configuration (blocks Phase 1)
- Training data labeling strategy (blocks Phase 3)
- Independent auditor engagement (blocks Phase 4 compliance)

**Approval Required:**
- Latency target confirmation (500ms vs. 1.2s baseline - significant optimization required)
- EU AI Act applicability assessment (determines Phase 4 scope)
- Training data quality review (determines Phase 3 approach: heuristic-first vs. ML-first)
