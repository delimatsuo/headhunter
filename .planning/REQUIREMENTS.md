# Requirements: Headhunter AI Leader-Level Search

**Defined:** 2026-01-24
**Core Value:** Find candidates who are actually qualified, not just candidates who happen to have the right keywords.

## v1 Requirements

Requirements for leader-level search. Each maps to roadmap phases.

### Search Recall (Fix Current Problem)

- [ ] **SRCL-01**: Search returns 50+ candidates from 23,000+ database (not ~10)
- [ ] **SRCL-02**: Missing data treated as neutral signal (0.5 score), not exclusion
- [ ] **SRCL-03**: Broad retrieval stage fetches 500+ candidates before scoring
- [ ] **SRCL-04**: Hard specialty/function filters removed from retrieval stage

### Hybrid Search

- [ ] **HYBD-01**: Vector similarity search via pgvector for semantic matching
- [ ] **HYBD-02**: BM25 text search for exact keyword matches (rare skills, certifications)
- [ ] **HYBD-03**: Reciprocal Rank Fusion (RRF) combines vector and text results
- [ ] **HYBD-04**: Configurable RRF parameter k (default 60) for tuning

### Multi-Signal Scoring

- [ ] **SCOR-01**: Vector similarity score (0-1) as baseline signal
- [ ] **SCOR-02**: Skills exact match score (0-1) for required skills found
- [ ] **SCOR-03**: Skills inferred score (0-1) for transferable skills detected
- [ ] **SCOR-04**: Seniority alignment score (0-1) for level appropriateness
- [ ] **SCOR-05**: Recency boost score (0-1) for recent skill usage
- [ ] **SCOR-06**: Company relevance score (0-1) for industry/company fit
- [ ] **SCOR-07**: Configurable signal weights per search or role type
- [ ] **SCOR-08**: Final score as weighted combination of all signals

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
- [ ] **PIPE-05**: Fix reranking bypass (Match Score currently = Similarity Score)

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
| (populated by roadmapper) | | |

**Coverage:**
- v1 requirements: 28 total
- Mapped to phases: 0
- Unmapped: 28 (pending roadmap creation)

---
*Requirements defined: 2026-01-24*
*Last updated: 2026-01-24 after research synthesis*
