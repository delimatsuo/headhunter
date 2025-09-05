<context>
# Overview
Headhunter v1.1 transforms Ella Executive Search's historical candidate database into an intelligent, semantic search engine. It solves the inefficiency and blind spots of keyword-based ATS queries by deeply analyzing each candidate's experience, leadership scope, and cultural signals, then matching them contextually to new role descriptions. Primary users are recruiters who need to build qualified long-lists in under 30 minutes while improving search quality and unlocking the strategic value of proprietary candidate data.

**Current Status**: Data processing pipeline completed with 29,135 candidates processed and enriched profiles ready for LLM analysis.

# Core Features
- **Candidate ingestion and normalization**: ✅ **COMPLETED** - Local Python pipeline (`data_processor.py`) parses Workable CSV export into enriched JSON profiles using structured data processing. Includes 29,135 candidates with 70,442 recruiter comments merged and optimized for LLM analysis.
- **AI enrichment pipeline**: Cloud Functions invoke Vertex AI Gemini to produce enriched candidate profiles including career arc analysis, standardized role scope, company pedigree, and recruiter takeaways (strengths/red flags). Results stored in Firestore with embeddings in Vertex AI Vector Search.
- **Semantic search UI**: Secure web app where recruiters paste a full job description and receive a ranked list of 10–20 candidates with name, current title, AI summary, and "Why they're a match" bullets.

# User Experience  
- **Persona: Alex (Senior Recruiter)**
  - Goals: Quickly surface the best candidates; fill roles faster; deliver high client value.
  - Frustrations: Time-consuming keyword searches; fear of missing the “perfect” past candidate.
- **Key flow**
  1) Paste JD → 2) Submit search → 3) View ranked candidates → 4) Read “Why they’re a match” → 5) Shortlist.
- **UX considerations**: Minimal inputs, fast results, clear rationale bullets, accessible UI on Firebase Hosting.
</context>
<PRD>
# Technical Architecture
- **System components**
  - Local Processing (Mac): ✅ **COMPLETED** - Python 3.10+ data processor (`data_processor.py`) converts Workable CSV export into enriched JSON Lines format optimized for LLM analysis. Processes 29,135 candidates with merged recruiter comments.
  - Cloud Enrichment: Cloud Functions (Node.js/TypeScript) triggered by GCS object finalize; Vertex AI Gemini for deep analysis; Firestore for enriched profiles; Vertex AI Vector Search for embeddings.
  - Frontend: React (or Vue) app on Firebase Hosting calling secure Cloud Function search API.
- **Data models**
  - Processed Candidate JSON Lines: ✅ **COMPLETED** - Enriched profiles in JSON Lines format (`enriched_candidates.jsonl`) with 29,135 candidates processed.
  - Current Profile Structure:
    - `candidate_id`: string, `name`: string, `email`: string
    - `education`: [{"raw": "string"}], `experience`: [{"raw": "string"}]
    - `social_profiles`: [{"type": "linkedin", "url": "string"}]
    - `recruiter_notes`: ["detailed qualitative insights"]
    - `stage`: "Sourced|Reached Out", `source`: "linkedin|unknown"
    - `resume_path`: "path/to/resume/file"
  - Future Enriched Profile (Cloud Processing):
    - `career_arc_analysis`: { velocity: "High|Moderate", trajectory_pattern: string, key_transitions: array }
    - `quantified_scope[]`: { role_title, company, team_size, direct_reports, budget_managed }
    - `company_tier[]`: tags per company (e.g., "FAANG/Big Tech", "Top-Tier VC-Backed Startup")
    - `recruiter_takeaways`: { unique_strengths: string[], red_flags: string[] }
    - `embedding_ref`: pointer to vector stored in Vertex AI Vector Search
- **APIs & integrations**
  - Vertex AI Gemini (analysis), Vertex AI Embeddings, Firestore SDK, Cloud Storage triggers, Firebase Hosting/Functions.
- **Infrastructure requirements**
  - GCP project with Vertex AI, Firestore, Cloud Storage, and Vector Search enabled; Firebase Hosting and Functions.

# Development Roadmap
- **✅ COMPLETED: Data Preparation Phase**
  - CSV processing pipeline built and tested with full dataset (29,135 candidates)
  - Recruiter comments merged with candidate profiles (70,442 comments processed)
  - JSON Lines format optimized for LLM analysis
  - Resume file paths mapped (67,606+ files available)

- **MVP requirements**
  - Cloud infrastructure setup: Enable Vertex AI, Firestore, GCS, Vector Search
  - Local LLM enrichment: Use Ollama (llama3.1:8b) for initial analysis testing
  - GCS upload + Cloud Function trigger for production pipeline
  - Gemini-based enrichment producing all specified analytical objects
  - Persist enriched profiles to Firestore and embeddings to Vector Search
  - Simple secure web page: paste JD → ranked results (10–20) with match rationale
- **Future enhancements**
  - Advanced search filters (boolean logic, save/share searches).
  - Near-real-time ingestion for new candidates.
  - Multi-tenant, client-facing portals and billing.
  - Expanded UX (candidate detail pages, export lists).
- **Scope guidance (no timelines)**
  - Build end-to-end vertical slice from JD input to ranked results before adding extras.

# Logical Dependency Chain
- ✅ **COMPLETED: Data Preparation** - CSV processing pipeline built, 29,135 candidates processed with enriched profiles in JSON Lines format
- Foundation: Enable Vertex AI, Firestore, GCS, Vector Search; set up Firebase Hosting/Functions.
- Data path: ✅ Local processing complete → GCS upload → Cloud Function enrichment → Firestore + embeddings.
- Search path: Embedding index ready → Search API → Frontend results with rationale.
- Fast-path to usable demo: Minimal UI + working search over existing enriched dataset (29K+ candidates ready).

# Risks and Mitigations
- **Data processing complexity**: ✅ **MITIGATED** - Processing pipeline tested with full dataset (29K candidates, 70K comments); JSON Lines format optimized for LLM analysis.
- **LLM analysis variability**: Use structured prompts/schemas; add validation; log anomalies for review.
- **Embedding quality**: Evaluate models; adjust chunking/fields; test retrieval metrics against real JDs.
- **Cost control**: Batch enrichment, use local parsing to reduce cloud spend; monitor quotas.
- **Data quality from ATS**: Add normalization and fallbacks; surface low-confidence flags to recruiters.
- **Resume file processing**: Implement OCR/PDF text extraction for complete profile enrichment.

# Appendix
- **Goals & success metrics**
  - Time-to-Longlist < 30 minutes; > 5 searches per recruiter per week; satisfaction > 4.5/5.
- **Data processing status**
  - ✅ CSV processing pipeline: 29,135 candidates processed
  - ✅ Recruiter comments merged: 70,442 comments integrated
  - ✅ JSON Lines format: Optimized for LLM analysis
  - ✅ Resume files mapped: 67,606+ files available for text extraction
- **Out of scope (v1.0)**
  - Client-facing access, multi-tenancy, billing/subscriptions, real-time ingestion, advanced boolean search or sharing.
- **User stories (traceability)**
  - ✅ **COMPLETED** Epic 1.1-1.2 (Local Processing): CSV parsing and JSON enrichment pipeline built and tested
  - Epic 1 (Ingestion & Enrichment): 1.3 upload to GCS, 1.4 Gemini deep analysis with specified objects, 1.5 save to Firestore + Vector Search.
  - Epic 2 (Search Interface): 2.1 secure access, 2.2 JD textbox, 2.3 ranked 10–20 results, 2.4 match rationale bullets.
- **Version & status**
  - Date: September 5, 2025; Status: Final Draft - Updated for v1.1 with data processing completion.
  - v1.1 changes: Enhanced AI enrichment for deeper career trajectory, role scope, company pedigree, strengths/red flags + completed data processing pipeline.
</PRD>

