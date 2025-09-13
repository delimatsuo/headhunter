# Headhunter System Architecture

> Update (2025‑09‑11): The authoritative architecture uses a single‑pass Together AI model (Qwen 2.5 32B Instruct) to produce the full structured profile including explicit skills and inferred skills with confidence/evidence. Low‑confidence profiles are flagged and demoted in ranking but remain searchable. Embeddings are generated from enriched profile text; one unified search pipeline blends ANN recall with structured signals (skills/experience/analysis_confidence). Any multi‑stage references below (Llama 3.2 3B → Qwen Coder 32B → Vertex) are legacy and retained for context only.

## Updated Architecture Summary

- Stage 1 Enrichment (Single Pass): Qwen 2.5 32B Instruct on Together AI (env: `TOGETHER_MODEL_STAGE1`, default `Qwen/Qwen2.5-32B-Instruct`).
- Outputs: structured profile JSON; explicit vs inferred skills with confidence and evidence; `analysis_confidence` and `quality_flags`.
- Storage: Firestore (`candidates/`, `enriched_profiles/`).
- Embeddings: Gemini Embeddings as default (US region), Vertex fallback; vectors stored in `candidate_embeddings`.
- Search: Unified pipeline — ANN recall (Cloud SQL + pgvector) + Together Rerank + structured signals → one ranked list with explainability.
- UI: React SPA on Firebase Hosting calling callable Functions; ensure callable exports for `skillAwareSearch` and `getCandidateSkillAssessment`.
- Functions: CRUD/search/upload; remove/guard Gemini enrichment; enrichment lives in Python processors.

### No Mock Fallbacks
- External services (Vertex embeddings, Gemini enrichment) do not fall back to mock/deterministic responses.
- When disabled or unavailable, errors are surfaced to clients; development can opt in to deterministic vectors only via `EMBEDDING_PROVIDER=local`.

## UX & IA (Information Architecture)

- People Search: search by name or LinkedIn URL → opens the Candidate Page.
- Job Search: paste a JD → up to 50 results (expandable). Rows are minimal; click opens Candidate Page.
- Candidate Page: full Skill Map (explicit + inferred with confidence and verification tags), Pre‑Interview Analysis (on‑demand), compact timeline, resume freshness badges, LinkedIn link.

Row content (minimal): name, current role @ company, years/level, composite score, freshness badge, LinkedIn link, and a small “Low profile depth” badge when applicable.

## Search Pipeline & Recall Safeguards

- ANN recall via embeddings (pgvector planned) unioned with deterministic recall (exact/phrase matches on title/company; name for people search), then composite re‑rank.
- Deterministic boost for exact title/company matches; keep analysis_confidence demotion but raise the floor when deterministic signals present.
- Optional quota (e.g., 10–20%) for a “Potential matches (low profile depth)” bucket.

## LLM Usage

- Single pass (ingestion/update): Qwen 2.5 32B generates structured profile with explicit/inferred skills, evidence, and `analysis_confidence`. Embeddings are generated from enriched text.
- Search time: no LLM calls; ANN + deterministic re‑rank only.
- Pre‑Interview Analysis (on‑demand): Qwen generates summary/strengths/red flags and signal chips with evidence; cached with TTL and invalidated on profile change.

## Candidate Data: LinkedIn & Freshness

- `linkedin_url` extracted from CSV when present; otherwise regex from resume text (linkedin.com/in/…).
- `resume_updated_at` from file metadata if available; else parsed “Last updated” line; else `processed_at` labeled as analysis date.
- Freshness badges: Recent (<6m), Stale (6–18m), Very stale (>18m).
- Stale Profiles view (manual initiate, auto refresh): list candidates beyond freshness threshold (configurable 18–24 months). Actions: Open LinkedIn (new tab), Upload updated resume, or Skip. After upload, backend auto-extracts → validates JSON → re‑embeds (Gemini default) → updates `candidate_sections` and `candidate_embeddings`, freshness, and audit logs.

## Future (not in current scope)

- Stale Profile Queue: nightly list of profiles with `resume_updated_at` > 18 months; admin console actions to open LinkedIn, request update, or upload a new resume to reprocess. No automated scraping.


## 🎯 Core Design Principle

Single‑pass enrichment + unified search. The system produces a complete structured profile in one pass (Qwen 2.5 32B), generates embeddings from the enriched text, and serves a single search pipeline that blends ANN recall with deterministic re‑ranking signals (skill match, confidence, vector similarity, experience). On‑demand pre‑interview analysis is generated only when a recruiter opens a Candidate Page.

## System Components

### Current System Components

- Processing: Python processors calling Together AI (Qwen 2.5 32B) for single‑pass enrichment; JSON repair + schema validation.
- Storage: Firestore for structured profiles; `candidate_embeddings` for vectors (Gemini Embeddings default, Vertex fallback).
- Search: Unified pipeline (ANN recall planned on pgvector) + deterministic re‑rank with analysis_confidence demotion and recall safeguards.
- UI: React SPA (Firebase Hosting) with minimal list → Candidate Page; callables for search and assessment.
- Optional: Cloud Run ANN service (planned), Cloud Run enrichment worker (future).

## Legacy Architecture (Archive)

The following multi‑stage architecture content is retained for historical context and is not the current design.

### 2. Data Storage Layer (Multi-Database Architecture)

Distributed storage optimized for both structured data and semantic search:

```
┌──────────────────────────────────────────────────┐
│              STORAGE LAYER                        │
├──────────────────────────────────────────────────┤
│  Structured Data: Firestore                     │
│  Vector Storage: Cloud SQL + pgvector           │
│  File Storage: Cloud Storage                    │
│  Configuration: Secret Manager                  │
│  Authentication: Firebase Auth                  │
│  API: Cloud Functions + Cloud Run              │
│  Hosting: Firebase Hosting                      │
└──────────────────────────────────────────────────┘
```

**Storage Collections:**
- `enhanced_candidates` - Comprehensive candidate profiles with 15+ detailed fields
- `processing_jobs` - Batch processing status and metrics
- `search_queries` - Job descriptions and search optimization data
- `embeddings_metadata` - Vector database synchronization status

**Cloud SQL Tables:**
- `candidate_embeddings` - pgvector storage for semantic search
- `search_cache` - Pre-computed similarity matches
- `performance_metrics` - Processing and search performance tracking

### 3. Semantic Search & API Layer

Intelligent search system for recruiter workflows:

```
┌──────────────────────────────────────────────────┐
│              SEARCH & API LAYER                   │
├──────────────────────────────────────────────────┤
│  Search API: FastAPI + Cloud Run                │
│  Vector Search: pgvector + cosine similarity    │
│  Embeddings: VertexAI text-embedding-004        │
│  Results Ranking: Hybrid semantic + keyword     │
│  CRUD Operations: Firestore + Cloud SQL sync    │
└──────────────────────────────────────────────────┘
```

**API Endpoints:**
- `/search/semantic` - Vector similarity search for job descriptions
- `/search/hybrid` - Combined semantic + keyword search
- `/search/skill-aware` - Skill-confidence weighted search with composite ranking
- `/candidates/{id}` - CRUD operations for individual profiles
- `/candidates/batch` - Bulk operations and updates
- `/embeddings/generate` - On-demand embedding generation
- `/processing/status` - Batch processing status and metrics

**Skill-Aware Search Features:**
- **Confidence Weighting**: Skills with higher confidence scores (90%+) weighted more heavily
- **Composite Ranking Algorithm**: 
  - Skill Match: 40% (primary relevance factor)
  - Confidence: 25% (reliability weighting)
  - Vector Similarity: 25% (semantic understanding)
  - Experience Match: 10% (additional context)
- **Evidence-Based Filtering**: Filter candidates based on skill evidence quality
- **Fuzzy Skill Matching**: Synonym support for skill variations (React.js ↔ ReactJS)
- **Category Filtering**: Search within skill categories (technical, soft, leadership, domain)

### 4. Web Interface Layer (React)

Recruiter-focused search and management application:

```
┌──────────────────────────────────────────────────┐
│              WEB INTERFACE                        │
├──────────────────────────────────────────────────┤
│  Framework: React + TypeScript                  │
│  Search UI: Job description → candidate matches │
│  Profile Management: CRUD + LinkedIn sync       │
│  Authentication: Firebase Auth                  │
│  API Client: Fetch + Firebase SDK               │
│  Hosting: Firebase Hosting                      │
└──────────────────────────────────────────────────┘
```

## Data Flow Architecture

```
Step 1: Data Ingestion (Cloud)
==============================
CSV Files → Cloud Storage → Pub/Sub Messages
                ↓
    Candidate Data Batches

Step 2: AI Processing (Together AI Cloud)
=========================================
        Cloud Run Workers
                ↓
    Together AI API (Llama 3.2 3B)
                ↓
    Comprehensive JSON Profiles
                ↓
        VertexAI Embeddings
                ↓
    Vector + Structured Data

Step 3: Dual Storage (Cloud)
============================
    Enhanced Profiles → Firestore
    Vector Embeddings → Cloud SQL (pgvector)
                ↓
        Search Indexing

Step 4: Semantic Search (Cloud + Web)
=====================================
    Job Description Input (Web)
                ↓
      Vector Search API (Cloud Run)
                ↓
    pgvector Similarity Query + Firestore Profile Fetch
                ↓
    Ranked Candidate Matches (Web Display)

Step 5: Profile Management (CRUD)
=================================
    LinkedIn Profile Updates (Web)
                ↓
      Profile Update API (Cloud Run)
                ↓
    Firestore Update + Re-embed + pgvector Sync
                ↓
    Updated Search Results
```

## Comprehensive JSON Data Structure

Generated by Together AI Llama 3.2 3B Instruct Turbo, optimized for recruiter search:

```json
{
  "candidate_id": "unique_id",
  "personal_info": {
    "name": "John Smith",
    "current_title": "Senior Software Engineer",
    "location": "San Francisco, CA",
    "linkedin_url": "https://linkedin.com/in/johnsmith",
    "email": "john@example.com",
    "phone": "+1-555-0123"
  },
  "processing_metadata": {
    "processed_by": "together_ai_llama3.2_3b",
    "processed_at": "2024-01-01T00:00:00Z",
    "processing_time_seconds": 2.3,
    "model_version": "meta-llama/Llama-3.2-3B-Instruct-Turbo",
    "api_cost_dollars": 0.0045,
    "confidence_score": 0.92
  },
  "career_trajectory": {
    "current_level": "senior",
    "progression_speed": "fast",
    "trajectory_type": "technical_leadership",
    "years_total_experience": 12,
    "years_current_role": 3,
    "career_velocity": "accelerating",
    "promotion_frequency": "every_2_3_years",
    "role_transitions": ["IC → Senior IC → Tech Lead"]
  },
  "leadership_scope": {
    "has_leadership": true,
    "team_size_managed": 8,
    "leadership_level": "tech_lead",
    "leadership_style": "servant_leadership",
    "direct_reports": 3,
    "cross_functional_collaboration": "high",
    "mentorship_experience": "extensive"
  },
  "company_pedigree": {
    "current_company": "Meta",
    "company_tier": "faang",
    "company_list": ["Meta", "Airbnb", "Medium"],
    "company_trajectory": "scaling_up",
    "stability_pattern": "strategic_moves",
    "industry_focus": ["social_media", "marketplaces", "content_platforms"],
    "company_stage_preference": "growth_stage"
  },
  "technical_skills": {
    "primary_languages": ["Python", "TypeScript", "Go"],
    "frameworks": ["React", "Django", "FastAPI", "Node.js"],
    "cloud_platforms": ["AWS", "GCP"],
    "databases": ["PostgreSQL", "Redis", "MongoDB"],
    "tools": ["Docker", "Kubernetes", "Git", "Jenkins"],
    "specializations": ["ML/AI", "System Design", "API Architecture"],
    "skill_depth": "expert",
    "learning_velocity": "high",
    "technical_breadth": "full_stack"
  },
  "domain_expertise": {
    "industries": ["fintech", "social_media", "e-commerce"],
    "business_functions": ["product_engineering", "platform_development"],
    "domain_depth": "expert",
    "vertical_knowledge": ["payments", "user_engagement", "scalability"],
    "regulatory_experience": ["SOX", "GDPR", "PCI_DSS"]
  },
  "soft_skills": {
    "communication": "exceptional",
    "leadership": "strong",
    "collaboration": "exceptional",
    "problem_solving": "expert",
    "adaptability": "high",
    "emotional_intelligence": "high",
    "conflict_resolution": "strong",
    "presentation_skills": "strong"
  },
  "cultural_signals": {
    "work_style": "collaborative_autonomous",
    "cultural_strengths": ["innovation", "ownership", "mentorship"],
    "values_alignment": ["growth_mindset", "customer_obsession", "excellence"],
    "red_flags": [],
    "team_dynamics": "positive_influence",
    "change_adaptability": "thrives_in_change",
    "feedback_receptiveness": "high"
  },
  "compensation_insights": {
    "current_salary_range": "$180k-220k",
    "total_compensation": "$280k-350k",
    "salary_expectations": "market_rate",
    "equity_preference": "growth_stage",
    "compensation_motivators": ["equity_upside", "base_growth"],
    "negotiation_flexibility": "moderate"
  },
  "recruiter_insights": {
    "engagement_history": "responsive",
    "placement_likelihood": "high",
    "best_fit_roles": ["Senior Staff Engineer", "Engineering Manager", "Tech Lead"],
    "cultural_fit_companies": ["high_growth_startups", "tech_forward_enterprises"],
    "interview_strengths": ["technical_depth", "leadership_examples"],
    "potential_concerns": ["relocation_flexibility"],
    "recruiter_notes": "Strong technical leader with fintech domain expertise"
  },
  "search_optimization": {
    "primary_keywords": ["python", "fintech", "technical_leadership", "aws", "machine_learning"],
    "secondary_keywords": ["payments", "scalability", "mentorship", "full_stack"],
    "skill_tags": ["senior_engineer", "tech_lead", "fintech_expert", "ml_engineer"],
    "location_tags": ["san_francisco", "bay_area", "remote_friendly"],
    "industry_tags": ["fintech", "payments", "financial_services"],
    "seniority_indicators": ["8_plus_years", "technical_leadership", "team_management"]
  },
  "matching_profiles": {
    "ideal_role_types": ["staff_engineer", "engineering_manager", "principal_engineer"],
    "company_size_preference": ["series_b_to_ipo", "100_to_1000_employees"],
    "technology_stack_match": 0.95,
    "leadership_readiness": 0.88,
    "domain_transferability": 0.82,
    "cultural_fit_score": 0.91
  },
  "executive_summary": {
    "one_line_pitch": "Senior full-stack engineer with fintech expertise and proven technical leadership track record",
    "key_differentiators": ["Domain expertise in payments", "Technical mentorship", "Scaling experience"],
    "ideal_next_role": "Staff Engineer or Engineering Manager at growth-stage fintech",
    "career_narrative": "Progressive technical leadership journey from IC to team lead with strong fintech domain knowledge",
    "overall_rating": 92,
    "recommendation_tier": "top_10_percent"
  },
  "embeddings_metadata": {
    "embedding_model": "text-embedding-004",
    "embedding_dimensions": 768,
    "last_embedded": "2024-01-01T00:00:00Z",
    "similarity_cache_updated": "2024-01-01T00:00:00Z"
  }
}
```

## Semantic Search Architecture

### Vector Generation Pipeline
```
Resume + Comments Text
        ↓
Together AI Profile Generation
        ↓
Profile Text Concatenation
        ↓
VertexAI text-embedding-004
        ↓
768-dimensional Vector
        ↓
Cloud SQL pgvector Storage
```

### Search Query Flow
```
Job Description Input
        ↓
VertexAI Embedding Generation
        ↓
pgvector Cosine Similarity Query
        ↓
Top-K Candidate Vector Matches
        ↓
Firestore Profile Enrichment
        ↓
Ranked Results with Similarity Scores
```

## Performance Characteristics

### Cloud Processing (Together AI + Cloud Run)
- **Model Loading**: ~0.5 seconds (cloud-hosted)
- **Per Candidate**: 2-3 seconds comprehensive analysis
- **Batch Processing**: 1,500+ candidates/hour with parallel workers
- **Cost per Candidate**: ~$0.005 (Together AI + GCP)
- **Embedding Generation**: ~0.3 seconds per profile
- **Vector Search Latency**: <100ms for 10K+ candidates

### Scalability Metrics
- **Concurrent Workers**: Auto-scaling 1-100 Cloud Run instances
- **Daily Processing Capacity**: 50,000+ candidates
- **Search Performance**: <200ms response time for complex queries
- **Storage Capacity**: Unlimited (Firestore + Cloud SQL)

## Cost Analysis

### Per-Candidate Processing Costs
- **Together AI API**: ~$0.004 per candidate
- **VertexAI Embeddings**: ~$0.0002 per candidate
- **Cloud Run Processing**: ~$0.0008 per candidate
- **Storage (Firestore + Cloud SQL)**: ~$0.0001 per candidate
- **Total**: ~$0.005 per candidate

### Monthly Operational Costs (20,000 candidates)
- **AI Processing**: ~$100/month
- **Storage & Database**: ~$50/month
- **Compute & Networking**: ~$200/month
- **Total**: ~$350/month for full operation

### Comparison with Alternatives
- **OpenAI GPT-4**: ~$0.15 per candidate (30x more expensive)
- **Google Vertex AI**: ~$0.08 per candidate (16x more expensive)
- **Together AI Llama 3.2**: ~$0.004 per candidate (current choice)

## Security & Privacy Architecture

### Data Privacy Layers

1. **API Key Security**
   - Together AI API keys stored in Google Secret Manager
   - No hardcoded credentials in codebase
   - Automatic key rotation capability

2. **Data Processing Security**
   - HTTPS-only API communication
   - Candidate data encrypted in transit and at rest
   - Processing logs sanitized of PII

3. **Storage Security**
   - Firebase Authentication required for all access
   - Firestore security rules with role-based access
   - Cloud SQL private IP with VPC peering
   - pgvector data encrypted at rest

### Compliance & Governance
- **GDPR**: Right to deletion implemented via CRUD APIs
- **Data Residency**: All processing within specified GCP regions
- **Audit Logging**: Complete processing and access audit trail
- **Access Control**: Firebase Auth + IAM roles

## Deployment & Operations

### Cloud Run Deployment
```bash
# Build and deploy Cloud Run worker
cd cloud_run_worker
gcloud run deploy headhunter-worker \
  --source . \
  --region us-central1 \
  --memory 2Gi \
  --cpu 2 \
  --min-instances 0 \
  --max-instances 100 \
  --concurrency 10

# Deploy Pub/Sub trigger
gcloud pubsub topics create candidate-processing
gcloud eventarc triggers create headhunter-trigger \
  --destination-run-service headhunter-worker \
  --event-filters type=google.cloud.pubsub.topic.v1.messagePublished
```

### Database Setup
```bash
# Create Cloud SQL instance with pgvector
gcloud sql instances create headhunter-vectors \
  --database-version POSTGRES_15 \
  --tier db-standard-2 \
  --region us-central1

# Enable pgvector extension
gcloud sql connect headhunter-vectors --user postgres
CREATE EXTENSION vector;
```

### Monitoring & Observability
- **Cloud Monitoring**: Processing latency and error rates
- **Cloud Logging**: Structured logs with candidate processing status
- **Pub/Sub Monitoring**: Message processing rates and dead letter queues
- **Custom Dashboards**: Candidate processing throughput and search performance

## Technology Stack Summary

| Layer | Technology | Purpose |
|-------|------------|---------|
| AI Processing | Together AI Qwen 2.5 32B | Cloud LLM for single‑pass enrichment |
| Orchestration | Cloud Run + Pub/Sub | Scalable processing workflow |
| Embeddings | VertexAI text-embedding-004 | Semantic search vectors |
| Vector DB | Cloud SQL + pgvector | Fast similarity search |
| Structured Storage | Firestore | Candidate profiles and metadata |
| Configuration | Secret Manager | Secure API key management |
| API Layer | FastAPI + Cloud Run | Search and CRUD endpoints |
| Web UI | React + TypeScript | Recruiter search interface |
| Authentication | Firebase Auth | User management and security |
| Monitoring | Cloud Monitoring + Logging | Operations and debugging |

## Key Architectural Decisions

1. **Why Together AI?**
   - Cost-effective cloud LLM processing
   - No local infrastructure requirements
   - Scalable and reliable API
   - Competitive pricing vs OpenAI/Anthropic

2. **Why Dual Storage (Firestore + Cloud SQL)?**
   - Firestore: Optimal for structured profile data and real-time sync
   - Cloud SQL: Required for pgvector similarity search
   - Best of both worlds for hybrid search workloads

3. **Why VertexAI Embeddings?**
   - High-quality semantic representations
   - Google Cloud native integration
   - Optimized for search and similarity tasks

4. **Why Cloud Run?**
   - Auto-scaling based on demand
   - Pay-per-request pricing model
   - Native integration with Pub/Sub and other GCP services

## Recruiter Workflow Integration

### Primary Use Cases

1. **Job Description Search**
   - Recruiters paste job requirements
   - System generates embeddings and finds similar candidates
   - Results ranked by technical fit and experience level

2. **Profile Updates**
   - Recruiters find updated LinkedIn profiles
   - System re-processes and updates candidate data
   - Embeddings refreshed for improved search accuracy

3. **Batch Processing**
   - CSV uploads trigger Pub/Sub processing
   - Thousands of candidates processed in parallel
   - Real-time status updates via web interface

4. **Advanced Search**
   - Hybrid semantic + keyword search
   - Filtering by seniority, location, skills
   - Export functionality for candidate lists

## Future Enhancements

### Planned Features
- **Multi-language Support**: International candidate processing
- **Real-time Processing**: Streaming profile updates via websockets
- **Advanced Analytics**: Hiring success metrics and model fine-tuning
- **Integration APIs**: ATS system connectors and third-party tools

### Scaling Roadmap
- **Multi-region Deployment**: Global processing with regional data residency
- **Model Fine-tuning**: Custom models trained on recruiter feedback
- **Advanced Search**: Graph-based candidate relationship mapping
- **Performance Optimization**: Sub-50ms search response times

## Conclusion

This architecture provides a production-ready, scalable solution for AI-powered recruitment analytics. The cloud-native design ensures reliable processing of large candidate volumes while maintaining cost efficiency and search performance. The dual-storage approach optimizes both structured data access and semantic search capabilities, enabling sophisticated recruiter workflows at enterprise scale.
