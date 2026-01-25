# Feature Landscape: v2.0 Advanced Intelligence

**Domain:** AI-powered recruitment analytics with predictive intelligence
**Researched:** 2026-01-25
**Confidence:** MEDIUM (WebSearch verified with multiple sources)

## Context: Building on v1.0

**Existing features (already built):**
- Search returns 50+ qualified candidates via pgvector + FTS hybrid recall
- 8-signal weighted scoring system
- Skills inference with 468-skill taxonomy
- Career trajectory analysis (direction, velocity, fit)
- Match transparency with rationale ("Why they're a match")
- Pre-interview analysis (on-demand)

**v2.0 Focus Areas:**
1. RNN-based career trajectory prediction
2. Natural language search ("Find senior Python devs in NYC open to fintech")
3. Bias reduction (anonymization, diverse slates)
4. Compliance tooling (NYC Local Law 144, EU AI Act)

---

## Table Stakes

Features users expect for these advanced capabilities. Missing = product feels incomplete.

### RNN/Transformer Career Prediction

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|--------------|-------|
| **Next role prediction** | Core value prop of "predictive intelligence" | HIGH | Existing career trajectory data | Predict likely next job title/level with confidence score |
| **Tenure prediction** | Standard in career modeling | MEDIUM | Employment history | Estimate how long candidate will stay in a role |
| **Progression velocity score** | Users already expect this (v1 has basic version) | LOW | Existing trajectory signals | Quantify career advancement speed |
| **Model confidence indicators** | Regulatory requirement (EU AI Act transparency) | LOW | Model outputs | Show when predictions are uncertain |
| **Training data recency indicator** | Prevents stale predictions | LOW | Model metadata | Flag when model trained on old data |

**Confidence:** MEDIUM - Based on academic research (NEMO, CAREER foundation model) and industry tools

### Natural Language Search

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|--------------|-------|
| **Intent parsing** | Core NLP capability | MEDIUM | LLM or semantic parser | Extract entities: role, skills, location, preferences |
| **Semantic query understanding** | Differentiates from keyword search | MEDIUM | Embeddings infrastructure | "Senior" should match "Lead", "Principal" |
| **Query expansion** | Standard in modern search | LOW | Skills ontology | Auto-expand "Python dev" to include related skills |
| **Multi-criteria queries** | Complex searches are the value prop | MEDIUM | Filter infrastructure | "Remote Python devs, 5+ years, open to startups" |
| **Query clarification** | Users expect conversational UX | MEDIUM | LLM integration | "Did you mean X or Y?" for ambiguous queries |
| **Fallback to structured search** | Graceful degradation | LOW | Existing search | If NLP fails, fall back to keyword/filter |

**Confidence:** HIGH - Semantic search is well-established; Resume2Vec and similar research shows 15%+ improvement over keyword matching

### Bias Reduction

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|--------------|-------|
| **Resume anonymization toggle** | Core blind hiring capability | LOW | Profile data model | Remove name, photo, school names on toggle |
| **Demographic-blind scoring** | Regulatory expectation | MEDIUM | Scoring pipeline | Ensure no demographic proxies in scoring |
| **Bias metrics dashboard** | Compliance requirement (NYC LL 144) | MEDIUM | Audit logging | Selection rates by demographic group |
| **Impact ratio calculation** | Required for bias audits | MEDIUM | Historical data | Four-fifths rule (80%) threshold |
| **Diverse slate generation** | Industry best practice | MEDIUM | Re-ranking logic | Ensure candidate pools aren't homogeneous |

**Confidence:** HIGH - NYC Local Law 144 explicitly requires bias audits; EU AI Act requires human oversight

### Compliance Tooling

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|--------------|-------|
| **Audit logging** | Required for all compliance regimes | MEDIUM | Logging infrastructure | Who searched what, when, what was shown |
| **Decision explanation storage** | EU AI Act requirement | LOW | Search results model | Store why each candidate was ranked |
| **Candidate notification system** | NYC LL 144 requirement | LOW | Notification service | "AI was used in evaluating your application" |
| **Data subject access request (DSAR) support** | GDPR requirement | MEDIUM | Data export tooling | Export all data about a candidate on request |
| **Retention policy enforcement** | GDPR requirement | MEDIUM | Scheduled jobs | Auto-delete after 6-12 months post-decision |
| **Bias audit report generation** | NYC LL 144 annual requirement | HIGH | Analytics pipeline | Selection rates, impact ratios, intersectional analysis |

**Confidence:** HIGH - Regulatory requirements are explicit and enforced

---

## Differentiators

Features that set the product apart. Not expected, but valued.

### Advanced Trajectory Intelligence

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|-------------------|------------|--------------|-------|
| **Career path visualization** | Shows trajectory, not just current state | MEDIUM | Timeline data | Interactive career journey view |
| **"Rising star" detection** | Find high-potential candidates early | HIGH | Trajectory model | Identify fast-trackers before peers |
| **Industry transition prediction** | Unique insight for cross-industry hires | HIGH | Cross-industry training data | "Likely to move from consulting to tech" |
| **Skill acquisition prediction** | Proactive talent development | HIGH | Skills trajectory data | "Will likely learn Kubernetes within 2 years" |
| **Counter-offer risk assessment** | Recruitment intelligence | MEDIUM | Market data, tenure patterns | Flag candidates likely to accept counter-offers |

**Confidence:** MEDIUM - CAREER foundation model research shows feasibility; real-world accuracy TBD

### Conversational Search Intelligence

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|-------------------|------------|--------------|-------|
| **Multi-turn refinement** | Conversational UX like ChatGPT | HIGH | Session state, LLM | "Show me more junior ones" |
| **Proactive suggestions** | AI assists recruiters | MEDIUM | Search analytics | "Candidates matching this JD often have X skill" |
| **Saved natural language queries** | Workflow efficiency | LOW | Query storage | Save "Find senior fintech PMs in NYC" as template |
| **Query-to-JD generation** | Reverse direction | MEDIUM | LLM integration | Generate JD from conversational requirements |
| **Competitive intelligence integration** | Market context | HIGH | External data sources | "Candidates from companies similar to Stripe" |

**Confidence:** MEDIUM - LLM-based search is evolving rapidly; accuracy depends on implementation

### Explainable AI (XAI)

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|-------------------|------------|--------------|-------|
| **SHAP-based feature importance** | Understand why candidates ranked | HIGH | SHAP library integration | Show which factors drove each ranking |
| **Counterfactual explanations** | Actionable insights | HIGH | XAI modeling | "Candidate would rank higher with X skill" |
| **Recruiter feedback loop** | Continuous improvement | MEDIUM | Feedback collection | "This match was off because..." |
| **Explanation confidence scores** | Trust calibration | MEDIUM | XAI infrastructure | When explanations are uncertain |

**Confidence:** MEDIUM - SHAP/LIME are well-established but "may be fooled by biased classifiers"

### Compliance Leadership

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|-------------------|------------|--------------|-------|
| **Real-time bias monitoring** | Proactive, not just annual audits | HIGH | Streaming analytics | Alert when selection rates drift |
| **Automated compliance reporting** | Reduces manual burden | MEDIUM | Report generation | Auto-generate NYC LL 144 bias audit reports |
| **Multi-jurisdiction compliance** | Global enterprise readiness | HIGH | Rule engine | Handle NYC, EU, Illinois, etc. simultaneously |
| **Audit-ready documentation** | Peace of mind | MEDIUM | Documentation pipeline | One-click export of all compliance evidence |
| **Third-party audit API** | Enable independent bias audits | MEDIUM | API design | Allow auditors to query system without full access |

**Confidence:** HIGH - Regulatory landscape is clear; implementation complexity is the challenge

---

## Anti-Features

Features to explicitly NOT build. Common mistakes in this domain.

### Do NOT Build: Autonomous Hiring Decisions

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Auto-reject candidates** | Regulatory risk (EU AI Act prohibits fully automated decisions with significant effects); legal liability | Always require human review; AI assists, doesn't decide |
| **Auto-shortlist without review** | Same regulatory issues; eliminates human judgment | Rank candidates, but human must confirm shortlist |
| **Salary offer automation** | High legal risk; compensation discrimination | Provide market data, but human determines offers |

**Regulatory basis:** EU AI Act explicitly requires human oversight for high-risk hiring AI. NYC LL 144 requires human alternative processes.

### Do NOT Build: Black-Box Scoring

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Opaque ranking algorithms** | Violates transparency requirements; can't audit for bias | Explainable scoring with rationale for every decision |
| **Proprietary "fit scores" without explanation** | Legally indefensible if challenged | Break down scores into interpretable components |
| **Hidden demographic proxies** | Can encode bias (zip code, school names as proxies for race/class) | Audit for proxy discrimination; document all features |

**Regulatory basis:** EU AI Act requires "sufficient transparency to enable users to interpret system output"

### Do NOT Build: Unbounded Data Collection

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Scraping social media without consent** | GDPR violation; platform ToS violation | Collect only with consent; use official APIs |
| **Storing data indefinitely** | GDPR data minimization principle | Implement retention policies (6-12 months typical) |
| **Processing sensitive categories without explicit consent** | Special category data requires explicit consent | Don't infer religion, health, political views from profiles |
| **Automated reference checking** | Privacy concerns; legal risk | Human-initiated, consent-based reference checks |

**Regulatory basis:** GDPR Article 5 (data minimization), Article 9 (special categories)

### Do NOT Build: Overconfident AI

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Presenting predictions as facts** | Erodes trust when wrong; legal risk | Always show confidence intervals; use "likely" language |
| **Career predictions without uncertainty** | Human careers are unpredictable; false precision | Show prediction ranges, not point estimates |
| **"Guaranteed" match scores** | No AI can guarantee fit | Frame as "estimated match based on available data" |

### Do NOT Build: One-Size-Fits-All Bias Mitigation

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Removing all demographic data** | Can hide discrimination rather than fix it; impossible to audit | Keep data for auditing, but anonymize for decision-making |
| **Simple demographic parity quotas** | Legally risky in some jurisdictions; may not address root causes | Focus on fair processes, not outcome mandates |
| **Automated "debiasing" without human oversight** | Can introduce new biases; lacks accountability | Human review of bias mitigation strategies |

---

## Feature Dependencies

```
Career Trajectory Prediction
    |
    +-- Skills taxonomy (EXISTING) --> Skill acquisition prediction
    |
    +-- Employment history parsing (EXISTING) --> Tenure prediction
    |
    +-- Model training infrastructure (NEW) --> Next role prediction
                                              |
                                              +--> "Rising star" detection

Natural Language Search
    |
    +-- Semantic embeddings (EXISTING) --> Intent parsing
    |
    +-- LLM integration (PARTIAL) --> Multi-turn refinement
    |                               |
    |                               +--> Query clarification
    |
    +-- Skills ontology (EXISTING) --> Query expansion

Bias Reduction
    |
    +-- Audit logging (NEW) --> Impact ratio calculation
    |                        |
    |                        +--> Bias metrics dashboard
    |
    +-- Profile anonymization (NEW) --> Demographic-blind scoring
    |
    +-- Re-ranking logic (EXISTING) --> Diverse slate generation

Compliance Tooling
    |
    +-- Audit logging (shared with Bias) --> Decision explanation storage
    |                                     |
    |                                     +--> Bias audit report generation
    |
    +-- Notification service (NEW) --> Candidate notification
    |
    +-- Data export (NEW) --> DSAR support
```

---

## MVP Recommendation

For v2.0 MVP, prioritize:

### Must Have (Phase 1)

1. **Natural language intent parsing** - Core UX improvement; builds on existing embeddings
   - Parse "Find senior Python devs in NYC" into structured query
   - Fallback to existing search if parsing fails
   - Dependencies: LLM integration (partial exists)

2. **Audit logging infrastructure** - Required for all compliance features
   - Log all search queries, results shown, candidate views
   - Include timestamps, user IDs, search parameters
   - Dependencies: New logging infrastructure

3. **Resume anonymization toggle** - Quick win for bias reduction
   - Hide name, photo, school names on toggle
   - Simple UI control per search
   - Dependencies: Profile data model (minor changes)

4. **Basic bias metrics** - Minimum for compliance readiness
   - Selection rates by available demographic proxies
   - Impact ratio warnings (below 80% threshold)
   - Dependencies: Audit logs, historical data

### Should Have (Phase 2)

5. **Career trajectory prediction (basic)** - Core differentiator
   - Predict next likely role (not full RNN yet; heuristic-based first)
   - Tenure estimate based on historical patterns
   - Dependencies: Employment history data

6. **Decision explanation storage** - Compliance requirement
   - Store why each candidate was ranked for each search
   - Linkable to audit logs
   - Dependencies: Search results model updates

7. **Candidate notification system** - NYC LL 144 requirement
   - Notify NYC candidates about AI usage
   - Template-based notifications
   - Dependencies: Notification service

### Defer to Post-MVP

- **Full RNN/Transformer trajectory model** - Requires significant ML infrastructure
- **Multi-turn conversational search** - Complex state management
- **SHAP-based explanations** - Computationally expensive; research needed on biased classifier risks
- **Real-time bias monitoring** - Requires streaming infrastructure
- **Multi-jurisdiction compliance engine** - Complex rule system

---

## Complexity Assessment

| Feature Category | Complexity | Rationale |
|------------------|------------|-----------|
| Natural Language Search | MEDIUM | LLM integration exists; intent parsing is well-understood |
| Basic Bias Reduction | LOW-MEDIUM | Anonymization is straightforward; metrics need historical data |
| Compliance Logging | MEDIUM | Infrastructure work; but patterns are well-established |
| Career Prediction (basic) | MEDIUM | Heuristic approach is feasible; ML approach is HIGH |
| Career Prediction (RNN/Transformer) | HIGH | Requires ML infrastructure, training data, evaluation |
| Explainable AI (SHAP/LIME) | HIGH | Integration complexity; interpretability challenges |
| Multi-turn Conversational | HIGH | Session state, context management, error recovery |

---

## Sources

### Career Trajectory Prediction
- [Job Recommendation Based on Recurrent Neural Network Approach](https://www.sciencedirect.com/science/article/pii/S1877050923006804) - ScienceDirect
- [NEMO: Next Career Move Prediction](http://team-net-work.org/pdfs/LiJTYHC_WWW17.pdf) - WWW17
- [CAREER: A Foundation Model for Labor Sequence Data](https://arxiv.org/pdf/2202.08370) - arXiv
- [Toward more realistic career path prediction: evaluation and methods](https://www.frontiersin.org/journals/big-data/articles/10.3389/fdata.2025.1564521/full) - Frontiers 2025
- [Transformer vs LSTM for Time Series](https://machinelearningmastery.com/transformer-vs-lstm-for-time-series-which-works-better/) - Machine Learning Mastery

### Natural Language Search
- [AI-Driven Semantic Similarity-Based Job Matching Framework](https://papers.ssrn.com/sol3/Delivery.cfm/f77503ce-1a0f-4b6b-9738-81c540cebed9-MECA.pdf?abstractid=5293689&mirid=1) - SSRN
- [How Semantic Search is Being Used in AI Recruitment](https://cvviz.com/blog/how-semantic-search-used-in-recruitment/) - CVViZ
- [Semantic Search in Recruitment: From Filters to Context](https://www.herohunt.ai/blog/semantic-search-in-recruitment) - HeroHunt.ai
- [Resume2Vec: Transforming Applicant Tracking Systems](https://www.mdpi.com/2079-9292/14/4/794) - MDPI Electronics
- [Combining Text-to-SQL with Semantic Search for RAG](https://www.llamaindex.ai/blog/combining-text-to-sql-with-semantic-search-for-retrieval-augmented-generation-c60af30ec3b) - LlamaIndex

### Bias Reduction
- [8 Diversity Hiring Best Practices for 2026](https://juicebox.ai/blog/diversity-hiring-best-practices) - Juicebox
- [Reducing AI bias in recruitment and selection](https://www.tandfonline.com/doi/full/10.1080/09585192.2025.2480617) - Taylor & Francis
- [Does blind hiring still make sense in 2026?](https://www.hiretruffle.com/blog/blind-hiring) - Truffle
- [How to Reduce AI Bias In Hiring](https://www.kula.ai/blog/how-to-reduce-ai-bias-in-hiring) - Kula.ai

### NYC Local Law 144 Compliance
- [NYC Local Law 144: AI Hiring Compliance Guide](https://fairnow.ai/guide/nyc-local-law-144/) - FairNow
- [Automated Employment Decision Tools (AEDT)](https://www.nyc.gov/site/dca/about/automated-employment-decision-tools.page) - NYC DCWP Official
- [New York AI Laws Guide 2026](https://www.glacis.io/guide-new-york-ai) - GLACIS
- [How to Comply with the NYC Bias Audit Law in 2026](https://www.nycbiasaudit.com/blog/how-to-comply-with-the-nyc-bias-audit-law) - NYC Bias Audit

### EU AI Act Compliance
- [Recruiting under the EU AI Act: Impact on Hiring](https://www.herohunt.ai/blog/recruiting-under-the-eu-ai-act-impact-on-hiring) - HeroHunt.ai
- [EU AI Act and Hiring: 2025 Compliance Guide](https://www.hiretruffle.com/blog/eu-ai-act-hiring) - Truffle
- [Use of AI in Recruitment and Hiring - EU and US](https://www.gtlaw.com/en/insights/2025/5/use-of-ai-in-recruitment-and-hiring-considerations-for-eu-and-us-companies) - Greenberg Traurig
- [High-level summary of the AI Act](https://artificialintelligenceact.eu/high-level-summary/) - EU AI Act Portal

### Explainable AI in Recruiting
- [Explainable AI in the talent recruitment process - literature review](https://www.tandfonline.com/doi/full/10.1080/23311975.2025.2570881) - Taylor & Francis 2025
- [A Perspective on Explainable AI Methods: SHAP and LIME](https://arxiv.org/html/2305.02012v3) - arXiv

### Skills Ontology & Knowledge Graphs
- [Skills ontology framework: Why You need it in 2026](https://gloat.com/blog/skills-ontology-framework/) - Gloat
- [Revolutionizing HR Recruiting with Knowledge Graphs and LLMs](https://blog.metaphacts.com/revolutionizing-hr-recruiting-with-knowledge-graphs-and-large-language-models) - Metaphacts
- [Matching Skills and Candidates with Graph RAG](https://www.ontotext.com/blog/matching-skills-and-candidates-with-graph-rag/) - Ontotext

### GDPR & Data Protection
- [Complete GDPR Compliance Guide (2026-Ready)](https://secureprivacy.ai/blog/gdpr-compliance-2026) - SecurePrivacy
- [GDPR Audit Trail Requirements](https://seersco.com/articles/tag/gdpr-audit-trail-requirements/) - Seers
- [6 Best Practices for GDPR Logging and Monitoring](https://www.cookieyes.com/blog/gdpr-logging-and-monitoring/) - CookieYes

---

## Quality Gate Checklist

- [x] Categories are clear (table stakes vs differentiators vs anti-features)
- [x] Complexity noted for each feature
- [x] Dependencies on existing features identified
- [x] Regulatory requirements cited for compliance features
- [x] MVP prioritization provided
- [x] Sources documented with confidence levels
