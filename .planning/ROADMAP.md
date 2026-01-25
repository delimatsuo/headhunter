# Roadmap: Headhunter AI v2.0 Advanced Intelligence

**Created:** 2026-01-25
**Depth:** Comprehensive
**Phases:** 15 (v1.0: 1-10, v2.0: 11-15)
**Coverage:** 26/26 v2.0 requirements mapped

---

## Overview

Build on v1.0's leader-level search foundation to add predictive trajectory modeling, natural language search, bias reduction, and compliance tooling. This milestone targets sub-500ms latency (from 1.2s baseline), RNN-based career prediction, and NYC Local Law 144 / EU AI Act compliance.

The approach remains enhancement, not replacement. All features integrate with existing infrastructure (PostgreSQL + pgvector, Redis, Together AI, Gemini embeddings, Fastify microservices).

---

## Progress

### v1.0 Leader-Level Search (Complete)

| Phase | Name | Status | Requirements |
|-------|------|--------|--------------|
| 1 | Reranking Fix | Complete | 1 |
| 2 | Search Recall Foundation | Complete | 4 |
| 3 | Hybrid Search | Complete | 4 |
| 4 | Multi-Signal Scoring Framework | Complete | 3 |
| 5 | Skills Infrastructure | Complete | 2 |
| 6 | Skills Intelligence | Complete | 3 |
| 7 | Signal Scoring Implementation | Complete | 5 |
| 8 | Career Trajectory | Complete | 4 |
| 9 | Match Transparency | Complete | 4 |
| 10 | Pipeline Integration | Complete | 4 |

**v1.0 Total:** 28 requirements across 10 phases - COMPLETE

### v2.0 Advanced Intelligence (Active)

| Phase | Name | Status | Requirements |
|-------|------|--------|--------------|
| 11 | Performance Foundation | Complete | 5 |
| 12 | Natural Language Search | Complete | 5 |
| 13 | ML Trajectory Prediction | Pending | 5 |
| 14 | Bias Reduction | Pending | 5 |
| 15 | Compliance Tooling | Pending | 6 |

**v2.0 Total:** 26 requirements across 5 phases

---

## Phase 11: Performance Foundation

**Goal:** Search achieves sub-500ms p95 latency with optimized database access and caching.

**Dependencies:** v1.0 complete (pipeline must exist before optimization)

**Plans:** 5 plans

Plans:
- [x] 11-01-PLAN.md - pgvectorscale extension and StreamingDiskANN index
- [x] 11-02-PLAN.md - Connection pool tuning and metrics
- [x] 11-03-PLAN.md - Parallel query execution
- [x] 11-04-PLAN.md - Multi-layer Redis caching strategy
- [x] 11-05-PLAN.md - Performance tracking and embedding backfill

**Status:** Code complete. Verification found 5 operational gaps (migrations not run, backfill not executed, latency unmeasured). See 11-VERIFICATION.md.

**Wave Structure:**
- Wave 1: 11-01 (pgvectorscale), 11-02 (pool tuning) - Foundation, parallel
- Wave 2: 11-03 (parallel execution), 11-04 (caching) - Depends on Wave 1
- Wave 3: 11-05 (observability, backfill) - Integration, depends on all

**Requirements:**
- PERF-01: p95 search latency under 500ms (from current 1.2s target)
- PERF-02: pgvectorscale integration for 28x latency improvement
- PERF-03: Connection pooling and parallel query execution
- PERF-04: Embedding pre-computation for entire candidate pool
- PERF-05: Redis caching strategy with scoring cache invalidation

**Success Criteria:**
1. User searches and receives results in under 500ms (p95) as measured by response time headers
2. pgvectorscale extension is enabled and StreamingDiskANN indices replace HNSW
3. Search logs show parallel execution of vector search, FTS, and trajectory scoring
4. All 23,000+ candidates have pre-computed embeddings (no on-demand embedding generation)
5. Redis cache hits for repeated searches return in under 50ms

**Latency Budget (500ms total):**
- Embedding query: 50ms
- Vector search: 100ms
- Text search: 50ms
- Scoring/filtering: 100ms
- Reranking: 200ms

**Research Needed:** Low - pgvectorscale migration is well-documented

---

## Phase 12: Natural Language Search

**Goal:** Recruiters can search using natural language queries instead of structured filters.

**Dependencies:** Phase 11 (latency budget must be established before adding NLP)

**Plans:** 6 plans

Plans:
- [x] 12-01-PLAN.md - Intent router with embedding-based classification
- [x] 12-02-PLAN.md - Entity extraction via Together AI JSON mode
- [x] 12-03-PLAN.md - Query expansion using skills ontology
- [x] 12-04-PLAN.md - Query parser orchestrator and NLP configuration
- [x] 12-05-PLAN.md - Search service NLP integration
- [x] 12-06-PLAN.md - Semantic synonyms and service initialization

**Status:** Complete. Verification passed - all 5 success criteria met. See 12-VERIFICATION.md.

**Wave Structure:**
- Wave 1: 12-01 (intent router), 12-02 (entity extractor), 12-03 (query expander) - Independent foundation modules
- Wave 2: 12-04 (query parser orchestrator) - Depends on Wave 1
- Wave 3: 12-05 (search service integration), 12-06 (semantic synonyms + startup) - Depends on Wave 2

**Requirements:**
- NLNG-01: Intent parsing extracts role, skills, location, preferences from natural language
- NLNG-02: Semantic query understanding ("Senior" matches "Lead", "Principal")
- NLNG-03: Query expansion using skills ontology ("Python dev" includes related skills)
- NLNG-04: Multi-criteria natural language queries ("Remote Python devs, 5+ years, open to startups")
- NLNG-05: Graceful fallback to structured search when NLP parsing fails

**Success Criteria:**
1. User types "senior python developer in NYC" and system extracts: role=developer, skill=Python, level=Senior, location=NYC
2. Searching "Lead engineer" returns candidates with titles "Principal", "Staff", "Senior" (semantic expansion)
3. Searching "Python dev" returns candidates with Django, Flask, FastAPI skills (ontology expansion)
4. Complex query "Remote ML engineers, 5+ years, open to startups" parses all 4 criteria correctly
5. Malformed query "asdfasdf" gracefully falls back to keyword search without error

**Technology Stack:**
- Custom semantic router lite using Gemini embeddings for intent classification (5-20ms)
- Together AI JSON mode for entity extraction (Llama 3.3-70B)
- Existing skills ontology (skills-graph.ts) for query expansion
- winkNLP for tokenization if needed

**Latency Budget Impact:**
- Intent classification: +5ms (cosine similarity)
- Entity extraction: +80-150ms (LLM call, cacheable)
- Skill expansion: +2ms (in-memory graph lookup)
- Total: +87-157ms (mitigated by caching)

**Research Needed:** Medium - validate performance on Portuguese-English mixed queries

---

## Phase 13: ML Trajectory Prediction

**Goal:** Career trajectory predictions use LSTM model instead of rule-based heuristics.

**Dependencies:** Phase 12 (NLP parsing informs trajectory context)

**Requirements:**
- TRAJ-05: Next role prediction with confidence score using LSTM model
- TRAJ-06: Tenure prediction (estimated time candidate will stay in role)
- TRAJ-07: Model confidence indicators (transparency for uncertain predictions)
- TRAJ-08: Shadow mode deployment comparing ML vs rule-based predictions
- TRAJ-09: Hireability prediction (likelihood to join company like ours)

**Success Criteria:**
1. Each candidate shows predicted next role with confidence percentage (e.g., "Senior Engineer -> Staff Engineer (78%)")
2. Tenure prediction displays estimated time in current role (e.g., "Likely to stay 18-24 months")
3. Low-confidence predictions (< 60%) display warning indicator and explanation of uncertainty
4. Shadow mode logs show side-by-side comparison of ML vs rule-based predictions for validation
5. Hireability score appears for each candidate (e.g., "High likelihood to join: startup experience, growth trajectory")

**Technology Stack:**
- PyTorch 2.5+ for LSTM training (offline)
- ONNX Runtime (onnxruntime-node ^1.23.2) for sub-50ms inference
- New service: hh-trajectory-svc on port 7109

**Research Needed:** HIGH - training data labeling strategy, LSTM vs GRU architecture choice, ONNX export patterns

**Critical Pitfalls:**
- Rule-to-ML migration must maintain baseline parity (shadow mode for 4-6 weeks)
- Sequence model mistraining (one-step lag problem) - test on career changers explicitly

---

## Phase 14: Bias Reduction

**Goal:** Search results can be anonymized and bias metrics are visible to administrators.

**Dependencies:** Phase 13 (trajectory predictions inform bias analysis)

**Requirements:**
- BIAS-01: Resume anonymization toggle (remove name, photo, school names)
- BIAS-02: Demographic-blind scoring (no demographic proxies in scoring)
- BIAS-03: Bias metrics dashboard with selection rates by group
- BIAS-04: Impact ratio calculation (four-fifths rule / 80% threshold)
- BIAS-05: Diverse slate generation to prevent homogeneous candidate pools

**Success Criteria:**
1. Recruiter can toggle "Anonymized View" and candidate cards show only skills/experience (no name, photo, school)
2. Search scoring algorithm documentation shows no demographic proxies (zip code, graduation year, school name)
3. Admin dashboard displays selection rate by demographic group with trend over time
4. Impact ratio alerts appear when any group falls below 80% of highest-selected group
5. Search results include diversity indicators ("This slate is 85% from same company tier - consider broadening")

**Technology Stack:**
- Fairlearn ^0.13.0 for bias metrics (demographic parity, equalized odds, four-fifths rule)
- Anonymization middleware in search response transformation
- Admin dashboard components in headhunter-ui

**Research Needed:** Medium - proxy variable audit, independent auditor selection for LL144

**Critical Pitfalls:**
- Anonymization proxy leakage (university name reveals demographic info)
- Compliance theater (bias audit with test data, not production data)

---

## Phase 15: Compliance Tooling

**Goal:** System meets NYC Local Law 144 and EU AI Act requirements for AI-assisted hiring.

**Dependencies:** Phase 14 (bias metrics feed into compliance reporting)

**Requirements:**
- COMP-01: Comprehensive audit logging (who searched what, when, results shown)
- COMP-02: Decision explanation storage for each ranking
- COMP-03: NYC Local Law 144 candidate notification system
- COMP-04: GDPR data subject access request (DSAR) support
- COMP-05: Data retention policy enforcement (auto-delete after period)
- COMP-06: Bias audit report generation for NYC LL144 annual requirement

**Success Criteria:**
1. Admin can view complete audit log showing: user, timestamp, query, candidates shown, candidates selected
2. Each ranking decision has stored explanation accessible via API (signal weights, scores, rationale)
3. Candidates receive automated notification within 10 days of AI-assisted decision per NYC LL144
4. Data subject can request export of all stored data about them (GDPR Article 15)
5. Candidate data older than configured retention period (default 4 years) is automatically purged
6. One-click generation of NYC LL144 bias audit report with impact ratios and methodology

**Technology Stack:**
- PostgreSQL audit schema with 4-year retention
- BigQuery export for long-term audit storage
- Notification service integration (email/in-app)
- Report generation service

**Research Needed:** Medium - independent auditor RFP, multi-jurisdiction compliance verification

**Critical Pitfalls:**
- NYC LL144 requires independent auditor, actual historical data, and action on adverse findings
- EU AI Act classifies recruitment AI as high-risk - requires human oversight in every decision
- GDPR retention vs. audit log retention conflict (resolve with anonymization after period)

---

## Dependency Graph

```
v1.0 Foundation (Phases 1-10)
    |
    v
Phase 11: Performance Foundation (latency budget)
    |
    v
Phase 12: Natural Language Search (NLP + ontology)
    |
    v
Phase 13: ML Trajectory Prediction (LSTM + shadow mode)
    |
    v
Phase 14: Bias Reduction (anonymization + metrics)
    |
    v
Phase 15: Compliance Tooling (audit + reporting)
```

All v2.0 phases are sequential. Performance must be established before adding latency-heavy ML features. Bias reduction informs compliance reporting.

---

## Timeline Estimate

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Phase 11: Performance | 4-6 weeks | 4-6 weeks |
| Phase 12: NLP Search | 3-4 weeks | 7-10 weeks |
| Phase 13: ML Trajectory | 6-8 weeks | 13-18 weeks |
| Phase 14: Bias Reduction | 4-5 weeks | 17-23 weeks |
| Phase 15: Compliance | 2-3 weeks | 19-26 weeks |

**Total v2.0 Estimate:** 19-26 weeks (5-6 months)

---

## Risk Notes

**Phase 11 (Performance):** pgvectorscale requires Cloud SQL extension enablement. Verify compatibility with existing pgvector indices before migration.

**Phase 12 (NLP Search):** Semantic Router trained on English. May need fine-tuning for Portuguese-English mixed queries common in Brazil-based recruiters.

**Phase 13 (ML Trajectory):** Training data quality unknown. May need to start with heuristic-augmented training if historical career outcomes are sparse.

**Phase 14 (Bias Reduction):** Anonymization must not leak demographic proxies. University names, zip codes, graduation years all reveal protected characteristics.

**Phase 15 (Compliance):** NYC LL144 enforcement is active ($500-$1500 fines per violation). EU AI Act takes effect February 2027 with 35M EUR fines.

---

*Roadmap created: 2026-01-25*
*Last updated: 2026-01-25 - Phase 12 complete (Natural Language Search)*
