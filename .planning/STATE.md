# Project State: Headhunter AI v2.0 Advanced Intelligence

**Initialized:** 2026-01-24
**Current Status:** Phase 14 IN PROGRESS - Bias Reduction (Plan 03 Complete)

---

## Project Reference

**Core Value:** Find candidates who are actually qualified, not just candidates who happen to have the right keywords.

**Current Focus:** v2.0 Advanced Intelligence - Performance optimization, NLP search, ML trajectory, bias reduction, compliance tooling.

**Key Files:**
- `.planning/PROJECT.md` - Project definition and constraints
- `.planning/REQUIREMENTS.md` - All requirements with traceability
- `.planning/ROADMAP.md` - Phase structure and success criteria
- `.planning/MILESTONES.md` - Archived v1.0 milestone
- `.planning/research/v2/SUMMARY.md` - v2.0 research findings

---

## Current Position

**Milestone:** v2.0 Advanced Intelligence
**Phase:** 14 - Bias Reduction (IN PROGRESS)
**Plan:** 3 of 6 executed
**Status:** Completed 14-03-PLAN.md (Fairlearn bias metrics worker)
**Last activity:** 2026-01-26 - Completed 14-03-PLAN.md (BIAS-03/BIAS-04 metrics)

**Progress:** [##########] v1.0 100% | [######----] v2.0: 3/5 phases (60%)

**Next Action:** Execute 14-04-PLAN.md (Admin dashboard)

---

## v2.0 Phase Progress

| Phase | Name | Status | Requirements | Progress |
|-------|------|--------|--------------|----------|
| 11 | Performance Foundation | Complete | 5 | 100% |
| 12 | Natural Language Search | Complete | 5 | 100% |
| 13 | ML Trajectory Prediction | Complete | 5 | 100% |
| 14 | Bias Reduction | In Progress | 5 | 50% (3/6 plans) |
| 15 | Compliance Tooling | Pending | 6 | 0% |

**Overall v2.0:** 3/5 phases complete (60%)

---

## v1.0 Phase Progress (Archived)

| Phase | Name | Status | Plans | Progress |
|-------|------|--------|-------|----------|
| 1 | Reranking Fix | Complete | 4/4 | 100% |
| 2 | Search Recall Foundation | Complete | 5/5 | 100% |
| 3 | Hybrid Search | Complete | 4/4 | 100% |
| 4 | Multi-Signal Scoring Framework | Complete | 5/5 | 100% |
| 5 | Skills Infrastructure | Complete | 4/4 | 100% |
| 6 | Skills Intelligence | Complete | 4/4 | 100% |
| 7 | Signal Scoring Implementation | Complete | 5/5 | 100% |
| 8 | Career Trajectory | Complete | 4/4 | 100% |
| 9 | Match Transparency | Complete | 7/7 | 100% |
| 10 | Pipeline Integration | Complete | 4/4 | 100% |

**v1.0 Total:** 10/10 phases complete (100%) - MILESTONE COMPLETE

---

## Performance Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| v1 Requirements | 28 | 28 done | Complete |
| v2 Requirements | 26 | 10 done | In Progress |
| p95 Latency | <500ms (v2) | ~1.2s (v1) | Phase 11 target |
| Search Recall | 50+ candidates | Achieved | Verified |
| Cache Hit Rate | >0.98 | Unknown | Unmeasured |
| NLP Tests | 100+ | 153 passing | Phase 12 complete |

---

## Accumulated Context

### Key Decisions (v2.0)

| Decision | Rationale | Phase |
|----------|-----------|-------|
| Performance before features | Latency budget must be established before adding NLP/ML overhead | 11 |
| pgvectorscale over Pinecone | Stay on existing PostgreSQL, 28x improvement documented | 11 |
| Side-by-side HNSW + DiskANN indices | Feature flag enables A/B testing; instant rollback if issues | 11 |
| Default to HNSW, opt-in to DiskANN | HNSW proven stable; DiskANN requires Cloud SQL compatibility verification | 11 |
| Runtime tunable search_list_size | Allows recall/latency tradeoff without redeployment | 11 |
| poolMax=20, poolMin=5 | Cloud Run concurrency + warm connections for sub-500ms p95 | 11 |
| Parallel pool warmup | Minimize cold-start latency with Promise.all connection acquisition | 11 |
| Multi-layer cache with TTL jitter | 4 layers (search/rerank/specialty/embedding) with ±20% jitter to prevent cache stampede | 11 |
| Cache layer TTLs by staleness tolerance | Search 10min, Rerank 6hr, Specialty 24hr based on data volatility | 11 |
| Semantic Router for NLP | 5-100ms vector-based routing, not LLM-based parsing | 12 |
| Confidence threshold 0.6 default | Balances precision vs recall for intent classification | 12 |
| Portuguese utterances in routes | Brazilian recruiter market support | 12 |
| 150ms extraction timeout | Per RESEARCH.md latency budget, fallback to empty on timeout | 12 |
| Post-extraction hallucination filter | Validate skills against query text instead of relying on LLM | 12 |
| Bidirectional abbreviation matching | Support js->JavaScript and JavaScript->js lookups | 12 |
| Copy skills ontology to services workspace | Enables direct imports without cross-workspace path issues | 12 |
| Default confidence threshold 0.8 for expansion | Balance between recall and precision for skill expansion | 12 |
| Weight 0.6x for expanded skills | Explicit skills dominate scoring; expanded skills boost recall | 12 |
| In-memory extraction cache (5-min TTL) | LLM calls expensive (~100ms); cache avoids repeat calls for same query | 12 |
| SHA256-based cache keys | Fast, deterministic, case-insensitive after lowercase normalization | 12 |
| Include higher seniority levels | "Lead" should match "Senior", "Staff", "Principal" candidates | 12 |
| Background NLP initialization | Non-blocking, Cloud Run fast startup, NLP ready before first search | 12 |
| NLP health endpoint | Report NLP status for observability and debugging | 12 |
| ONNX Runtime for inference | Sub-50ms CPU inference, no GPU dependency, portable | 13 |
| Shadow mode for ML transition | 4-6 weeks side-by-side to validate ML matches rule-based baseline | 13 |
| Fairlearn for bias metrics | Actively maintained, simpler API than AIF360 | 14 |
| PostgreSQL for audit logs | No new databases, 4-year retention in existing infrastructure | 15 |
| Disable auth and rate-limit temporarily | Focus on core functionality first, enable after Plan 02 ONNX integration | 13 |
| Use stub responses in predict endpoint | Actual ONNX inference deferred to Plan 02 | 13 |
| ONNX session singleton pattern | Prevent repeated model loading (expensive ~100ms+) across requests | 13 |
| Linear interpolation for calibration | Matches scikit-learn IsotonicRegression without Python dependency | 13 |
| Confidence threshold 0.6 for ML predictions | Balance precision vs recall for uncertainty flagging | 13 |
| Background predictor initialization | Cloud Run fast startup, setImmediate() non-blocking model load | 13 |
| 100ms timeout for ML predictions | Must not impact overall search latency budget (<500ms p95) | 13 |
| Circuit breaker after 3 failures | Prevents cascade failures when hh-trajectory-svc unavailable, 30s cooldown | 13 |
| Batch predictions for top 50 candidates | Balance ML coverage vs efficiency - most users focus on top results | 13 |
| Shadow mode for ML scoring | ML predictions returned for UI but don't affect ranking; enables safe A/B comparison | 13 |
| 30-second health check interval | Detects hh-trajectory-svc recovery, updates observability status | 13 |
| Confidence color thresholds (UI) | Green >=80%, Yellow 60-79%, Red <60% for visual distinction | 13 |
| Hireability three-tier labels | High >=0.7, Moderate >=0.4, Lower <0.4 for recruiter guidance | 13 |
| ML predictions in expanded card | Avoid clutter in collapsed view, keep related to career trajectory section | 13 |
| No HIGH-risk proxies in scoring | Verified absence of location, graduationYear, educationInstitutions | 14 |
| companyPedigree as MEDIUM risk | Keep in scoring with 12% cap, prior experience at scale is job-related | 14 |
| yearsExperience filter-only | Used for filtering not scoring, correlates with job seniority requirements | 14 |

### Key Decisions (v1.0 - Archived)

| Decision | Rationale | Phase |
|----------|-----------|-------|
| Fix reranking first | Critical bug: Match Score = Similarity Score (bypass active) | 1 |
| Sequential phases | Each phase builds on previous; no parallel paths | All |
| Copy skills taxonomy | Local copy for customization, independence from EllaAI | 5 |
| Rule-based trajectory | Explainable, sufficient per research; ML deferred to v2 | 8 |
| 3-stage pipeline | Retrieval (500) -> Scoring (100) -> Rerank (50) | 10 |

### Technical Notes

**v2.0 Infrastructure Additions:**
- hh-trajectory-svc on port 7109 (new service for ML trajectory)
- pgvectorscale extension (replaces HNSW with StreamingDiskANN)
- BigQuery export for long-term audit storage

**Phase 12 Deliverables (COMPLETE):**
- IntentRouter class with semantic routing (NLNG-01) - 19 tests
- EntityExtractor class with Together AI JSON mode (NLNG-02) - 33 tests
- QueryExpander class with skills ontology expansion (NLNG-03) - 23 tests
- QueryParser class orchestrating all NLP components (NLNG-04) - 25 tests
- SemanticSynonyms module for seniority/role expansion (NLNG-05) - 44 tests
- SearchService NLP integration with semantic filters
- QueryParser initialization at service startup
- NLP health endpoint reporting
- NLP types: IntentType, IntentRoute, ParsedQuery, ExtractedEntities, NLPConfig
- Vector utilities: cosineSimilarity, averageEmbeddings
- Skills ontology (200+ skills) in services workspace
- NLP barrel export at `src/nlp/index.ts`
- NLPSearchConfig added to config.ts with environment variables
- **153 passing unit tests total**

**Phase 13 Deliverables (IN PROGRESS - 5/7 plans):**
- hh-trajectory-svc Fastify server (port 7109) with health and predict endpoints
- TypeScript types: TrajectoryPrediction, PredictRequest, PredictResponse, ShadowLog, HealthResponse
- Service configuration with environment variable parsing
- Python ML training pipeline: data prep, LSTM model, ONNX export, calibration, evaluation
- ONNX session singleton with optimized config (CPU, graph optimization, 4 threads)
- Input encoder with title normalization (abbreviations, lowercase, punctuation)
- Isotonic regression calibrator via linear interpolation
- TrajectoryPredictor orchestrating inference, encoding, and calibration
- /predict endpoint using ML inference with calibrated confidence
- /predict/health endpoint for predictor status
- Uncertainty reason generation for low confidence predictions
- Background initialization with setImmediate for non-blocking startup
- Graceful shutdown with ONNX session disposal
- Multi-stage Dockerfile following service mesh patterns
- Shadow mode infrastructure with comparison logging
- GET /shadow/stats endpoint (promotion criteria: >85% direction, >80% velocity, >1000 comparisons)
- Batch logging with 60-second auto-flush
- MLTrajectoryClient in hh-search-svc with circuit breaker
- ML predictions enriching search results (top 50 candidates)
- Shadow mode comparison logging (ML vs rule-based)
- Health endpoint reporting ML trajectory availability

**v1.0 Deliverables:**
- 3-stage pipeline with 500/100/50 funnel
- Hybrid search (vector + BM25 via RRF)
- 8-signal weighted scoring framework
- 468-skill taxonomy with inference and transferability
- Career trajectory (direction, velocity, fit)
- Match transparency (breakdown, chips, rationale)

### Blockers

None currently identified.

### TODOs

**v2.0:**
- [x] Plan Phase 11 (Performance Foundation) - 5 plans created
- [x] Execute 11-01-PLAN.md (pgvectorscale + StreamingDiskANN)
- [x] Execute 11-02-PLAN.md (Connection pool tuning)
- [x] Execute 11-03-PLAN.md (Parallel query execution)
- [x] Execute 11-04-PLAN.md (Multi-layer Redis caching)
- [x] Execute 11-05-PLAN.md (Performance tracking + backfill)
- [x] Plan Phase 12 (Natural Language Search) - 6 plans created
- [x] Execute 12-01-PLAN.md (Semantic Router Lite)
- [x] Execute 12-02-PLAN.md (Entity Extraction)
- [x] Execute 12-03-PLAN.md (Query Expansion)
- [x] Execute 12-04-PLAN.md (Query Parser Orchestrator)
- [x] Execute 12-05-PLAN.md (SearchService Integration)
- [x] Execute 12-06-PLAN.md (NLP Integration & Semantic Synonyms)
- [x] Plan Phase 13 (ML Trajectory Prediction) - 7 plans created
- [x] Execute 13-01-PLAN.md (hh-trajectory-svc scaffolding)
- [x] Execute 13-02-PLAN.md (Python ML training pipeline)
- [x] Execute 13-03-PLAN.md (ONNX inference integration)
- [x] Execute 13-04-PLAN.md (Shadow mode infrastructure)
- [x] Execute 13-05-PLAN.md (TrajectoryClient with circuit breaker)
- [x] Execute 13-06-PLAN.md (ML trajectory UI components)
- [x] Execute 13-07-PLAN.md (Test suite and verification)
- [ ] Verify pgvectorscale Cloud SQL compatibility
- [ ] Run embedding backfill in production after Cloud SQL migration
- [ ] Prepare training data for trajectory LSTM (Phase 13 blocker)
- [ ] Identify independent auditor for NYC LL144 (Phase 15 blocker)

**v1.0 (deferred):**
- [ ] Verify search recall improvement in production
- [ ] Measure actual p95 latency baseline

---

## Session Continuity

**Last session:** 2026-01-26
**Stopped at:** Completed 14-03-PLAN.md (Fairlearn bias metrics worker)
**Resume file:** None

**Phase 13 COMPLETE (All 7 Plans):**

All 7 plans executed successfully across 4 waves:

**Plan 01 (Wave 1):** hh-trajectory-svc Scaffolding
- 3 tasks, 3 commits (4aaf03e, 411c9ee, 642e7a5)
- Service on port 7109 with health and predict routes

**Plan 02 (Wave 2):** ML Training Pipeline
- 4 tasks, 4 commits (c186da5, d3740b9, b6a34c4, 896dca7)
- Python LSTM training with ONNX export and calibration

**Plan 03 (Wave 2):** ONNX Inference Engine
- 3 tasks, 3 commits (896dca7, 603ee3f, 2c3aa7a)
- TrajectoryPredictor with ONNX Runtime integration

**Plan 04 (Wave 2):** Shadow Mode Infrastructure
- 3 tasks, 3 commits (f470a18, bffd1b6, be39ca3)
- Comparison logging with promotion readiness tracking

**Plan 05 (Wave 3):** TrajectoryClient with Circuit Breaker
- 3 tasks, 3 commits (c3f6314, 1e0e747, 7b1c8d2)
- HTTP client for hh-trajectory-svc with Opossum circuit breaker

**Plan 06 (Wave 3):** ML Trajectory UI Components
- 3 tasks, 3 commits (b9a0b8b, 5f0fcfd, 745cf56)
- React components for displaying ML predictions on candidate cards

**Plan 07 (Wave 4):** Test Suite and Verification
- 3 tasks, 4 commits (c8165f3, 0c6d687, 23ce319, 5168421)
- 39 passing tests (29 trajectory-svc + 10 ML client)
- Docker Compose integration
- Comprehensive verification document (13-VERIFICATION.md)

**Phase 13 Key Deliverables:**
- hh-trajectory-svc service fully functional on port 7109
- ONNX Runtime integration with LSTM model
- Shadow mode for ML vs rule-based validation
- GET /shadow/stats endpoint (promotion criteria: >85% direction, >80% velocity, >1000 comparisons)
- Batch logging with 60-second auto-flush
- TrajectoryClient with circuit breaker (100ms timeout, 4-failure threshold)
- ConfidenceIndicator React component with green/yellow/red badges
- TrajectoryPrediction component displaying next role, tenure, hireability
- Candidate card integration in expanded details section
- Comprehensive test suite (100% passing)
- Docker Compose configuration with hh-trajectory-svc
- Requirement verification document

**Deviations:**
- None - all 7 plans executed as written

**Production Blockers:**
- Train ONNX model with real data (mock model path currently)
- Re-enable authentication (temporarily disabled)
- Configure shadow mode storage (switch from memory to PostgreSQL/BigQuery)

**Phase 12 VERIFIED COMPLETE:**

All 6 plans executed successfully:

- 12-01: Semantic Router Lite (IntentRouter)
- 12-02: Entity Extraction (EntityExtractor)
- 12-03: Query Expansion (QueryExpander)
- 12-04: Query Parser Orchestrator (QueryParser)
- 12-05: SearchService Integration (NLP filters, semantic expansion)
- 12-06: NLP Integration & Semantic Synonyms (startup init, health endpoint)

**Phase 12 Plan 06 Commits:**
- `d6ee8f1`: feat(12-06): add semantic synonyms expansion module
- `554a429`: feat(12-06): wire up QueryParser initialization at startup
- `bf2e8c5`: feat(12-06): integrate semantic synonyms into NLP pipeline

**Key Deliverables:**
- Semantic synonyms for seniority (10 levels) and roles
- Portuguese language support
- QueryParser initialized at service startup (background, non-blocking)
- NLP health status in /health endpoint
- 153 total NLP tests passing

**Phase 12 Success Criteria MET:**
1. Natural language queries parsed into structured search parameters - YES
2. Intent classification in <20ms (semantic router) - YES
3. Entity extraction with >90% accuracy on test set - YES
4. Skill expansion using ontology graph - YES
5. Fallback to keyword search when confidence low - YES
6. Semantic seniority expansion ("Lead" -> Senior, Staff, Principal) - YES

**Ready for Phase 13:** ML Trajectory Prediction

---

v2.0 Roadmap complete. 5 phases defined with 26 requirements mapped:

| Phase | Name | Requirements | Research Needed |
|-------|------|--------------|-----------------|
| 11 | Performance Foundation | PERF-01 to PERF-05 | Low |
| 12 | Natural Language Search | NLNG-01 to NLNG-05 | Medium |
| 13 | ML Trajectory Prediction | TRAJ-05 to TRAJ-09 | HIGH |
| 14 | Bias Reduction | BIAS-01 to BIAS-05 | Medium |
| 15 | Compliance Tooling | COMP-01 to COMP-06 | Medium |

**Phase 13 Prerequisites:**
- NLP infrastructure provides structured entities for ML features
- Seniority/role expansion enables better candidate matching
- Performance baseline established with 144 passing tests

---

**Phase 14 IN PROGRESS (3/6 Plans):**

**Plan 01 (Wave 1):** Resume Anonymization Toggle (BIAS-01)
- Anonymization types: AnonymizationConfig, AnonymizedCandidate, AnonymizedSearchResponse
- anonymizeCandidate() and anonymizeSearchResponse() functions
- Match reason filtering for company/school/location mentions
- API integration: `anonymizedView` param on /v1/search/hybrid
- 30 unit tests (514 lines)
- Commits: b93dcc5, 344ba5b, ecd2b4d

**Plan 02 (Wave 1):** Demographic-Blind Scoring (BIAS-02)
- Proxy variable audit completed
- Slate diversity analysis module
- analyzeSlateDiversity() function with entropy-based scoring
- 30 unit tests
- Commits: (see 14-02-SUMMARY.md)

**Plan 03 (Wave 2):** Fairlearn Bias Metrics Worker (BIAS-03/BIAS-04)
- Database migration 013_bias_tables.sql
- Selection event logging module with dimension inference
- Fairlearn-based bias_metrics_worker.py (366 lines)
- Four-fifths rule impact ratio calculation
- Chi-square and Fisher's exact significance tests
- 23 unit tests
- Commits: 5842bdf, 893ad7c, 13f3837, 8468752

**Phase 14 Key Progress:**
- BIAS-01: Resume anonymization toggle COMPLETE
- BIAS-02: Demographic-blind scoring COMPLETE
- BIAS-03: Selection event logging COMPLETE
- BIAS-04: Bias metrics computation COMPLETE
- Ready for: BIAS-05 (Admin dashboard)

---

*State initialized: 2026-01-24*
*Last updated: 2026-01-26 - Phase 14 Plan 03 Complete (BIAS-03/BIAS-04 Metrics)*
