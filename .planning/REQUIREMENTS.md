# Requirements: Headhunter AI Leader-Level Search

**Defined:** 2026-01-24
**Core Value:** Find candidates who are actually qualified, not just candidates who happen to have the right keywords.

## v1 Requirements

Requirements for leader-level search. Each maps to roadmap phases.

### Search Recall (Fix Current Problem)

- [x] **SRCL-01**: Search returns 50+ candidates from 23,000+ database (not ~10)
- [x] **SRCL-02**: Missing data treated as neutral signal (0.5 score), not exclusion
- [x] **SRCL-03**: Broad retrieval stage fetches 500+ candidates before scoring
- [x] **SRCL-04**: Hard specialty/function filters removed from retrieval stage

### Hybrid Search

- [x] **HYBD-01**: Vector similarity search via pgvector for semantic matching
- [x] **HYBD-02**: BM25 text search for exact keyword matches (rare skills, certifications)
- [x] **HYBD-03**: Reciprocal Rank Fusion (RRF) combines vector and text results
- [x] **HYBD-04**: Configurable RRF parameter k (default 60) for tuning

### Multi-Signal Scoring

- [x] **SCOR-01**: Vector similarity score (0-1) as baseline signal
- [ ] **SCOR-02**: Skills exact match score (0-1) for required skills found
- [ ] **SCOR-03**: Skills inferred score (0-1) for transferable skills detected
- [ ] **SCOR-04**: Seniority alignment score (0-1) for level appropriateness
- [ ] **SCOR-05**: Recency boost score (0-1) for recent skill usage
- [ ] **SCOR-06**: Company relevance score (0-1) for industry/company fit
- [x] **SCOR-07**: Configurable signal weights per search or role type
- [x] **SCOR-08**: Final score as weighted combination of all signals

### Skills Intelligence

- [ ] **SKIL-01**: EllaAI skills taxonomy (200+ skills) integrated into search
- [ ] **SKIL-02**: Related skills expansion ("Python" matches "Django", "Flask" users)
- [ ] **SKIL-03**: Skill synonym/alias normalization ("JS" = "JavaScript", "K8s" = "Kubernetes")
- [ ] **SKIL-04**: Skills inference from context (patterns in profile data)
- [ ] **SKIL-05**: Transferable skills surfaced with confidence levels

### Career Trajectory

- [ ] **TRAJ-01**: Career direction computed from title sequence analysis
- [ ] **TRAJ-02**: Career velocity computed (fast/normal/slow progression)
- [ ] **TRAJ-03**: Trajectory fit score for role alignment
- [ ] **TRAJ-04**: Trajectory type classification (technical, leadership, lateral, pivot)

### Match Transparency

- [ ] **TRNS-01**: Match score visible to recruiters for each candidate
- [ ] **TRNS-02**: Component scores shown (skills, trajectory, seniority, etc.)
- [ ] **TRNS-03**: LLM-generated match rationale for top candidates
- [ ] **TRNS-04**: Inferred skills displayed with confidence indicators

### Search Pipeline

- [ ] **PIPE-01**: 3-stage pipeline: retrieval (500+) -> scoring (top 100) -> reranking (top 50)
- [ ] **PIPE-02**: Retrieval focuses on recall (don't miss candidates)
- [ ] **PIPE-03**: Scoring focuses on precision (rank best higher)
- [ ] **PIPE-04**: Reranking via LLM for nuance and context
- [x] **PIPE-05**: Fix reranking bypass (Match Score currently = Similarity Score)

## v2 Requirements

Deferred to future release. Valuable but not in current scope.

### Advanced Trajectory

- **TRAJ-05**: RNN-based next-title prediction ("Support Engineer -> QA -> Backend -> ?")
- **TRAJ-06**: Hireability prediction (will they join a company like ours?)
- **TRAJ-07**: Success signal detection from career patterns

### Natural Language Interface

- **NLNG-01**: Recruiters can search using natural language ("Find senior Python developers in NYC open to fintech")
- **NLNG-02**: Query auto-classification into structured search parameters

### Diversity & Bias

- **DIVS-01**: Anonymization mode for bias reduction
- **DIVS-02**: Diversity indicators in search results
- **DIVS-03**: Bias audit tooling for compliance (NYC Local Law 144, EU AI Act)

### Performance Optimization

- **PERF-01**: p95 latency under 500ms for search (vs current 1.2s target)
- **PERF-02**: Embedding pre-computation for entire candidate pool
- **PERF-03**: Real-time scoring cache invalidation

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Hard keyword filters | Anti-pattern: Excludes 10M+ qualified candidates (Harvard study) |
| Full automation of decisions | Legal risk: Human-in-the-loop required |
| Opaque scoring | Regulatory risk: NYC/EU require transparency |
| Agentic AI (autonomous outreach) | Different product category, requires outreach integration |
| Relationship/network intelligence | Requires social graph data we don't have |
| Multi-channel sourcing (GitHub, etc.) | Focus on existing 23,000 candidates first |
| Real-time market intelligence | Requires additional data sources |
| Internal mobility matching | Different use case than external sourcing |
| Mobile native app | Web-first approach |
| Real-time chat | Different product focus |
| ATS/application tracking | This is search/discovery, not applicant tracking |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PIPE-05 | Phase 1: Reranking Fix | Complete |
| SRCL-01 | Phase 2: Search Recall Foundation | Complete |
| SRCL-02 | Phase 2: Search Recall Foundation | Complete |
| SRCL-03 | Phase 2: Search Recall Foundation | Complete |
| SRCL-04 | Phase 2: Search Recall Foundation | Complete |
| HYBD-01 | Phase 3: Hybrid Search | Complete |
| HYBD-02 | Phase 3: Hybrid Search | Complete |
| HYBD-03 | Phase 3: Hybrid Search | Complete |
| HYBD-04 | Phase 3: Hybrid Search | Complete |
| SCOR-01 | Phase 4: Multi-Signal Scoring Framework | Complete |
| SCOR-07 | Phase 4: Multi-Signal Scoring Framework | Complete |
| SCOR-08 | Phase 4: Multi-Signal Scoring Framework | Complete |
| SKIL-01 | Phase 5: Skills Infrastructure | Pending |
| SKIL-03 | Phase 5: Skills Infrastructure | Pending |
| SKIL-02 | Phase 6: Skills Intelligence | Pending |
| SKIL-04 | Phase 6: Skills Intelligence | Pending |
| SKIL-05 | Phase 6: Skills Intelligence | Pending |
| SCOR-02 | Phase 7: Signal Scoring Implementation | Pending |
| SCOR-03 | Phase 7: Signal Scoring Implementation | Pending |
| SCOR-04 | Phase 7: Signal Scoring Implementation | Pending |
| SCOR-05 | Phase 7: Signal Scoring Implementation | Pending |
| SCOR-06 | Phase 7: Signal Scoring Implementation | Pending |
| TRAJ-01 | Phase 8: Career Trajectory | Pending |
| TRAJ-02 | Phase 8: Career Trajectory | Pending |
| TRAJ-03 | Phase 8: Career Trajectory | Pending |
| TRAJ-04 | Phase 8: Career Trajectory | Pending |
| TRNS-01 | Phase 9: Match Transparency | Pending |
| TRNS-02 | Phase 9: Match Transparency | Pending |
| TRNS-03 | Phase 9: Match Transparency | Pending |
| TRNS-04 | Phase 9: Match Transparency | Pending |
| PIPE-01 | Phase 10: Pipeline Integration | Pending |
| PIPE-02 | Phase 10: Pipeline Integration | Pending |
| PIPE-03 | Phase 10: Pipeline Integration | Pending |
| PIPE-04 | Phase 10: Pipeline Integration | Pending |

**Coverage:**
- v1 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0

---
*Requirements defined: 2026-01-24*
*Last updated: 2026-01-24 after Phase 4 completion*
