# Requirements: Headhunter AI v2.0 Advanced Intelligence

**Defined:** 2026-01-25
**Core Value:** Find candidates who are actually qualified, not just candidates who happen to have the right keywords.

## v2.0 Requirements

Requirements for advanced intelligence milestone. Building on v1.0 leader-level search foundation.

### Performance Optimization

- [ ] **PERF-01**: p95 search latency under 500ms (from current 1.2s target)
- [ ] **PERF-02**: pgvectorscale integration for 28x latency improvement
- [ ] **PERF-03**: Connection pooling and parallel query execution
- [ ] **PERF-04**: Embedding pre-computation for entire candidate pool
- [ ] **PERF-05**: Redis caching strategy with scoring cache invalidation

### Natural Language Search

- [ ] **NLNG-01**: Intent parsing extracts role, skills, location, preferences from natural language
- [ ] **NLNG-02**: Semantic query understanding ("Senior" matches "Lead", "Principal")
- [ ] **NLNG-03**: Query expansion using skills ontology ("Python dev" includes related skills)
- [ ] **NLNG-04**: Multi-criteria natural language queries ("Remote Python devs, 5+ years, open to startups")
- [ ] **NLNG-05**: Graceful fallback to structured search when NLP parsing fails

### ML Trajectory Prediction

- [ ] **TRAJ-05**: Next role prediction with confidence score using LSTM model
- [ ] **TRAJ-06**: Tenure prediction (estimated time candidate will stay in role)
- [ ] **TRAJ-07**: Model confidence indicators (transparency for uncertain predictions)
- [ ] **TRAJ-08**: Shadow mode deployment comparing ML vs rule-based predictions
- [ ] **TRAJ-09**: Hireability prediction (likelihood to join company like ours)

### Bias Reduction

- [ ] **BIAS-01**: Resume anonymization toggle (remove name, photo, school names)
- [ ] **BIAS-02**: Demographic-blind scoring (no demographic proxies in scoring)
- [ ] **BIAS-03**: Bias metrics dashboard with selection rates by group
- [ ] **BIAS-04**: Impact ratio calculation (four-fifths rule / 80% threshold)
- [ ] **BIAS-05**: Diverse slate generation to prevent homogeneous candidate pools

### Compliance Tooling

- [ ] **COMP-01**: Comprehensive audit logging (who searched what, when, results shown)
- [ ] **COMP-02**: Decision explanation storage for each ranking
- [ ] **COMP-03**: NYC Local Law 144 candidate notification system
- [ ] **COMP-04**: GDPR data subject access request (DSAR) support
- [ ] **COMP-05**: Data retention policy enforcement (auto-delete after period)
- [ ] **COMP-06**: Bias audit report generation for NYC LL144 annual requirement

## Future Requirements

Deferred beyond v2.0. Valuable but higher complexity.

### Advanced Trajectory Intelligence

- **TRAJ-10**: Career path visualization (interactive journey view)
- **TRAJ-11**: "Rising star" detection for high-potential candidates
- **TRAJ-12**: Industry transition prediction
- **TRAJ-13**: Skill acquisition prediction

### Conversational Search

- **NLNG-06**: Multi-turn refinement ("Show me more junior ones")
- **NLNG-07**: Proactive suggestions based on search patterns
- **NLNG-08**: Query-to-JD generation

### Explainable AI

- **XAI-01**: SHAP-based feature importance for rankings
- **XAI-02**: Counterfactual explanations ("Would rank higher with X skill")
- **XAI-03**: Recruiter feedback loop for continuous improvement

### Multi-Jurisdiction Compliance

- **COMP-07**: Multi-jurisdiction compliance engine (NYC, EU, Illinois, etc.)
- **COMP-08**: Real-time bias monitoring with drift alerts
- **COMP-09**: Third-party audit API

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Autonomous hiring decisions (auto-reject/shortlist) | Regulatory risk - EU AI Act prohibits fully automated decisions |
| Black-box scoring | NYC LL144 and EU AI Act require transparency |
| Salary offer automation | High legal risk for compensation discrimination |
| Unbounded data collection | GDPR minimization principle |
| Full automation without human oversight | Regulatory requirement for human-in-the-loop |
| Mobile native app | Web-first approach |
| Real-time chat | Different product focus |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PERF-01 | Phase 11: Performance Foundation | Pending |
| PERF-02 | Phase 11: Performance Foundation | Pending |
| PERF-03 | Phase 11: Performance Foundation | Pending |
| PERF-04 | Phase 11: Performance Foundation | Pending |
| PERF-05 | Phase 11: Performance Foundation | Pending |
| NLNG-01 | Phase 12: Natural Language Search | Pending |
| NLNG-02 | Phase 12: Natural Language Search | Pending |
| NLNG-03 | Phase 12: Natural Language Search | Pending |
| NLNG-04 | Phase 12: Natural Language Search | Pending |
| NLNG-05 | Phase 12: Natural Language Search | Pending |
| TRAJ-05 | Phase 13: ML Trajectory Prediction | Pending |
| TRAJ-06 | Phase 13: ML Trajectory Prediction | Pending |
| TRAJ-07 | Phase 13: ML Trajectory Prediction | Pending |
| TRAJ-08 | Phase 13: ML Trajectory Prediction | Pending |
| TRAJ-09 | Phase 13: ML Trajectory Prediction | Pending |
| BIAS-01 | Phase 14: Bias Reduction | Pending |
| BIAS-02 | Phase 14: Bias Reduction | Pending |
| BIAS-03 | Phase 14: Bias Reduction | Pending |
| BIAS-04 | Phase 14: Bias Reduction | Pending |
| BIAS-05 | Phase 14: Bias Reduction | Pending |
| COMP-01 | Phase 15: Compliance Tooling | Pending |
| COMP-02 | Phase 15: Compliance Tooling | Pending |
| COMP-03 | Phase 15: Compliance Tooling | Pending |
| COMP-04 | Phase 15: Compliance Tooling | Pending |
| COMP-05 | Phase 15: Compliance Tooling | Pending |
| COMP-06 | Phase 15: Compliance Tooling | Pending |

**Coverage:**
- v2.0 requirements: 26 total
- Mapped to phases: 26
- Unmapped: 0

---
*Requirements defined: 2026-01-25*
*Last updated: 2026-01-25 after v2.0 research*
