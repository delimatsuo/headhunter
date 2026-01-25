# Roadmap: Headhunter AI Leader-Level Search

**Created:** 2026-01-24
**Depth:** Comprehensive
**Phases:** 10
**Coverage:** 28/28 v1 requirements mapped

---

## Overview

Transform Headhunter from keyword-based search returning ~10 candidates to leader-level semantic search returning 50+ qualified candidates from 23,000+ profiles. This roadmap implements multi-signal scoring, skills intelligence, career trajectory analysis, and transparent match explanations through a 3-stage retrieval pipeline.

The approach is enhancement, not replacement. The existing stack (PostgreSQL + pgvector, Redis, Together AI, Gemini embeddings, Fastify microservices) is already aligned with industry best practices.

---

## Progress

| Phase | Name | Status | Requirements |
|-------|------|--------|--------------|
| 1 | Reranking Fix | Complete | 1 |
| 2 | Search Recall Foundation | Complete | 4 |
| 3 | Hybrid Search | Complete | 4 |
| 4 | Multi-Signal Scoring Framework | Complete | 3 |
| 5 | Skills Infrastructure | Complete | 2 |
| 6 | Skills Intelligence | Complete | 3 |
| 7 | Signal Scoring Implementation | Pending | 5 |
| 8 | Career Trajectory | Pending | 4 |
| 9 | Match Transparency | Pending | 4 |
| 10 | Pipeline Integration | Pending | 4 |

**Total:** 28 requirements across 10 phases

---

## Phase 1: Reranking Fix

**Goal:** LLM reranking actually influences final match scores instead of being bypassed.

**Dependencies:** None (critical bugfix, must be first)

**Plans:** 4 plans in 3 waves

Plans:
- [x] 01-01-PLAN.md — Preserve raw vector similarity in backend (Wave 1)
- [x] 01-02-PLAN.md — Fix frontend API score extraction (Wave 2)
- [x] 01-03-PLAN.md — Display both scores in UI (Wave 2)
- [x] 01-04-PLAN.md — CSS styling and verification checkpoint (Wave 3)

**Requirements:**
- PIPE-05: Fix reranking bypass (Match Score currently = Similarity Score)

**Success Criteria:**
1. Match Score differs from raw Similarity Score for at least 90% of results
2. LLM reranking response is logged and verified in search results
3. Candidates with strong qualitative fit (good rationale) rank higher than weak keyword matches
4. Rerank latency remains under 500ms per batch

**Rationale:** Research identified this as a critical bug. Reranking bypass means all the sophisticated LLM analysis is discarded. Nothing else matters until this works.

---

## Phase 2: Search Recall Foundation

**Goal:** Search returns 50+ candidates instead of ~10 by converting exclusionary filters to soft scoring signals.

**Dependencies:** Phase 1 (reranking must work before increasing recall)

**Plans:** 5 plans in 3 waves

Plans:
- [x] 02-01-PLAN.md — Lower similarity thresholds for broad retrieval (Wave 1)
- [x] 02-02-PLAN.md — Convert level filter to scoring signal (Wave 1)
- [x] 02-03-PLAN.md — Convert specialty filter to scoring signal (Wave 1)
- [x] 02-04-PLAN.md — Convert remaining filters to scoring (Wave 2)
- [x] 02-05-PLAN.md — Integrate scores and add stage logging (Wave 3, checkpoint)

**Requirements:**
- SRCL-01: Search returns 50+ candidates from 23,000+ database (not ~10)
- SRCL-02: Missing data treated as neutral signal (0.5 score), not exclusion
- SRCL-03: Broad retrieval stage fetches 500+ candidates before scoring
- SRCL-04: Hard specialty/function filters removed from retrieval stage

**Success Criteria:**
1. User searches for "Python developer" and receives 50+ results (not ~10)
2. Candidates with missing specialty data appear in results with neutral scoring
3. Search query log shows 500+ candidates retrieved before scoring stage
4. No hard WHERE clauses for specialty, function, or optional profile fields in retrieval SQL
5. Candidates with incomplete profiles appear in results (ranked lower, not excluded)

**Rationale:** The fundamental problem is exclusion. Harvard research shows hard filters exclude 10M+ qualified candidates. Fix the filter cascade before adding features.

---

## Phase 3: Hybrid Search

**Goal:** Search uses both semantic understanding AND exact keyword matching for better recall.

**Dependencies:** Phase 2 (need broad retrieval working first)

**Plans:** 4 plans in 2 waves

Plans:
- [x] 03-01-PLAN.md — Fix textScore=0 and add FTS diagnostic logging (Wave 1)
- [x] 03-02-PLAN.md — Add RRF configuration parameters (Wave 1)
- [x] 03-03-PLAN.md — Implement RRF fusion SQL and update types (Wave 2)
- [x] 03-04-PLAN.md — Add summary logging and verification checkpoint (Wave 2)

**Requirements:**
- HYBD-01: Vector similarity search via pgvector for semantic matching
- HYBD-02: BM25 text search for exact keyword matches (rare skills, certifications)
- HYBD-03: Reciprocal Rank Fusion (RRF) combines vector and text results
- HYBD-04: Configurable RRF parameter k (default 60) for tuning

**Success Criteria:**
1. Searching for "K8s" returns candidates with "Kubernetes" in their profiles (semantic match)
2. Searching for "AWS Solutions Architect" returns candidates with exact certification (BM25 match)
3. Search results combine candidates found by vector OR text search (union, not intersection)
4. Admin can configure RRF k parameter without code changes (env var or config)

**Rationale:** Pure vector search misses exact keyword matches. Pure text search misses semantic relationships. RRF fusion is proven, pure SQL, zero new dependencies.

---

## Phase 4: Multi-Signal Scoring Framework

**Goal:** Scoring infrastructure exists to compute weighted combinations of signals.

**Dependencies:** Phase 3 (need hybrid search results to score)

**Plans:** 5 plans in 4 waves

Plans:
- [x] 04-01-PLAN.md — Create SignalWeightConfig types and role-type presets (Wave 1)
- [x] 04-02-PLAN.md — Extend search types and create scoring utilities (Wave 2)
- [x] 04-03-PLAN.md — Integrate signal scoring into SearchService (Wave 3)
- [x] 04-04-PLAN.md — Wire API layer and module exports (Wave 3)
- [x] 04-05-PLAN.md — Verification checkpoint (Wave 4)

**Requirements:**
- SCOR-01: Vector similarity score (0-1) as baseline signal
- SCOR-07: Configurable signal weights per search or role type
- SCOR-08: Final score as weighted combination of all signals

**Success Criteria:**
1. Each candidate result includes a vector_similarity_score field (0-1 normalized)
2. Search request can include custom signal weights (e.g., `{ skills: 0.3, trajectory: 0.4 }`)
3. Final match score is computed as weighted sum: `sum(signal * weight) / sum(weights)`
4. Default weights are applied when no custom weights specified
5. Signal weights can be configured per role type (IC vs Manager vs Executive)

**Rationale:** Build the framework before populating signals. The weighted combination pattern applies to all signals we'll add in subsequent phases.

---

## Phase 5: Skills Infrastructure

**Goal:** EllaAI skills taxonomy is available for search with synonym normalization.

**Dependencies:** Phase 4 (scoring framework to integrate skills signals)

**Plans:** 4 plans in 3 waves

Plans:
- [x] 05-01-PLAN.md — Copy skills-master.ts and create skills-service wrapper (Wave 1)
- [x] 05-02-PLAN.md — Refactor vector-search.ts to use skills-service (Wave 2)
- [x] 05-03-PLAN.md — Refactor skill-aware-search.ts to use skills-service (Wave 2)
- [x] 05-04-PLAN.md — Verification checkpoint (Wave 3)

**Requirements:**
- SKIL-01: EllaAI skills taxonomy (200+ skills) integrated into search
- SKIL-03: Skill synonym/alias normalization ("JS" = "JavaScript", "K8s" = "Kubernetes")

**Success Criteria:**
1. skills-master.ts from EllaAI exists in functions/src/shared/ (copied, not linked)
2. Searching for "JS" normalizes to "JavaScript" before matching
3. Skill lookup by alias returns canonical skill ID
4. Skill taxonomy is accessible from search service without external API call

**Rationale:** Skills intelligence requires the taxonomy foundation. Copy the file locally for customization and independence from EllaAI repo.

---

## Phase 6: Skills Intelligence

**Goal:** Search finds candidates with related and inferred skills, not just exact matches.

**Dependencies:** Phase 5 (taxonomy must be integrated)

**Plans:** 4 plans in 3 waves

Plans:
- [x] 06-01-PLAN.md — Create skills-graph.ts with BFS expansion (Wave 1)
- [x] 06-02-PLAN.md — Create skills-inference.ts with title patterns (Wave 1)
- [x] 06-03-PLAN.md — Integrate skill expansion into search (Wave 2)
- [x] 06-04-PLAN.md — Verification checkpoint (Wave 3)

**Requirements:**
- SKIL-02: Related skills expansion ("Python" matches "Django", "Flask" users)
- SKIL-04: Skills inference from context (patterns in profile data)
- SKIL-05: Transferable skills surfaced with confidence levels

**Success Criteria:**
1. Searching for "Python" returns candidates who have "Django" or "Flask" (related skills)
2. Related skills are flagged with relationship type (e.g., "related", "transferable")
3. Skills inference detects implied skills from job titles (e.g., "Full Stack" implies JS + backend)
4. Inferred skills include confidence score (0-1)
5. Transferable skills (e.g., "Java" -> "Kotlin" pivot potential) appear with explanation

**Rationale:** Skills inference during indexing, not search time, avoids latency. Related skills expand the candidate pool meaningfully.

---

## Phase 7: Signal Scoring Implementation

**Goal:** All 8 scoring signals are computed and contribute to final match score.

**Dependencies:** Phase 6 (skills signals require skills infrastructure)

**Plans:** 5 plans in 4 waves

Plans:
- [ ] 07-01-PLAN.md — Create signal-calculators.ts with skill matching functions (Wave 1)
- [ ] 07-02-PLAN.md — Add seniority, recency, and company calculators (Wave 1)
- [ ] 07-03-PLAN.md — Extend types and weight presets (Wave 2)
- [ ] 07-04-PLAN.md — Integrate signals into scoring and search service (Wave 3)
- [ ] 07-05-PLAN.md — Verification checkpoint (Wave 4)

**Requirements:**
- SCOR-02: Skills exact match score (0-1) for required skills found
- SCOR-03: Skills inferred score (0-1) for transferable skills detected
- SCOR-04: Seniority alignment score (0-1) for level appropriateness
- SCOR-05: Recency boost score (0-1) for recent skill usage
- SCOR-06: Company relevance score (0-1) for industry/company fit

**Success Criteria:**
1. Candidate results include skills_exact_score reflecting % of required skills matched
2. Candidate results include skills_inferred_score for transferable skills detected
3. Searching for "Senior" returns Senior/Staff candidates ranked higher than Junior
4. Candidates who used a skill recently (last 2 years) rank higher than those who used it 5+ years ago
5. Candidates from relevant industries/companies (fintech for fintech role) rank higher

**Rationale:** These are the signals that differentiate leader-level search from keyword matching. Each signal is 0-1 normalized for consistent weighting.

---

## Phase 8: Career Trajectory

**Goal:** Career direction and velocity inform candidate ranking.

**Dependencies:** Phase 7 (trajectory is a signal in the scoring framework)

**Requirements:**
- TRAJ-01: Career direction computed from title sequence analysis
- TRAJ-02: Career velocity computed (fast/normal/slow progression)
- TRAJ-03: Trajectory fit score for role alignment
- TRAJ-04: Trajectory type classification (technical, leadership, lateral, pivot)

**Success Criteria:**
1. Each candidate has computed trajectory_direction (upward, lateral, downward)
2. Each candidate has computed trajectory_velocity (fast: <2yr/promo, normal: 2-4yr, slow: >4yr)
3. Manager role search ranks candidates with leadership trajectory higher
4. Trajectory type classification appears in candidate data (technical_growth, leadership_track, lateral_move, career_pivot)
5. Trajectory fit score (0-1) reflects alignment between candidate trajectory and role direction

**Rationale:** Career trajectory is the key differentiator for leader-level search. Rule-based computation is explainable and sufficient per research.

---

## Phase 9: Match Transparency

**Goal:** Recruiters understand why each candidate matched and how they scored.

**Dependencies:** Phase 8 (need all signals computed to display)

**Requirements:**
- TRNS-01: Match score visible to recruiters for each candidate
- TRNS-02: Component scores shown (skills, trajectory, seniority, etc.)
- TRNS-03: LLM-generated match rationale for top candidates
- TRNS-04: Inferred skills displayed with confidence indicators

**Success Criteria:**
1. Search results UI shows overall match score (0-100) for each candidate
2. Expandable score breakdown shows individual signal scores (skills: 0.8, trajectory: 0.9, etc.)
3. Top 10 candidates have LLM-generated "Why this candidate matches" rationale
4. Inferred skills appear with confidence badge (High: >0.8, Medium: 0.5-0.8, Low: <0.5)
5. Recruiters can sort/filter by individual signal scores

**Rationale:** Transparency is both a regulatory requirement (NYC/EU) and a usability feature. Recruiters need to understand and trust the ranking.

---

## Phase 10: Pipeline Integration

**Goal:** Complete 3-stage pipeline operates end-to-end with proper stage handoffs.

**Dependencies:** Phase 9 (all components must work before integration)

**Requirements:**
- PIPE-01: 3-stage pipeline: retrieval (500+) -> scoring (top 100) -> reranking (top 50)
- PIPE-02: Retrieval focuses on recall (don't miss candidates)
- PIPE-03: Scoring focuses on precision (rank best higher)
- PIPE-04: Reranking via LLM for nuance and context

**Success Criteria:**
1. Search logs show clear stage transitions: retrieval count, scoring count, final count
2. Retrieval stage returns 500+ candidates for typical queries (recall-focused)
3. Scoring stage reduces to top 100 using signal weights (precision-focused)
4. Reranking stage uses LLM to produce final top 50 with nuanced ordering
5. End-to-end search latency remains under p95 1.2s target

**Rationale:** This phase validates the entire system works together. Each stage has clear responsibility and the handoffs are logged for debugging.

---

## Dependency Graph

```
Phase 1: Reranking Fix
    |
    v
Phase 2: Search Recall Foundation
    |
    v
Phase 3: Hybrid Search
    |
    v
Phase 4: Multi-Signal Scoring Framework
    |
    v
Phase 5: Skills Infrastructure
    |
    v
Phase 6: Skills Intelligence
    |
    v
Phase 7: Signal Scoring Implementation
    |
    v
Phase 8: Career Trajectory
    |
    v
Phase 9: Match Transparency
    |
    v
Phase 10: Pipeline Integration
```

All phases are sequential. Each builds on the previous. No parallel execution paths.

---

## Risk Notes

**Phase 3 (Hybrid Search):** BM25 implementation in PostgreSQL may require pg_trgm or ts_rank. Verify extension availability.

**Phase 5 (Skills Infrastructure):** EllaAI skills-master.ts must be copied, not linked. Verify file location and format.

**Phase 8 (Career Trajectory):** Rule-based velocity computation requires consistent date formatting in profile data.

**Phase 10 (Pipeline Integration):** p95 1.2s latency target may require optimization if earlier phases add overhead.

---

*Roadmap created: 2026-01-24*
*Last updated: 2026-01-25 after Phase 6 completion*
