<context>
# Overview  
Headhunter v1.1 transforms Ella Executive Search's historical candidate database into an intelligent, semantic search engine. It solves the inefficiency and blind spots of keyword-based ATS queries by deeply analyzing each candidate's experience, leadership scope, and cultural signals, then matching them contextually to new role descriptions. Primary users are recruiters who need to build qualified long-lists in under 30 minutes while improving search quality and unlocking the strategic value of proprietary candidate data.

# Core Features
- **LLM-Powered Data Processing**: Use Llama 3.1 8b via Together AI API for scalable batch processing of 29,000 candidates, intelligently analyzing unstructured candidate data (resumes, recruiter comments, experience descriptions) to create structured JSON profiles with deep insights.
- **AI enrichment pipeline**: Together AI Llama 3.1 8b processes candidate data at scale to produce enriched candidate profiles including career arc analysis, standardized role scope, company pedigree, and recruiter takeaways (strengths/red flags). Results stored in Firestore.
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
  - ✅ LLM Data Processing: Python 3.10+ with Together AI API and Llama 3.1 8b integration for scalable batch processing of 29,000 candidates; includes local fallback mode
  - ✅ Cloud Processing: Together AI Llama 3.1 8b for large-scale candidate analysis; Cloud Functions (Node.js/TypeScript) for data management; Firestore for profiles
  - ✅ Security Layer: Comprehensive input validation (Zod), XSS protection (DOMPurify), audit logging, error handling with circuit breakers
  - ✅ Frontend: React TypeScript app with Firebase Authentication, optimized build pipeline, and secure API integration
- **Data models**
  - LLM-Generated Candidate Profiles: Intelligent analysis of unstructured data producing:
    - `career_trajectory`: Deep analysis of career progression patterns and velocity
    - `leadership_scope`: Extracted team size, reporting structure, and management experience
    - `company_pedigree`: Categorized company tiers and industry context
    - `cultural_signals`: Identified strengths, red flags, and fit indicators
    - `skill_assessment`: Technical and soft skill evaluation from resume content
    - `recruiter_insights`: Synthesized analysis of all recruiter comments and notes
  - Search-Ready Profiles: Structured JSON optimized for semantic search and matching
- **APIs & integrations**
  - Together AI Llama 3.1 8b API (scalable processing), Firestore SDK, Cloud Storage, Firebase Hosting/Functions.
- **Infrastructure requirements**
  - Firebase project with Firestore, Cloud Storage enabled; Firebase Hosting and Functions; Together AI API for Llama 3.1 8b processing.

# Development Status & Testing Guide

## ✅ COMPLETED MVP Features
- ✅ **LLM Data Processing**: Full pipeline with Llama 3.1 8b integration and fallback mode
- ✅ **Together AI Integration**: Together AI Llama 3.1 8b API for scalable semantic analysis and batch candidate processing
- ✅ **Security Implementation**: All 35 vulnerabilities fixed - input validation, XSS protection, audit logging
- ✅ **Cloud Functions**: 9 production-ready endpoints with comprehensive error handling
- ✅ **Frontend**: React TypeScript app with Firebase Auth and optimized build
- ✅ **Quality Validation**: TypeScript compilation, build optimization, security scanning

## 🧪 How to Test the Complete System

### Prerequisites
```bash
# 1. Start Cloud Functions locally
firebase emulators:start --only functions
# Functions will be available at: http://127.0.0.1:5001

# 2. Ensure Ollama is running (optional - has fallback)
ollama serve
ollama pull llama3.1:8b
```

### Testing Flow

#### Step 1: Parse Database Content
```bash
# Option A: Using Python LLM Processor (with sample data)
cd scripts
python3 llm_processor.py --input "sample_resumes.csv" --output "processed_candidates.json"

# Option B: Upload resume files to trigger Cloud Functions
# Upload PDF/DOCX files to Firebase Storage bucket to trigger processUploadedProfile
```

#### Step 2: Generate Embeddings (Semantic Search Setup)
```bash
# Generate embeddings for all processed candidates
curl -X POST "http://127.0.0.1:5001/headhunter-ai-0088/us-central1/generateEmbedding" \
  -H "Content-Type: application/json" \
  -d '{"candidate_id": "test-candidate-1"}'
```

#### Step 3: Test Search Functionality
```bash
# Test job search with comprehensive matching
curl -X POST "http://127.0.0.1:5001/headhunter-ai-0088/us-central1/searchJobCandidates" \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "job_description": {
      "title": "Senior Software Engineer",
      "description": "Looking for a senior engineer with React and Python experience",
      "required_skills": ["React", "Python", "AWS"],
      "years_experience": 5
    },
    "limit": 10
  }'

# Test semantic search
curl -X POST "http://127.0.0.1:5001/headhunter-ai-0088/us-central1/semanticSearch" \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "senior developer with leadership experience in fintech",
    "limit": 20
  }'
```

#### Step 4: Frontend Testing
```bash
# Build and serve React app
cd headhunter-ui
npm run build
npx serve -s build -p 3000

# Access at: http://localhost:3000
# Login with Google → Paste job description → View ranked results
```
- **Future enhancements**
  - Advanced search filters (boolean logic, save/share searches).
  - Near-real-time ingestion for new candidates.
  - Multi-tenant, client-facing portals and billing.
  - Expanded UX (candidate detail pages, export lists).
- **Scope guidance (no timelines)**
  - Build end-to-end vertical slice from JD input to ranked results before adding extras.

# Logical Dependency Chain
- Foundation: Set up Ollama with Llama 3.1 8b; enable Firestore, Cloud Storage; set up Firebase Hosting/Functions.
- Data path: LLM analysis of unstructured data → Structured JSON profiles → GCS upload → Cloud Function enrichment → Firestore + embeddings.
- Search path: Embedding index ready → Search API → Frontend results with rationale.
- Fast-path to usable demo: LLM processing of sample candidates → Local search testing → Minimal UI with working semantic matching.

# Risks and Mitigations
- **LLM analysis quality**: Implement prompt engineering, few-shot examples, and output validation; test analysis accuracy against known profiles; establish quality metrics and human review workflows.
- **Local LLM performance**: Optimize Llama 3.1 8b context windows for resume processing; implement batch processing for large datasets; monitor memory usage and processing times.
- **Structured output consistency**: Use JSON schema validation and retry mechanisms; implement output parsing with fallbacks; establish quality thresholds for automated processing.
- **Data privacy and security**: Ensure local LLM processing maintains data confidentiality; implement secure data handling protocols; avoid external API calls during initial processing.
- **Cost control**: Local processing reduces cloud costs; batch enrichment for production; monitor quotas and implement cost-effective scaling strategies.

# Appendix  
- **Goals & success metrics**
  - Time-to-Longlist < 30 minutes; > 5 searches per recruiter per week; satisfaction > 4.5/5.
- **Out of scope (v1.0)**
  - Client-facing access, multi-tenancy, billing/subscriptions, real-time ingestion, advanced boolean search or sharing.
- **User stories (traceability)**
  - Epic 1 (LLM Data Processing): 1.1 Set up Ollama with Llama 3.1 8b, 1.2 Create prompts for resume analysis and career insights, 1.3 Process unstructured data into structured JSON profiles, 1.4 Validate LLM output quality and consistency.
  - Epic 2 (Ingestion & Enrichment): 2.1 Local Llama 3.1 8b processes candidate data, 2.2 Upload enhanced profiles to Cloud Storage, 2.3 Store structured profiles in Firestore.
  - Epic 3 (Search Interface): 3.1 Secure web access, 3.2 JD input interface, 3.3 Ranked candidate results (10–20), 3.4 "Why they're a match" rationale generation.
 - **Version & status**
   - Date: September 5, 2025; Status: Final Draft.
   - v1.1 change: Enhanced AI enrichment for deeper career trajectory, role scope, company pedigree, strengths/red flags.
</PRD>

