# Architecture Research: v2.0 Advanced Intelligence Integration

**Project:** Headhunter v2.0 Advanced Intelligence
**Research Focus:** RNN trajectory models, NLP search, compliance features
**Researched:** 2026-01-25
**Confidence:** MEDIUM (based on existing architecture analysis + current ML serving patterns)

---

## Executive Summary

This document analyzes how RNN trajectory models, NLP query parsing, and compliance features integrate with Headhunter's existing microservices architecture. The current system uses Firebase Cloud Functions for search orchestration with PostgreSQL/pgvector for retrieval and Gemini/Together AI for LLM reranking. New intelligence features should follow the existing Model-as-Service pattern while introducing dedicated services for ML inference.

**Key Recommendations:**
1. **RNN Trajectory Model**: Deploy as a dedicated Cloud Run service (`hh-trajectory-svc`) with model serving via TensorFlow Serving or TorchServe
2. **NLP Query Parsing**: Integrate into existing `hh-search-svc` as a pre-processing step using a fine-tuned transformer model
3. **Anonymization Layer**: Implement as middleware in Cloud Functions before candidate data reaches search results
4. **Audit Logging**: Extend existing `AuditLogger` class with new compliance-specific event types

---

## Current Architecture Analysis

### Existing Search Pipeline

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          Current Search Flow                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. QUERY ENTRY                                                              │
│     └─> Firebase Cloud Function: engineSearch                                │
│         └─> LegacyEngine.search()                                            │
│                                                                              │
│  2. JOB CLASSIFICATION                                                       │
│     └─> JobClassificationService.classifyJob()                               │
│         └─> Gemini 2.5 Flash (function + level extraction)                   │
│                                                                              │
│  3. RETRIEVAL (Parallel)                                                     │
│     ├─> Firestore: Function-based filtering                                  │
│     └─> PostgreSQL/pgvector: Vector similarity search                        │
│                                                                              │
│  4. SCORING (8 Signals)                                                      │
│     ├─> function_score, vector_score, company_score, level_score             │
│     ├─> specialty_score, tech_stack_score, function_title_score              │
│     └─> trajectory_score (basic: step-up/step-down detection)                │
│                                                                              │
│  5. LLM RERANKING                                                            │
│     └─> GeminiRerankingService.rerank()                                      │
│         └─> Two-pass: Quick Filter → Deep Rank (batched)                     │
│                                                                              │
│  6. RESPONSE                                                                 │
│     └─> CandidateMatch[] with scores, rationale, match_metadata              │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Existing Services Inventory

| Service | Port | Current Role | v2.0 Integration Point |
|---------|------|--------------|------------------------|
| `hh-search-svc` | 7102 | Hybrid search, pgvector | NLP query parsing entry |
| `hh-rerank-svc` | 7103 | Redis cache, LLM reranking | Trajectory scores input |
| `hh-embed-svc` | 7101 | Embedding generation | Training data extraction |
| `hh-enrich-svc` | 7108 | Profile enrichment | Career history extraction |
| Cloud Functions | N/A | Search orchestration | Anonymization middleware |

### Key Integration Constraints

1. **Latency Budget**: p95 target of 1.2s total; reranking budget 350ms
2. **Current Scoring**: 8 signals already computed in `LegacyEngine`
3. **Trajectory Calculation**: Basic heuristics exist in `trajectory-calculators.ts`
4. **Audit Logging**: Foundation exists in `audit-logger.ts` with Firestore batch writes
5. **Data Sources**: PostgreSQL (sourcing schema) + Firestore (candidates collection)

---

## Component 1: RNN Trajectory Model

### Purpose

Predict career trajectory patterns from work history sequences to score candidate-role fit beyond simple step-up/step-down heuristics.

### Model Architecture Options

| Approach | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| **LSTM** | Proven for sequences, interpretable | Higher latency, training complexity | RECOMMENDED for v1 |
| **Transformer** | Better long-range dependencies | Overkill for 5-10 job sequence | Future consideration |
| **GRU** | Faster than LSTM, similar accuracy | Less proven in career domain | Alternative option |

**Rationale:** Based on [career trajectory prediction research](https://dl.acm.org/doi/abs/10.1145/3490725.3490753), LSTM networks effectively capture job sequence patterns. The existing `trajectory-calculators.ts` provides a solid baseline to compare against.

### Proposed Service: `hh-trajectory-svc`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      hh-trajectory-svc Architecture                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌──────────────────┐    ┌─────────────────────┐        │
│  │ /predict    │───>│ Feature Extractor │───>│ LSTM Model (TF/PT)  │        │
│  │ POST        │    │ (title→embedding) │    │ Hidden: 128-256     │        │
│  └─────────────┘    └──────────────────┘    │ Layers: 2           │        │
│        │                                     │ Output: [0,1] score │        │
│        │            ┌──────────────────┐    └─────────────────────┘        │
│        └───────────>│ Response Cache   │                                    │
│                     │ (Redis, 1hr TTL) │                                    │
│                     └──────────────────┘                                    │
│                                                                             │
│  Inputs:                                                                    │
│  - candidate_id: string                                                     │
│  - title_sequence: string[] (chronological)                                 │
│  - target_role: { function, level, title }                                  │
│                                                                             │
│  Outputs:                                                                   │
│  - trajectory_fit: number (0-1)                                             │
│  - trajectory_type: "upward" | "lateral" | "downward" | "pivot"             │
│  - velocity: "fast" | "normal" | "slow"                                     │
│  - confidence: number (0-1)                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Integration with Existing Search

**Option A: Inline Scoring (Synchronous)** - RECOMMENDED
- Call `hh-trajectory-svc` during Stage 2 (Scoring) in `LegacyEngine`
- Replace `_trajectory_score` heuristic with ML prediction
- Latency impact: +50-100ms (batch prediction for top 100 candidates)

```typescript
// In legacy-engine.ts, after specialty/tech-stack scoring
const trajectoryScores = await trajectoryService.batchPredict(
  candidates.map(c => ({
    candidate_id: c.candidate_id,
    title_sequence: extractTitleSequence(c),
    target_role: { function: targetClassification.function, level: targetClassification.level }
  }))
);

candidates = candidates.map((c, i) => ({
  ...c,
  _trajectory_score: trajectoryScores[i].trajectory_fit,
  _trajectory_metadata: trajectoryScores[i]
}));
```

**Option B: Pre-computed Scores (Asynchronous)**
- Compute trajectory scores during enrichment and store in PostgreSQL
- Pros: Zero search latency impact
- Cons: Scores not role-specific; requires job matrix pre-computation

### Training Data Pipeline

```
┌────────────────────────────────────────────────────────────────────────────┐
│                     Training Data Pipeline                                  │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  1. EXTRACTION (from PostgreSQL sourcing.candidates)                       │
│     └─> Work history: intelligent_analysis.work_history                    │
│     └─> Titles: current_title, previous_titles                             │
│     └─> Outcome labels: placement data (if available) OR synthetic         │
│                                                                            │
│  2. LABELING STRATEGY                                                      │
│     ├─> Positive (successful trajectory): Senior→Lead, Mid→Senior          │
│     ├─> Negative (unlikely fit): VP→Senior IC, Manager→Junior              │
│     └─> Synthetic generation from recruiter domain knowledge               │
│                                                                            │
│  3. TRAINING                                                               │
│     └─> Cloud Run Job or Vertex AI Training                                │
│     └─> Weekly retraining with new enrichment data                         │
│                                                                            │
│  4. MODEL SERVING                                                          │
│     └─> TensorFlow Serving or TorchServe on Cloud Run                      │
│     └─> Model versioning via Cloud Storage                                 │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### Model Serving Infrastructure

**Recommended Stack:**
- **Serving Framework**: TensorFlow Serving (mature, low-latency) or TorchServe
- **Container**: Cloud Run with GPU (optional) or CPU-optimized
- **Caching**: Redis (existing infrastructure) for prediction caching
- **Model Storage**: Cloud Storage with versioning

**Deployment Pattern**: Following [Model-as-Service patterns](https://www.anyscale.com/blog/serving-ml-models-in-production-common-patterns), wrap the LSTM model as an independent gRPC/REST service.

---

## Component 2: NLP Query Parsing

### Purpose

Extract structured intent from natural language job searches to improve retrieval precision.

### Query Classification Taxonomy

```
Query Types:
├── ROLE_SEARCH: "Senior Backend Engineer"
│   └─> Extract: function=engineering, level=senior, specialty=backend
│
├── SKILLS_SEARCH: "Python developer with AWS experience"
│   └─> Extract: skills=[python, aws], function=engineering
│
├── COMPANY_SEARCH: "Product managers from FAANG"
│   └─> Extract: function=product, company_filter=faang
│
├── COMBINED: "Senior React developer for fintech startup"
│   └─> Extract: level=senior, skills=[react], industry=fintech, stage=startup
│
└── PERSON_SEARCH: "Maria Silva LinkedIn"
    └─> Redirect to name-based lookup
```

### Model Architecture

**Recommended: Fine-tuned BERT/RoBERTa with DIET-style multi-task head**

Based on [intent classification research](https://labelyourdata.com/articles/machine-learning/intent-classification), using a transformer encoder with dual classification heads provides:
- Intent classification (query type)
- Entity extraction (skills, level, function, companies)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        NLP Query Parser Architecture                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Input: "Senior backend engineer with Python and AWS for fintech"          │
│         ↓                                                                   │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │ Tokenizer (BERT WordPiece)                                        │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│         ↓                                                                   │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │ BERT Encoder (distilbert-base-uncased for latency)               │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│         ↓                         ↓                                         │
│  ┌──────────────────┐    ┌──────────────────────┐                          │
│  │ Intent Head      │    │ Entity Head (NER)     │                          │
│  │ [CLS] → softmax  │    │ Token → BIO tags      │                          │
│  └──────────────────┘    └──────────────────────┘                          │
│         ↓                         ↓                                         │
│  intent: ROLE_SEARCH     entities: {                                        │
│                            level: "senior",                                 │
│                            specialty: "backend",                            │
│                            skills: ["python", "aws"],                       │
│                            industry: "fintech"                              │
│                          }                                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Integration Points

**Location: `hh-search-svc` Pre-processing**

```typescript
// In search-service.ts, at start of hybridSearch()
async hybridSearch(context: SearchContext, request: HybridSearchRequest): Promise<HybridSearchResponse> {
  // NEW: NLP parsing before existing logic
  const parsedQuery = await this.queryParser.parse(request.jobDescription || request.query);

  // Augment request with extracted entities
  const enrichedRequest: HybridSearchRequest = {
    ...request,
    filters: {
      ...request.filters,
      skills: [...(request.filters?.skills || []), ...(parsedQuery.skills || [])],
      seniorityLevels: parsedQuery.level ? [parsedQuery.level] : request.filters?.seniorityLevels,
    },
    roleType: parsedQuery.intent === 'EXECUTIVE_SEARCH' ? 'executive' : request.roleType,
    metadata: {
      ...request.metadata,
      nlpParsed: true,
      extractedEntities: parsedQuery.entities
    }
  };

  // Continue with existing flow...
}
```

### Deployment Options

| Option | Latency | Cost | Complexity | Recommendation |
|--------|---------|------|------------|----------------|
| **Embedded in hh-search-svc** | ~20ms | Low | Medium | RECOMMENDED |
| **Separate microservice** | ~50ms (network) | Medium | High | For scale |
| **LLM-based (Gemini)** | ~200ms | High | Low | Prototyping only |

**Recommendation**: Embed the query parser directly in `hh-search-svc` using a quantized DistilBERT model for minimal latency. The model can be loaded at service startup.

### Training Data Requirements

```
Labeled examples needed: ~5,000-10,000 queries
Sources:
├── Historical search logs (if available)
├── Synthetic generation from job title corpus
├── Recruiter annotation of sample queries
└── Augmentation via paraphrasing

Format:
{
  "query": "Senior React developer with 5+ years experience",
  "intent": "ROLE_SEARCH",
  "entities": {
    "level": "senior",
    "specialty": "frontend",
    "skills": ["react"],
    "experience_years": "5+"
  }
}
```

---

## Component 3: Anonymization Layer

### Purpose

Reduce hiring bias by removing identifying information from candidate data before recruiter review.

### Anonymization Strategy

Based on [AI bias reduction research](https://www.tandfonline.com/doi/full/10.1080/09585192.2025.2480617), implementing blind screening through data anonymization is a proven approach.

**Fields to Anonymize:**

| Field | Anonymization Method | Reversible |
|-------|---------------------|------------|
| `name` | Hash + "Candidate A/B/C" | Yes (admin only) |
| `email` | Remove entirely | Yes (admin only) |
| `linkedin_url` | Remove from results | Yes (admin only) |
| `photo_url` | Remove entirely | Yes (admin only) |
| `gender` indicators | NLP detection + removal | No |
| `age` indicators | Graduation year → "X years ago" | Partial |
| `ethnicity` indicators | Name-based inference + masking | N/A |

### Architecture: Middleware Pattern

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Anonymization Middleware Flow                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Search Results (from LegacyEngine)                                         │
│         ↓                                                                   │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │ AnonymizationService.anonymize(results, context)                  │      │
│  │                                                                   │      │
│  │ Inputs:                                                           │      │
│  │ - results: CandidateMatch[]                                       │      │
│  │ - context: { userId, orgId, anonymizationLevel }                  │      │
│  │                                                                   │      │
│  │ Processing:                                                       │      │
│  │ 1. Check org settings for anonymization level                     │      │
│  │ 2. Generate stable pseudonyms (hash-based for consistency)        │      │
│  │ 3. Strip PII fields based on level                                │      │
│  │ 4. Transform age-related data                                     │      │
│  │ 5. Log anonymization event to audit trail                         │      │
│  │                                                                   │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│         ↓                                                                   │
│  Anonymized Results (to frontend)                                           │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │ Admin Reveal Flow (when candidate shortlisted)                    │      │
│  │                                                                   │      │
│  │ 1. Recruiter clicks "Reveal Identity"                             │      │
│  │ 2. AnonymizationService.reveal(candidateId, userId)               │      │
│  │ 3. Audit log: IDENTITY_REVEALED event                             │      │
│  │ 4. Return full candidate data                                     │      │
│  │                                                                   │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Anonymization Levels

```typescript
enum AnonymizationLevel {
  NONE = 0,           // Full data (admin mode)
  PARTIAL = 1,        // Names visible, no contact info
  STANDARD = 2,       // Pseudonyms, no PII, ages masked
  STRICT = 3          // Everything anonymized, skills/experience only
}

// Organization settings in Firestore
interface OrgSettings {
  anonymization_level: AnonymizationLevel;
  reveal_requires_approval: boolean;
  reveal_audit_required: boolean;
}
```

### Implementation Location

**Cloud Functions Middleware** (in `engine-search.ts` or new `anonymization-middleware.ts`):

```typescript
// After search results, before response
const results = await engine.search(job, options, vectorResults);

// Apply anonymization based on org settings
const orgSettings = await getOrgSettings(context.orgId);
const anonymizedResults = await anonymizationService.anonymize(
  results.matches,
  {
    level: orgSettings.anonymization_level,
    userId: context.userId,
    requestId: context.requestId
  }
);

// Audit log the anonymization
await auditLogger.log(AuditAction.SEARCH_ANONYMIZED, {
  userId: context.userId,
  resourceType: 'search',
  details: {
    result_count: anonymizedResults.length,
    anonymization_level: orgSettings.anonymization_level
  }
});

return { ...results, matches: anonymizedResults };
```

---

## Component 4: Compliance Audit Logging

### Current State Analysis

The existing `AuditLogger` class provides:
- Batch writing to Firestore (`audit_logs` collection)
- Event types for auth, data access, search operations
- Sanitization of sensitive data
- Report generation

### Required Extensions for v2.0

**New Audit Event Types:**

```typescript
// Extend existing AuditAction enum
export enum AuditAction {
  // ... existing events ...

  // Bias & Fairness (v2.0)
  SEARCH_ANONYMIZED = "SEARCH_ANONYMIZED",
  IDENTITY_REVEALED = "IDENTITY_REVEALED",
  BIAS_FLAG_TRIGGERED = "BIAS_FLAG_TRIGGERED",

  // ML Model Decisions (v2.0)
  TRAJECTORY_PREDICTION = "TRAJECTORY_PREDICTION",
  QUERY_PARSED = "QUERY_PARSED",
  MODEL_OVERRIDE = "MODEL_OVERRIDE",

  // Compliance (v2.0)
  GDPR_DATA_EXPORT = "GDPR_DATA_EXPORT",
  GDPR_DELETION_REQUEST = "GDPR_DELETION_REQUEST",
  CONSENT_RECORDED = "CONSENT_RECORDED",
  CONSENT_WITHDRAWN = "CONSENT_WITHDRAWN",

  // Decision Explainability (v2.0)
  RANKING_EXPLANATION_VIEWED = "RANKING_EXPLANATION_VIEWED",
  DECISION_CHALLENGED = "DECISION_CHALLENGED",
}
```

### Compliance-Specific Logging

Based on [GDPR ATS requirements](https://www.manatal.com/blog/gdpr-compliant), audit trails must demonstrate accountability.

```typescript
// New compliance logger extension
class ComplianceAuditLogger extends AuditLogger {

  /**
   * Log ML model decision for explainability
   */
  async logModelDecision(
    modelType: 'trajectory' | 'query_parser' | 'reranker',
    input: any,
    output: any,
    candidateId: string,
    userId: string
  ): Promise<void> {
    await this.log(AuditAction.TRAJECTORY_PREDICTION, {
      userId,
      resourceType: 'ml_model',
      resourceId: candidateId,
      details: {
        model_type: modelType,
        model_version: this.getModelVersion(modelType),
        input_summary: this.summarizeInput(input),
        output: output,
        timestamp: new Date().toISOString()
      },
      success: true
    });
  }

  /**
   * Log anonymization with reversibility tracking
   */
  async logAnonymization(
    candidateIds: string[],
    level: AnonymizationLevel,
    userId: string,
    pseudonymMap: Map<string, string>
  ): Promise<void> {
    await this.log(AuditAction.SEARCH_ANONYMIZED, {
      userId,
      resourceType: 'anonymization',
      details: {
        candidate_count: candidateIds.length,
        level: level,
        pseudonym_mapping_stored: true,  // For admin reveal
        retention_days: 90
      },
      success: true
    });
  }

  /**
   * Log identity reveal for bias audit
   */
  async logIdentityReveal(
    candidateId: string,
    userId: string,
    reason: string
  ): Promise<void> {
    await this.log(AuditAction.IDENTITY_REVEALED, {
      userId,
      resourceType: 'candidate',
      resourceId: candidateId,
      details: {
        reason: reason,
        timestamp: new Date().toISOString(),
        requires_review: true  // Flag for compliance review
      },
      success: true
    });
  }
}
```

### Audit Report Enhancements

```typescript
interface ComplianceReport extends AuditReport {
  // Bias metrics
  anonymization_rate: number;          // % of searches with anonymization
  reveal_rate: number;                 // % of anonymized candidates revealed
  reveal_reasons: Record<string, number>;

  // ML transparency
  model_decisions_logged: number;
  decision_challenges: number;
  challenge_resolution_rate: number;

  // GDPR compliance
  data_export_requests: number;
  deletion_requests: number;
  consent_status: {
    active: number;
    withdrawn: number;
    expired: number;
  };
}
```

---

## Data Flow Architecture (Combined)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         v2.0 Advanced Intelligence Data Flow                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────┐                                                            │
│  │ Search Request  │                                                            │
│  │ (job desc/query)│                                                            │
│  └────────┬────────┘                                                            │
│           │                                                                     │
│           ▼                                                                     │
│  ┌────────────────────┐     ┌─────────────────────┐                            │
│  │ 1. QUERY PARSING   │────>│ NLP Parser          │                            │
│  │    (NEW)           │     │ (DistilBERT)        │                            │
│  └────────┬───────────┘     └─────────────────────┘                            │
│           │ Extracted: level, function, skills, industry                        │
│           ▼                                                                     │
│  ┌────────────────────┐                                                        │
│  │ 2. RETRIEVAL       │                                                        │
│  │    (Existing)      │                                                        │
│  │    - pgvector      │                                                        │
│  │    - Firestore     │                                                        │
│  └────────┬───────────┘                                                        │
│           │ ~200-500 candidates                                                 │
│           ▼                                                                     │
│  ┌────────────────────┐     ┌─────────────────────┐                            │
│  │ 3. SCORING         │────>│ hh-trajectory-svc   │                            │
│  │    (Enhanced)      │     │ (LSTM Model)        │                            │
│  │    - 8 signals     │     └─────────────────────┘                            │
│  │    - ML trajectory │                                                        │
│  └────────┬───────────┘                                                        │
│           │ Scored candidates with trajectory_fit                               │
│           ▼                                                                     │
│  ┌────────────────────┐                                                        │
│  │ 4. RERANKING       │                                                        │
│  │    (Existing)      │                                                        │
│  │    - Gemini 2-pass │                                                        │
│  └────────┬───────────┘                                                        │
│           │ Top 50 reranked                                                     │
│           ▼                                                                     │
│  ┌────────────────────┐     ┌─────────────────────┐                            │
│  │ 5. ANONYMIZATION   │────>│ Anonymization Svc   │                            │
│  │    (NEW)           │     │ (Middleware)        │                            │
│  └────────┬───────────┘     └─────────────────────┘                            │
│           │ Pseudonymized results                                               │
│           ▼                                                                     │
│  ┌────────────────────┐     ┌─────────────────────┐                            │
│  │ 6. AUDIT LOGGING   │────>│ ComplianceAuditLog  │                            │
│  │    (Enhanced)      │     │ (Firestore batch)   │                            │
│  └────────┬───────────┘     └─────────────────────┘                            │
│           │                                                                     │
│           ▼                                                                     │
│  ┌─────────────────┐                                                            │
│  │ Search Response │                                                            │
│  │ (anonymized)    │                                                            │
│  └─────────────────┘                                                            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Suggested Build Order

Based on dependencies and existing infrastructure:

### Phase 1: Foundation (Weeks 1-2)
1. **Extend Audit Logging** - Low risk, enables compliance tracking for all subsequent features
2. **Anonymization Middleware** - Can be toggled per-org, minimal search impact

### Phase 2: NLP Query Parsing (Weeks 3-4)
3. **Query Parser Model Training** - Requires labeled data collection
4. **Integration into hh-search-svc** - Replace/augment existing job classification

### Phase 3: Trajectory Model (Weeks 5-8)
5. **Training Data Pipeline** - Extract work histories from PostgreSQL
6. **LSTM Model Training** - Vertex AI or custom training job
7. **hh-trajectory-svc Deployment** - Cloud Run with model serving
8. **Integration with Scoring** - Replace heuristic `_trajectory_score`

### Phase 4: Integration & Testing (Weeks 9-10)
9. **End-to-end testing** - Latency validation, accuracy benchmarks
10. **A/B testing framework** - Compare ML vs heuristic trajectory scoring

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Trajectory model latency exceeds budget | Medium | High | Batch prediction, aggressive caching |
| NLP parser fails on edge cases | High | Medium | Fallback to existing classification |
| Anonymization reveals patterns | Low | High | Randomize pseudonym assignment |
| Audit log volume overwhelms Firestore | Medium | Medium | Batch writes, retention policies |
| Training data insufficient | Medium | High | Synthetic data generation, transfer learning |

---

## Technology Recommendations

### RNN Trajectory Service
- **Framework**: TensorFlow 2.x or PyTorch
- **Serving**: TensorFlow Serving (mature) or TorchServe
- **Infrastructure**: Cloud Run (CPU) initially, GPU if latency critical
- **Caching**: Redis (existing) with 1-hour TTL

### NLP Query Parser
- **Model**: DistilBERT or DistilRoBERTa (quantized)
- **Framework**: Hugging Face Transformers
- **Deployment**: Embedded in `hh-search-svc` (no separate service)
- **Latency Target**: <50ms

### Anonymization
- **Implementation**: TypeScript middleware in Cloud Functions
- **Pseudonym Generation**: SHA-256 hash of (candidate_id + session_salt)
- **Storage**: Firestore `anonymization_sessions` collection

### Audit Logging
- **Existing**: Firestore batch writes (keep)
- **Enhancement**: Add BigQuery export for long-term analytics
- **Retention**: 90 days in Firestore, 7 years in BigQuery (compliance)

---

## Sources

- [Career Trajectory Prediction with Neural Networks](https://dl.acm.org/doi/abs/10.1145/3490725.3490753)
- [NEMO: Next Career Move Prediction](http://team-net-work.org/pdfs/LiJTYHC_WWW17.pdf)
- [Intent Classification: 2025 Techniques](https://labelyourdata.com/articles/machine-learning/intent-classification)
- [Intent Classification in 2026](https://research.aimultiple.com/intent-classification/)
- [Model Serving Patterns](https://www.anyscale.com/blog/serving-ml-models-in-production-common-patterns)
- [Microservices for AI Applications 2025](https://medium.com/@meeran03/microservices-architecture-for-ai-applications-scalable-patterns-and-2025-trends-5ac273eac232)
- [AI Bias Reduction in Recruitment](https://www.tandfonline.com/doi/full/10.1080/09585192.2025.2480617)
- [Fairness in AI-Driven Recruitment](https://arxiv.org/html/2405.19699v3)
- [GDPR-Compliant ATS Architecture](https://www.manatal.com/blog/gdpr-compliant)
- [GDPR Recruitment Compliance 2025](https://atzcrm.com/gdpr-recruitment-candidate-data/)
