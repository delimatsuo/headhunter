# Domain Pitfalls: AI-Powered Talent Search

**Domain:** AI-powered candidate search and multi-signal scoring
**Researched:** 2026-01-24
**Confidence:** HIGH (based on industry failures, academic research, and current codebase issues)

---

## Critical Pitfalls

Mistakes that cause rewrites, major failures, or fundamentally broken systems.

---

### Pitfall 1: Filter-First Architecture (The 90% Exclusion Problem)

**What goes wrong:** Hard filters cascade exclusions, eliminating candidates before scoring even happens. A search for "Backend Engineer, Brazil, 5+ years" excludes candidates with missing specialty data, missing location, or missing experience fields — even if they're perfect matches semantically.

**Why it happens:**
- Filters are easier to implement than scoring
- SQL WHERE clauses feel "correct" and deterministic
- Teams optimize for precision over recall without measuring trade-offs
- Missing data is treated as "didn't meet criteria" instead of "unknown"

**Consequences:**
- 90%+ of candidates excluded from consideration
- Best candidates with incomplete profiles never surface
- Search returns only candidates with perfect data hygiene
- Users lose trust when obviously qualified candidates don't appear

**YOUR CURRENT CODEBASE EXAMPLE:**
From `SEARCH_INVESTIGATION_HANDOFF.md`: "Frontend engineers appearing in Backend searches" and "Product Managers, Directors, Data Analysts in engineering searches" — but also specialty filtering excludes candidates with `specialties = '{}' OR specialties IS NULL`, which is a band-aid that lets everyone through when specialty data is missing.

**Prevention:**
- **Scoring-first architecture:** Replace WHERE clauses with score penalties
- **Neutral handling for missing data:** Score of 0.5 (neutral), not exclusion
- **Multi-stage retrieval:** Broad recall first (vector similarity), then scoring, then reranking
- **Measure recall AND precision:** Track "qualified candidates excluded" as a metric

**Detection:**
- Compare total candidates vs. candidates returned (if <10% returned, filters too aggressive)
- A/B test filter removal — if removing filters improves user satisfaction, filters were wrong
- Review excluded candidates manually — are any actually qualified?

**Phase to address:** Phase 1 (Foundation) — this is architectural, not incremental

**Industry evidence:**
- [Harvard Business School study](https://www.technologyreview.com/2021/06/23/1026825/linkedin-ai-bias-ziprecruiter-monster-artificial-intelligence/): 88% of employers agree ATS systems vet out qualified candidates
- [Medium article on hiring flaws](https://medium.com/junior-economist/the-hidden-cost-of-missing-data-how-flawed-analytics-shape-hiring-decisions-376091afb091): Career gaps and non-traditional backgrounds overlooked due to missing data

---

### Pitfall 2: Reranking Bypass / Silent Failures

**What goes wrong:** The AI reranking layer exists in code but isn't actually called, returns unchanged scores, or silently fails — and no one notices because the system still "works" (returns results).

**Why it happens:**
- Conditional logic gates reranking (if missing JD, if candidates < threshold, etc.)
- Error handling catches exceptions and returns base results
- No visibility into whether reranking actually ran
- Match Score displayed from same field as Similarity Score

**Consequences:**
- Users think they have AI-powered search when they have keyword matching
- Development effort wasted on features that don't execute
- False confidence in system capabilities
- No competitive differentiation from basic search

**YOUR CURRENT CODEBASE EXAMPLE:**
From `SEARCH_INVESTIGATION_HANDOFF.md`: "Match Score = Similarity Score for ALL 50 candidates" and "Gemini reranking is not being called" or "returning unchanged scores."

**Prevention:**
- **Observability:** Log when reranking runs, skips, or fails — make this a first-class metric
- **Mandatory reranking:** If reranking is critical, don't make it optional with fallback
- **Score divergence checks:** Alert if Match Score == Similarity Score for >90% of results
- **Separate score fields:** Never conflate pre-rerank and post-rerank scores in the same field

**Detection:**
- Compare pre-rerank vs. post-rerank scores — should be different
- Monitor rerank_invocation_rate and rerank_success_rate as metrics
- Add integration tests that verify reranking changes result order

**Phase to address:** Phase 1 (Foundation) — observability is foundational

**Industry evidence:**
- [Gene Dai's Medium article](https://genedai.medium.com/implementing-ai-in-recruitment-what-five-years-of-failures-taught-me-37c239804aaa): "The implementation failures vastly outnumber the successes. And the failures follow predictable patterns."

---

### Pitfall 3: Skills Inference Overconfidence

**What goes wrong:** AI infers skills that candidates don't actually have, then ranks them highly for roles requiring those skills. "Worked at Google" doesn't mean "knows distributed systems." "Used Excel" doesn't mean "data analysis expert."

**Why it happens:**
- LLMs confidently infer skills from weak signals
- Training data encodes correlation (Google employees often know distributed systems) as causation
- No validation mechanism for inferred skills
- Inferred skills treated with same weight as stated skills

**Consequences:**
- False positives — candidates ranked highly for skills they lack
- Recruiter frustration when "top matches" can't answer basic questions
- Bias perpetuation — inference based on company/school pedigree
- Legal risk if inference creates proxy discrimination

**Prevention:**
- **Confidence scores for inferred skills:** Never treat inference as certain (0.6-0.8 max)
- **"Needs verification" tags:** Flag inferred skills visibly in UI
- **Evidence requirements:** Inference requires supporting evidence (e.g., "inferred Python from GitHub activity")
- **Differential weighting:** Stated skills weight 1.0, inferred skills weight 0.5-0.7
- **Human-in-the-loop validation:** Allow recruiters to confirm/reject inferences

**Detection:**
- Track "recruiter rejected candidate" rate for high-inference candidates
- Compare inference accuracy against interview outcomes
- A/B test inference on/off — measure quality of hire

**Phase to address:** Phase 2 (Skills Inference) — this IS the skills inference phase, so build verification in from start

**Industry evidence:**
- [Eightfold AI review](https://www.testgorilla.com/blog/eightfold-ai-review/): "The AI sometimes infers candidates' skills, which can lead to erroneous matches"
- [Fuel50 skills assessment](https://fuel50.com/2025/06/skills-assessment-platforms/): "Eightfold's skills data is largely machine-inferred. It lacks the nuance and validation that comes from direct skill assessment."

---

### Pitfall 4: Training Data Bias Perpetuation

**What goes wrong:** The model learns historical patterns that encode bias. "Senior engineers typically are male" becomes "rank male candidates higher for senior roles." "Top performers came from Stanford" becomes "downgrade state school graduates."

**Why it happens:**
- Historical hiring data reflects past biases
- Optimization for "hire probability" encodes what managers historically preferred
- Proxy features (company names, school names) correlate with protected characteristics
- Aggregate patterns applied to individual candidates

**Consequences:**
- Systematic discrimination against protected groups
- Legal liability (see Amazon lawsuit, iTutorGroup EEOC case)
- Narrow candidate pools that mirror existing workforce
- Loss of diverse talent pipelines

**YOUR PROJECT RISK:**
Career trajectory prediction based on historical patterns may encode biases like "women leave for caregiving" or "older workers have shorter expected tenure."

**Prevention:**
- **Audit for bias before deployment:** Test ranking across demographic groups
- **Avoid protected proxies:** Don't use features that correlate with protected characteristics
- **Fairness constraints:** Enforce demographic parity or equal opportunity in ranking
- **Regular bias testing:** Not one-time — continuous monitoring
- **Explainability requirements:** If you can't explain why a candidate ranked low, don't rank them low

**Detection:**
- Statistical parity testing across gender, age, ethnicity
- Adverse impact analysis (4/5ths rule)
- Review "downgraded" candidates manually for patterns

**Phase to address:** ALL phases — bias prevention is not a feature, it's a constraint

**Industry evidence:**
- [Amazon AI recruiting tool](https://www.shrm.org/topics-tools/news/hr-trends/recruitment-is-broken): Penalized resumes containing "women's" (women's chess club, women's college)
- [LinkedIn bias discovery](https://www.technologyreview.com/2021/06/23/1026825/linkedin-ai-bias-ziprecruiter-monster-artificial-intelligence/): Algorithm detected behavioral patterns that disadvantaged women who only applied to roles matching their qualifications
- [HireVue speech recognition](https://mitsloan.mit.edu/ideas-made-to-matter/ai-reinventing-hiring-same-old-biases-heres-how-to-avoid-trap): Disadvantaged non-white and deaf applicants
- [iTutorGroup EEOC case](https://www.goco.io/blog/common-ai-recruitment-pitfalls-to-avoid): AI automatically rejected female applicants 55+ and male applicants 60+

---

### Pitfall 5: Semantic Search "Vocabulary Mismatch"

**What goes wrong:** Vector embeddings don't understand domain vocabulary. "Senior Backend Engineer" and "Staff Platform Engineer" are far apart in embedding space despite being similar roles. "Node.js" and "Express" are distant despite being used together.

**Why it happens:**
- General-purpose embedding models trained on broad corpora
- Technical jargon and role titles have domain-specific meanings
- Synonyms and aliases not mapped ("JS" vs "JavaScript" vs "ECMAScript")
- Job titles vary wildly across companies for same role

**Consequences:**
- Qualified candidates missed because of terminology differences
- Over-reliance on exact keyword matching
- Semantic search provides no improvement over BM25
- "Cold start" problem — new terminology not understood

**Prevention:**
- **Skills ontology with aliases:** Map synonyms explicitly ("JS" -> "JavaScript")
- **Fine-tuned embeddings:** Train on recruitment-specific corpus
- **Hybrid search:** Combine vector similarity with BM25/keyword matching
- **Query expansion:** Add synonyms and related terms to search query
- **Domain-specific preprocessing:** Normalize job titles to standard taxonomy

**Detection:**
- Test with synonym queries — should return same results
- Compare vector search vs. keyword search — if same results, embeddings adding no value
- User feedback on "obviously missing" candidates

**Phase to address:** Phase 1 (Foundation) for hybrid search, Phase 2 (Skills) for ontology

**Industry evidence:**
- [SOO Group semantic matching](https://thesoogroup.com/blog/semantic-talent-matching-vector-search): "Traditional systems have significant limitations including vocabulary mismatch, context insensitivity, and synonym blindness"
- [Microsoft Azure relevance docs](https://learn.microsoft.com/en-us/azure/search/search-relevance-overview): "Most of the dissatisfaction cases in relevance are due to term mismatch between queries and documents"

---

## Moderate Pitfalls

Mistakes that cause delays, technical debt, or degraded quality — but don't require full rewrites.

---

### Pitfall 6: Score Calibration Drift

**What goes wrong:** Multi-signal scores become uncalibrated over time. "0.8 match score" means different things for different queries, candidate pools, or time periods. Users can't trust the scores.

**Why it happens:**
- Scores are relative to current candidate pool
- Weights tuned on one dataset don't generalize
- No ongoing calibration against outcomes
- Different scoring algorithms produce incompatible ranges

**Consequences:**
- Inconsistent user experience
- Difficulty setting thresholds ("only show >0.7 matches")
- A/B testing invalidated by score drift
- Technical debt from ad-hoc score adjustments

**Prevention:**
- **Normalize scores to consistent range:** Always 0-1 with known distribution
- **Calibrate against outcomes:** Track which scores lead to good hires
- **Monitor score distributions:** Alert on drift from baseline
- **Document score meaning:** "0.8 means 80% likelihood of interview request"

**Detection:**
- Track score distribution over time
- Compare user actions (interview requests) against scores
- Run calibration tests monthly

**Phase to address:** Phase 1 (Foundation) — establish calibration from start

---

### Pitfall 7: Recall vs. Precision Imbalance

**What goes wrong:** Optimizing for one metric destroys the other. Removing all filters improves recall to 100% but precision to 0% (everyone is a "match"). Tight filters give 100% precision but 1% recall (only perfect matches).

**Why it happens:**
- Teams optimize for the metric they measure
- "Just remove the filters" feels like a quick fix
- No clear definition of acceptable precision/recall trade-off
- Different stakeholders want different trade-offs

**YOUR CURRENT CODEBASE NOTE:**
From PROJECT.md: "We already made the 'lazy' mistake of just removing filters without improving quality."

**Consequences:**
- Users overwhelmed with irrelevant results (low precision)
- OR users see too few results (low recall)
- Oscillating between extremes with each "fix"
- No stable equilibrium

**Prevention:**
- **Define acceptable trade-off:** e.g., "70% precision at 50% recall"
- **Measure both metrics:** Track precision AND recall, not just result count
- **Stage the pipeline:** High recall first, then precision-improving reranking
- **User feedback loop:** Let users rate relevance, feed back into tuning

**Detection:**
- Measure precision via user actions (interviews, hires)
- Measure recall via "missed candidate" reports
- Track F1 score or similar combined metric

**Phase to address:** Phase 1 (Foundation) — define metrics before building

**Industry evidence:**
- [Wikipedia precision/recall](https://en.wikipedia.org/wiki/Precision_and_recall): Classic trade-off documented extensively
- [Vector search recall](https://opensourceconnections.com/blog/2025/02/27/vector-search-navigating-recall-and-performance/): "Post-filtering can lead to very low recall values when the filters become more restrictive"

---

### Pitfall 8: Career Trajectory Overfitting

**What goes wrong:** Trajectory models learn patterns that don't generalize. "Fast promotions in 2015-2020" doesn't predict success in 2026 market. Model fits historical careers but fails on non-traditional paths.

**Why it happens:**
- Limited training data (company's own hiring history)
- Career patterns are non-stationary (change over time)
- Non-linear careers penalized (freelancers, founders, career changers)
- Model memorizes specific patterns instead of learning principles

**Consequences:**
- Biased against career changers and non-traditional backgrounds
- Model accuracy degrades over time
- False confidence in trajectory predictions
- Rejection of candidates who would succeed

**Prevention:**
- **Use trajectory as signal, not filter:** Score penalty, not exclusion
- **Recency weighting:** Recent trajectory matters more than 10-year-old patterns
- **Handle non-linear paths:** Explicit handling for gaps, pivots, freelance
- **Regular retraining:** Update model as market and careers evolve
- **Outcome validation:** Track whether trajectory predictions correlate with actual success

**Detection:**
- Track prediction accuracy over time (should stay stable)
- Audit candidates with non-traditional paths — are they unfairly penalized?
- Compare predictions to actual hire outcomes

**Phase to address:** Phase 3 (Career Trajectory) — build validation into the feature

**Industry evidence:**
- [Frontiers career prediction research](https://www.frontiersin.org/journals/big-data/articles/10.3389/fdata.2025.1564521/full): "Effective career path prediction (CPP) modeling faces challenges including highly variable career trajectories, free-text resume data, and limited publicly available benchmark datasets"

---

### Pitfall 9: LLM Hallucination in Reranking

**What goes wrong:** LLM reranking hallucinates skills, experience, or qualifications that aren't in the candidate profile. "This candidate has extensive AWS experience" when the profile doesn't mention AWS.

**Why it happens:**
- LLMs optimize for plausible text, not factual accuracy
- Prompt engineering insufficient to constrain output
- No verification step after LLM response
- LLMs associate contexts (e.g., "worked at Amazon" -> "knows AWS")

**Consequences:**
- Candidates ranked highly for hallucinated qualifications
- "Why they're a match" reasons don't match reality
- User trust erodes when rationale is wrong
- Legal risk if decisions based on false information

**Prevention:**
- **Constrained output schemas:** Require LLM to cite specific profile sections
- **Verification step:** Cross-check LLM claims against actual profile data
- **Grounded prompting:** Include full candidate profile in context, require citations
- **Confidence thresholds:** Reject responses where LLM confidence is low
- **Human review for high-stakes:** Recruiters verify AI rationale before acting

**Detection:**
- Audit "match reasons" against actual profiles — flag mismatches
- Track hallucination rate as metric
- User reports of incorrect match reasons

**Phase to address:** All phases using LLM — especially reranking in Phase 1

**Industry evidence:**
- [OpenAI hallucination research](https://openai.com/index/why-language-models-hallucinate/): "Language models hallucinate because standard training and evaluation procedures reward guessing over acknowledging uncertainty"
- [Databricks testing](https://www.zeroentropy.dev/articles/ultimate-guide-to-choosing-the-best-reranking-model-in-2025): "Reranked results reduce LLM hallucinations by 35% compared to raw embedding similarity" — but still 65% of hallucinations remain

---

### Pitfall 10: Missing Data Death Spiral

**What goes wrong:** System requires complete data to function. Incomplete profiles excluded from search. Users don't improve profiles because they're not being shown. Profile quality never improves.

**Why it happens:**
- Engineers assume data will be complete
- Missing fields handled with exclusion, not neutral scoring
- No incentive for candidates/recruiters to complete profiles
- System optimizes for existing complete profiles

**Consequences:**
- Shrinking effective candidate pool
- Best candidates (passive, employed) have sparse profiles
- Active candidates over-represented (survivorship bias)
- Database full of data that's never used

**Prevention:**
- **Neutral scoring for missing data:** 0.5 score, not 0 or exclusion
- **Partial match surfacing:** "Lower confidence, needs more information"
- **Data enrichment pipelines:** Automatically fill missing data where possible
- **Profile completeness incentives:** Show recruiters what data would help

**Detection:**
- Track % of database actually searchable
- Monitor profile completeness trends
- A/B test neutral vs. exclusionary handling

**Phase to address:** Phase 1 (Foundation) — handling missing data is architectural

**Industry evidence:**
- [Clay AI scoring errors](https://community.clay.com/x/support/v7nd22or1yah/handling-ai-scoring-errors-due-to-empty-candidate): "Some fields for some candidates may be empty, which can cause errors"
- [Research on missing data in hiring](https://medium.com/junior-economist/the-hidden-cost-of-missing-data-how-flawed-analytics-shape-hiring-decisions-376091afb091): "78% of resumes contain misleading information, with 46% including actual fabrications" — but also missing data causes exclusion of qualified candidates

---

## Minor Pitfalls

Mistakes that cause annoyance or small quality degradation but are easily fixable.

---

### Pitfall 11: Query Expansion Gone Wrong

**What goes wrong:** Synonym expansion adds irrelevant terms. "Python" expands to include "python snake" or "Monty Python." "React" expands to "chemical reaction."

**Prevention:**
- Domain-specific synonym dictionaries
- Context-aware expansion (programming context vs. other)
- Limit expansion to high-confidence synonyms

**Phase to address:** Phase 2 (Skills) with skills ontology

---

### Pitfall 12: Embedding Dimension Mismatch

**What goes wrong:** Query embeddings and candidate embeddings generated by different models have incompatible dimensions or semantics. 768-dim vectors compared to 1536-dim vectors.

**Prevention:**
- Single embedding model for all embeddings
- Verify embedding provider consistency at query time
- Migration plan when changing embedding models

**Phase to address:** Phase 1 (Foundation) — ensure consistency

---

### Pitfall 13: Latency Budget Exceeded

**What goes wrong:** Multi-stage pipeline (embed -> retrieve -> score -> rerank) takes 5+ seconds. Users abandon search.

**Prevention:**
- Latency budget per stage (embed: 200ms, retrieve: 300ms, rerank: 500ms)
- Caching at each stage
- Async loading / progressive display
- Limit candidate pool for reranking

**Phase to address:** Phase 1 (Foundation) — build performance into architecture

---

### Pitfall 14: Rank Inflation Over Time

**What goes wrong:** As database grows, scores drift. A "0.9 match" in a 1,000-candidate pool means different things in a 100,000-candidate pool.

**Prevention:**
- Percentile-based scoring instead of absolute
- Regular score recalibration
- Document score semantics

**Phase to address:** Phase 1 (Foundation) — establish calibration approach

---

## Phase-Specific Warnings

| Phase | Likely Pitfall | Mitigation |
|-------|---------------|------------|
| Phase 1: Foundation | Reranking bypass (Pitfall 2) | Observability-first; log every rerank decision |
| Phase 1: Foundation | Filter-first exclusion (Pitfall 1) | Scoring-first architecture from day 1 |
| Phase 1: Foundation | Score calibration (Pitfall 6) | Define score semantics before implementing |
| Phase 2: Skills Inference | Overconfidence (Pitfall 3) | Confidence scores + verification tags |
| Phase 2: Skills Inference | Vocabulary mismatch (Pitfall 5) | Skills ontology with aliases |
| Phase 3: Trajectory | Overfitting (Pitfall 8) | Outcome validation; non-linear path handling |
| Phase 3: Trajectory | Bias perpetuation (Pitfall 4) | Fairness testing before deployment |
| All Phases | LLM hallucination (Pitfall 9) | Grounded prompting; verification step |
| All Phases | Missing data spiral (Pitfall 10) | Neutral scoring; never exclude for missing data |

---

## Your Codebase's Current Pitfall Status

Based on `SEARCH_INVESTIGATION_HANDOFF.md`:

| Pitfall | Current Status | Severity |
|---------|---------------|----------|
| Reranking bypass (2) | ACTIVE - Match Score = Similarity Score | CRITICAL |
| Filter architecture (1) | PARTIAL - Filters exist but may not execute | HIGH |
| Specialty data gaps (10) | ACTIVE - Specialty filter includes NULL/empty | MEDIUM |
| Score calibration (6) | UNKNOWN - No evidence of calibration | MEDIUM |
| Observability | MISSING - No visibility into what runs | HIGH |

**Recommended immediate actions:**
1. Add logging to every decision point (rerank called/skipped, filter applied/skipped)
2. Create integration tests that verify reranking changes scores
3. Audit specialty data completeness in database
4. Establish baseline metrics before building new features

---

## Sources

### Industry Failures and Case Studies
- [SHRM: Recruitment Is Broken](https://www.shrm.org/topics-tools/news/hr-trends/recruitment-is-broken)
- [MIT Sloan: AI Hiring Bias](https://mitsloan.mit.edu/ideas-made-to-matter/ai-reinventing-hiring-same-old-biases-heres-how-to-avoid-trap)
- [Gene Dai: Five Years of AI Recruitment Failures](https://genedai.medium.com/implementing-ai-in-recruitment-what-five-years-of-failures-taught-me-37c239804aaa)
- [LinkedIn AI Bias Discovery](https://www.technologyreview.com/2021/06/23/1026825/linkedin-ai-bias-ziprecruiter-monster-artificial-intelligence/)
- [Juicebox: AI Recruitment Mistakes 2025](https://juicebox.ai/blog/ai-recruitment-mistakes)
- [GoCo: AI Recruitment Pitfalls](https://www.goco.io/blog/common-ai-recruitment-pitfalls-to-avoid)

### Technical Research
- [Frontiers: Career Path Prediction](https://www.frontiersin.org/journals/big-data/articles/10.3389/fdata.2025.1564521/full)
- [OpenAI: Why LLMs Hallucinate](https://openai.com/index/why-language-models-hallucinate/)
- [ZeroEntropy: Reranking Models Guide](https://www.zeroentropy.dev/articles/ultimate-guide-to-choosing-the-best-reranking-model-in-2025)
- [SOO Group: Semantic Talent Matching](https://thesoogroup.com/blog/semantic-talent-matching-vector-search)
- [arXiv: From Text to Talent](https://arxiv.org/html/2503.17438v1)
- [Resume2Vec Research](https://www.mdpi.com/2079-9292/14/4/794)

### Skills and Ontology
- [Eightfold AI Review](https://www.testgorilla.com/blog/eightfold-ai-review/)
- [Fuel50: Skills Ontology](https://fuel50.com/2025/06/what-is-a-skills-ontology/)
- [Virtual Employee: AI Skills Graphs](https://www.virtualemployee.com/blog/beyond-the-cv-the-global-rise-of-ai-powered-skills-graphs-in-hiring/)

### Data and Scoring
- [Medium: Missing Data in Hiring](https://medium.com/junior-economist/the-hidden-cost-of-missing-data-how-flawed-analytics-shape-hiring-decisions-376091afb091)
- [Clay: Handling Empty Fields](https://community.clay.com/x/support/v7nd22or1yah/handling-ai-scoring-errors-due-to-empty-candidate)
- [HiringBranch: AI Resume Screening Guide](https://www.hiringbranch.com/blog/artificial-intelligence-resume-screening)

---

*Pitfalls analysis: 2026-01-24*
