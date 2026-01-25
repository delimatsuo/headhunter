# Domain Pitfalls: v2.0 Advanced Intelligence

**Domain:** Adding ML trajectory prediction, NLP search, and compliance tooling to existing AI recruiting system
**Researched:** 2026-01-25
**Confidence:** HIGH (based on academic research, regulatory guidance, and production ML deployment patterns)

---

## Critical Pitfalls

Mistakes that cause rewrites, major regulatory issues, or fundamentally broken systems.

---

### Pitfall 1: Rule-to-ML Migration Without Baseline Parity

**What goes wrong:** Teams replace the working rule-based career trajectory system with an RNN/LSTM model that performs worse on edge cases the rules handled correctly. The ML model looks impressive on aggregate metrics but fails spectacularly on specific scenarios that matter to recruiters.

**Why it happens:**
- ML model trained on aggregate data doesn't capture business-critical edge cases
- Rule-based system embodies years of implicit domain knowledge not documented anywhere
- Team measures ML accuracy but not business-outcome parity
- Pressure to "modernize" trumps careful migration planning

**Consequences:**
- Regression on scenarios recruiters rely on (e.g., career changers, gap years, non-linear paths)
- User trust destroyed when previously-working searches fail
- Rollback pressure creates organizational friction
- Wasted 3-6 months of ML development effort

**YOUR CURRENT CODEBASE CONTEXT:**
From PRD: v1.0 uses rule-based trajectory that "works but not predictive." This working system represents a baseline that any ML replacement must match or exceed on ALL scenarios, not just average performance.

**Warning signs:**
- ML model has higher aggregate accuracy but fails on recruiter-reported edge cases
- No documented test suite covering rule-based system's behavior
- No A/B comparison framework in place before migration
- Team cannot articulate what specific predictions the ML model improves

**Prevention:**
- **Document rule-based behavior exhaustively:** Create test cases from current rules before writing any ML code
- **Define parity gates:** ML model must match rules on 100% of documented scenarios before deployment
- **Hybrid fallback:** Keep rules active for scenarios where ML confidence is low
- **Shadow mode first:** Run ML predictions alongside rules for 4-6 weeks, measure divergence
- **Business metrics over ML metrics:** Track "recruiter satisfaction" and "time-to-shortlist," not just model accuracy

**Phase to address:** Phase 1 (ML Trajectory) - baseline documentation and parity gates before model development

**Industry evidence:**
- [Capital One engineering](https://www.capitalone.com/tech/machine-learning/rules-vs-machine-learning/): "It's fantastically rare for systems to be migrated to only use machine learning. Instead, a pragmatic trade-off is to understand what value the ML bit is providing."
- [ML deployment failures research](https://cloud.folio3.com/blog/mlops-best-practices/): "Poor data quality causes 60% of ML project failures."

---

### Pitfall 2: Sequence Model Mistraining (One-Step Lag Problem)

**What goes wrong:** LSTM/RNN career trajectory model learns to predict "next job = current job" because training uses sequence length 1, the model isn't properly unrolled, or teacher forcing is misconfigured. Model achieves high accuracy by simply copying input to output.

**Why it happens:**
- Training code feeds one-timestep sequences without proper unrolling
- Model states reset between batches, preventing temporal learning
- Teacher forcing not gradually reduced during training (scheduled sampling)
- Vanishing gradient problem not addressed with proper architecture choices
- Dataset has many stable careers (same role for years) which rewards identity prediction

**Consequences:**
- Model predicts everyone will stay in their current role
- No actual career trajectory insight - just expensive identity function
- Impossible to detect without explicit testing for trajectory change scenarios
- High reported accuracy masks complete failure on actual prediction task

**Warning signs:**
- Model accuracy > 90% on first iteration (suspiciously high)
- Predictions rarely differ from current position
- Model performance identical across 1-year, 3-year, 5-year horizons
- Career changers consistently predicted to stay in current field

**Prevention:**
- **Test on trajectory changers explicitly:** Create holdout set of candidates who DID change roles
- **Force prediction horizon diversity:** Train separate heads for 1-year, 3-year, 5-year predictions
- **Scheduled sampling:** Gradually increase use of model's own predictions during training
- **Sequence length validation:** Ensure training sequences are 3+ jobs, properly unrolled
- **Baseline comparison:** Compare against "predict last seen role" baseline - must beat it significantly
- **Modern alternatives:** Consider Transformer architectures over LSTM for long-range dependencies

**Phase to address:** Phase 1 (ML Trajectory) - architecture and training protocol design

**Industry evidence:**
- [Machine Learning Mastery](https://machinelearningmastery.com/time-series-prediction-lstm-recurrent-neural-networks-python-keras/): "Feeding a sequence of length 1 means the RNN is not unrolled. The updated internal state is not used anywhere."
- [Frontiers research on career prediction](https://www.frontiersin.org/journals/big-data/articles/10.3389/fdata.2025.1564521/full): "Prior models predict only one immediate next step, so users cannot make long-term plans."

---

### Pitfall 3: NYC Local Law 144 Compliance Theater

**What goes wrong:** Company posts a bias audit on website and sends notices, but the audit uses inadequate data, doesn't meet statistical significance thresholds, or the company fails to act on adverse findings. Compliance appears complete but legal exposure remains.

**Why it happens:**
- Audit uses test data or imputed data instead of actual historical decisions
- Audit conducted by non-independent party (internal team or vendor who built the tool)
- Impact ratios calculated but no action taken when bias detected
- Notice sent but not 10 business days before AEDT use
- Assuming weak enforcement means low risk (private litigation still applies)

**Consequences:**
- $500-$1500 fines per violation (can multiply quickly with volume)
- Private litigation from rejected candidates citing audit as evidence
- Reputational damage when audit results become public
- Liability under federal Title VII even if LL144 technically satisfied

**YOUR CURRENT CODEBASE CONTEXT:**
System has 23,000+ candidates in production. Any AEDT features (ML trajectory, NLP ranking) processing NYC applicants triggers LL144 requirements. The volume means statistical significance thresholds can be met but also amplifies violation counts if non-compliant.

**Warning signs:**
- Audit uses vendor-provided test data instead of your actual hiring decisions
- Same vendor that built the tool is conducting the audit
- No documented process for responding to adverse impact findings
- Candidate notices template-generic, not specific to your AEDT features
- No tracking of when candidates received notice vs. when AEDT processed them

**Prevention:**
- **Independent auditor requirement:** Engage auditor with no financial relationship to your company or tool vendor
- **Use actual historical data:** Collect sufficient actual decision data (may need 6+ months before deployment)
- **Impact ratio tracking:** Monitor selection rates by race/ethnicity/sex continuously, not just annually
- **EEOC 80% rule alignment:** LL144 doesn't require EEOC compliance, but violating 80% rule creates Title VII exposure
- **Document everything:** Audit methodology, data sources, remediation actions - all discoverable in litigation
- **Notice timing automation:** System must prove 10 business days elapsed between notice and AEDT use

**Phase to address:** Phase 3 (Compliance) - audit framework and notice automation

**Industry evidence:**
- [NYC Comptroller audit Dec 2025](https://www.osc.ny.gov/state-agencies/audits/2025/12/02/enforcement-local-law-144-automated-employment-decision-tools): Found 17 potential violations in 32 companies reviewed; DCWP identified only 1.
- [Fairly AI compliance guide](https://www.fairly.ai/blog/how-to-comply-with-nyc-ll-144-in-2025): "Organizations should not assume weak enforcement protects them - private litigation and reputational risks remain significant."

---

### Pitfall 4: EU AI Act High-Risk Misclassification

**What goes wrong:** Team assumes existing features are not "high-risk" under EU AI Act because they're "just search" or "just recommendations." Any AI system used in recruitment decisions is automatically high-risk, triggering extensive documentation, human oversight, and conformity assessment requirements.

**Why it happens:**
- Misunderstanding scope: "recruitment and HR decision-making" is explicitly high-risk
- Assuming EU-only companies affected (extraterritorial reach applies if output used in EU)
- Timeline confusion: thinking 2026 deadline means no action needed in 2025
- Underestimating documentation burden (risk management, data governance, logging)

**Consequences:**
- Fines up to 35 million EUR or 7% of global turnover
- System banned from EU market until conformity achieved
- 6-12 month scramble to retrofit compliance into production system
- Clients with EU operations cannot use your product

**YOUR CURRENT CODEBASE CONTEXT:**
PRD mentions "Ella recruiters" with candidates in Brazil. If Ella has any EU presence or processes EU residents, the entire system becomes subject to EU AI Act. ML trajectory predictions and NLP ranking are unambiguously "AI systems used for recruitment" = high-risk.

**Warning signs:**
- No EU AI Act assessment in product roadmap
- No human oversight mechanisms documented
- No risk management system for AI features
- No plan for CE marking or EU database registration
- Assuming "we don't operate in EU" without checking client/candidate geography

**Prevention:**
- **Immediate (Feb 2025):** Remove any emotion recognition or biometric categorization features
- **Document now:** Start risk management documentation even before 2026 deadline
- **Human oversight by design:** Build review/override mechanisms into every AI decision
- **Vendor pressure:** If using third-party ML, require their EU AI Act compliance roadmap
- **Per-decision logging:** Every AI recommendation must be logged with rationale for post-market monitoring
- **Geography filtering:** Know where your candidates/clients are; segment EU-affected flows

**Phase to address:** Phase 3 (Compliance) - overlaps with LL144 but has additional requirements

**Industry evidence:**
- [EU AI Act official text](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai): High-risk systems include "employment, workers' management and access to self-employment."
- [HeroHunt.ai EU compliance guide](https://www.herohunt.ai/blog/recruiting-under-the-eu-ai-act-impact-on-hiring): "If the AI's output is used in the EU, the Act applies - even if you're outside the EU."

---

## Moderate Pitfalls

Mistakes that cause delays, technical debt, or degraded user experience.

---

### Pitfall 5: NLP Query Parsing Brittleness

**What goes wrong:** NLP search query parser works well on clean, well-structured queries but fails catastrophically on real recruiter queries with typos, slang, mixed languages, or domain-specific abbreviations.

**Why it happens:**
- Parser trained on clean text, not messy real-world queries
- No graceful degradation when parsing fails
- Over-reliance on intent classification without fallback
- Not handling Portuguese-English mixed queries (your user base)

**Consequences:**
- Search returns irrelevant results or errors on common query patterns
- Users lose trust and revert to basic keyword search
- Edge cases dominate support tickets
- Parser "improvements" fix one case, break another

**Warning signs:**
- Parser works in demos but fails in production logs
- High rate of "no results" for queries that should match
- Users adding quotes or special syntax to "help" the parser
- Different behavior for same query with minor variations

**Prevention:**
- **Test on production query logs:** Use actual user queries, not synthetic test cases
- **Graceful degradation:** Falling back to keyword search is better than error or empty results
- **Confidence thresholds:** Return parsing confidence; use fallback when low
- **Multi-language training:** Include PT-BR queries in training data
- **Fuzzy matching layer:** Handle typos and abbreviations before semantic parsing
- **User feedback loop:** Let users mark "this isn't what I meant" for retraining

**Phase to address:** Phase 2 (NLP Search) - robustness testing before launch

**Industry evidence:**
- [arXiv NLP in HR survey](https://arxiv.org/abs/2410.16498): "Keyword-based filters often result in false negatives - desirable candidates with poorly written resumes are filtered out."
- [LLM-as-a-Judge research](https://public-pages-files-2025.frontiersin.org/journals/big-data/articles/10.3389/fdata.2025.1611389/pdf): "Traditional evaluation methods struggle to reflect query understanding capability in complex applications."

---

### Pitfall 6: Latency Budget Exhaustion

**What goes wrong:** Adding ML trajectory predictions and NLP parsing to the search pipeline pushes latency from 1.2s to 2-3s, exceeding the 500ms target. Each component is "fast enough" in isolation but the cumulative effect breaks SLAs.

**Why it happens:**
- Each team optimizes their component without end-to-end budget
- Cold start latency not accounted for (first query after idle)
- No parallel execution design - everything runs sequentially
- Model size selected for accuracy without latency consideration
- Network round-trips to ML services add up

**Consequences:**
- Search feels slow to users, especially on repeated queries
- Infrastructure costs spike from auto-scaling to meet latency under load
- Performance regressions block feature launches
- Constant firefighting instead of feature development

**YOUR CURRENT CODEBASE CONTEXT:**
PRD states "p95 <= 1.2s; rerank <= 350ms @K<=200." Adding ML trajectory + NLP parsing to this budget means each new component gets ~50-75ms, not the 200-300ms typical for naive ML serving.

**Warning signs:**
- p95 latency creeping up with each feature addition
- "It's fast on my machine" but slow in production
- Latency varies wildly between queries (cold vs warm)
- Performance tests pass but production monitoring shows SLA violations

**Prevention:**
- **Explicit latency budgets:** Allocate ms to each pipeline stage BEFORE implementation
- **Parallel execution:** Run ML trajectory and NLP parsing concurrently, not sequentially
- **Model quantization:** INT8 quantization can cut inference time 4x with minimal accuracy loss
- **Precomputation:** Compute trajectory predictions at enrichment time, not search time
- **Caching:** Cache NLP parsing results for repeated/similar queries
- **Timeout with fallback:** If ML stage exceeds budget, skip it and return results without that signal

**Phase to address:** Phase 4 (Performance) - but budget allocation needed in Phase 1-2 design

**Industry evidence:**
- [Google Cloud ML serving guide](https://cloud.google.com/architecture/minimizing-predictive-serving-latency-in-machine-learning): "Most libraries are tuned to use all available resources for single model evaluation - this breaks down for concurrent evaluations."
- [NStarX latency optimization](https://nstarxinc.com/blog/the-business-imperative-of-llm-latency-optimization-winning-the-speed-wars-in-production-ai/): "User expectations are compressing: today's acceptable 1-2 second threshold will become 200-500ms."

---

### Pitfall 7: Anonymization Proxy Leakage

**What goes wrong:** Bias reduction anonymization removes obvious identifiers (name, photo, gender) but leaves proxy variables that encode the same information. University name reveals race, employment gaps reveal parenting status, address reveals socioeconomic background.

**Why it happens:**
- Anonymization focuses on direct identifiers, not proxies
- Model learns indirect correlations from "neutral" features
- No testing for proxy-based disparate impact
- Assuming "we removed the protected field" means bias eliminated

**Consequences:**
- False confidence in bias reduction while discrimination continues
- Audit failures when proxy correlations discovered
- Legal exposure worse than no anonymization (shows knowledge + inadequate action)
- Candidates from underrepresented groups still filtered despite "blind" process

**Warning signs:**
- Selection rates still differ by demographic after anonymization
- Model weights high on features correlated with protected classes
- Certain universities/companies systematically scored lower
- Employment gap penalty disproportionately affects women

**Prevention:**
- **Proxy variable audit:** Identify all features correlated with protected classes
- **Disparate impact testing:** Measure selection rates AFTER anonymization, not just before
- **Fairness-aware training:** Use techniques that explicitly constrain demographic parity
- **Feature contribution analysis:** Understand why model makes decisions, not just what decisions
- **Regular re-auditing:** Proxy effects can emerge as model retrains on new data

**Phase to address:** Phase 3 (Compliance) - anonymization design

**Industry evidence:**
- [MIT Sloan](https://mitsloan.mit.edu/ideas-made-to-matter/ai-reinventing-hiring-same-old-biases-heres-how-to-avoid-trap): "Some AI tools have downgraded resumes from historically Black colleges and women's colleges. Others have penalized employment gaps, disadvantaging parents."
- [MDPI AI techniques review](https://www.mdpi.com/2673-2688/5/1/19): "Even when removing sensitive attributes, proxies can still encode bias - including university lists, language, location, and employment gaps."

---

### Pitfall 8: Training Data Drift from Production

**What goes wrong:** ML trajectory model trained on historical data performs well initially but degrades over time as career patterns change. Model keeps predicting 2020-era career paths in 2026 job market.

**Why it happens:**
- Training data is static snapshot, not updated pipeline
- Career patterns shifted (remote work, tech layoffs, AI roles)
- No monitoring for prediction accuracy over time
- Retraining scheduled annually but market shifts quarterly

**Consequences:**
- Model predictions increasingly wrong over time
- Users notice outdated suggestions ("why is it predicting everyone goes to FAANG?")
- Competitive disadvantage vs. systems with fresher models
- Silent degradation - no alerts until users complain

**Warning signs:**
- Model accuracy declining month-over-month on holdout set
- Predictions increasingly divergent from actual career moves observed
- Model confident about predictions that recruiters say are wrong
- Training data ends 12+ months ago

**Prevention:**
- **Continuous evaluation:** Track prediction accuracy on actual outcomes, not just training metrics
- **Automated retraining triggers:** Retrain when accuracy drops below threshold
- **Concept drift detection:** Monitor input distribution shifts that indicate market changes
- **Recruiter feedback loop:** Let users flag "this prediction was wrong" for retraining signal
- **Vintage labeling:** Track when predictions were made, compare vintage cohorts

**Phase to address:** Phase 1 (ML Trajectory) - MLOps design

**Industry evidence:**
- [Folio3 MLOps guide](https://cloud.folio3.com/blog/mlops-best-practices/): "A common fallacy is that ML models never need retraining. Models must be retrained as data drifts from what they were trained on."
- [Production ML systems - Google](https://developers.google.com/machine-learning/crash-course/production-ml-systems): "Production ML models experience performance degradation over time due to changing data patterns."

---

## Minor Pitfalls

Mistakes that cause annoyance but are fixable without major rework.

---

### Pitfall 9: Career Taxonomy Mismatch

**What goes wrong:** ML trajectory model uses one job taxonomy (e.g., O*NET), NLP parser uses another (e.g., internal categories), and existing profiles use a third (e.g., recruiter-defined titles). Predictions don't map to searchable categories.

**Prevention:**
- Define single canonical taxonomy before building any component
- Build bidirectional mappings for legacy data
- Validate taxonomy coverage against actual profile data

**Phase to address:** Phase 1 (ML Trajectory) - data modeling

---

### Pitfall 10: Test Data Contamination

**What goes wrong:** ML model test set includes candidates who were also in training set (e.g., same person with updated resume). Reported accuracy is inflated because model memorized individuals.

**Prevention:**
- Split by candidate ID, not by record
- Hold out entire candidate histories, not individual snapshots
- Use truly future data (never seen during training) for final evaluation

**Phase to address:** Phase 1 (ML Trajectory) - evaluation design

---

### Pitfall 11: Compliance Documentation Rot

**What goes wrong:** Initial compliance documentation is thorough, but not updated as system evolves. Auditors find documentation describes v1.0 while production runs v2.3.

**Prevention:**
- Tie documentation to deployment pipeline (force update before deploy)
- Version compliance docs alongside code
- Quarterly documentation review scheduled and assigned

**Phase to address:** Phase 3 (Compliance) - process design

---

### Pitfall 12: Human Oversight Checkbox

**What goes wrong:** "Human oversight" for EU AI Act compliance means a human clicks "approve" on 100% of decisions without actually reviewing. Technically compliant, practically useless, legally vulnerable.

**Prevention:**
- Design oversight that forces meaningful review (show subset of info, require explanation)
- Sample audit of override decisions
- Track oversight decision time (instant approvals flagged)

**Phase to address:** Phase 3 (Compliance) - UX design for oversight

---

## Phase-Specific Warnings

| Phase | Topic | Likely Pitfall | Mitigation |
|-------|-------|---------------|------------|
| Phase 1 | ML Trajectory | Rule parity regression | Exhaustive test suite from existing rules |
| Phase 1 | ML Trajectory | One-step lag mistraining | Test on career changers, compare to baseline |
| Phase 1 | ML Trajectory | Latency budget consumed | Set 75ms budget for trajectory component |
| Phase 2 | NLP Search | Query parsing brittleness | Test on production query logs, not synthetic |
| Phase 2 | NLP Search | Mixed language failures | Include PT-BR in training data |
| Phase 2 | NLP Search | Latency addition | Parallel execution with trajectory |
| Phase 3 | Compliance | LL144 audit inadequacy | Independent auditor, actual historical data |
| Phase 3 | Compliance | EU AI Act high-risk scope | Document everything NOW, don't wait for 2026 |
| Phase 3 | Compliance | Proxy variable leakage | Disparate impact testing after anonymization |
| Phase 4 | Performance | Cumulative latency | Pre-allocate budgets, precompute where possible |
| Phase 4 | Performance | Cold start spikes | Warm-up strategies, caching layer |

---

## Sources

### ML Career Prediction
- [Frontiers - Toward more realistic career path prediction](https://www.frontiersin.org/journals/big-data/articles/10.3389/fdata.2025.1564521/full)
- [Machine Learning Mastery - LSTM sequence prediction](https://machinelearningmastery.com/time-series-prediction-lstm-recurrent-neural-networks-python-keras/)
- [Capital One - Rules vs Machine Learning](https://www.capitalone.com/tech/machine-learning/rules-vs-machine-learning/)

### NLP and Query Understanding
- [arXiv - NLP for Human Resources Survey](https://arxiv.org/abs/2410.16498)
- [MDPI - Intent Identification by Semantic Analysis](https://www.mdpi.com/2673-3951/5/1/16)

### NYC Local Law 144
- [NYC DCWP - AEDT Official Page](https://www.nyc.gov/site/dca/about/automated-employment-decision-tools.page)
- [NYC Comptroller - Enforcement Audit Dec 2025](https://www.osc.ny.gov/state-agencies/audits/2025/12/02/enforcement-local-law-144-automated-employment-decision-tools)
- [Fairly AI - LL144 Compliance Guide 2025](https://www.fairly.ai/blog/how-to-comply-with-nyc-ll-144-in-2025)

### EU AI Act
- [EU Official - AI Act Framework](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai)
- [HeroHunt - EU AI Act Recruiting Guide](https://www.herohunt.ai/blog/recruiting-under-the-eu-ai-act-impact-on-hiring)
- [Dataiku - High-Risk Requirements](https://www.dataiku.com/stories/blog/eu-ai-act-high-risk-requirements)

### Bias and Fairness
- [MIT Sloan - AI Hiring Bias](https://mitsloan.mit.edu/ideas-made-to-matter/ai-reinventing-hiring-same-old-biases-heres-how-to-avoid-trap)
- [MDPI - AI Techniques for Algorithmic Bias](https://www.mdpi.com/2673-2688/5/1/19)
- [arXiv - Fairness in AI-Driven Recruitment](https://arxiv.org/html/2405.19699v3)

### ML Production and Latency
- [Google Cloud - Minimizing ML Serving Latency](https://cloud.google.com/architecture/minimizing-predictive-serving-latency-in-machine-learning)
- [Google Developers - Production ML Systems](https://developers.google.com/machine-learning/crash-course/production-ml-systems)
- [Folio3 - MLOps Best Practices](https://cloud.folio3.com/blog/mlops-best-practices/)
