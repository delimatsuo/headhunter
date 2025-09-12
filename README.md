# Headhunter - AI-Powered Recruitment Analytics

**Cloud-First Architecture** powered by Together AI (single‑pass Qwen 2.5 32B) with Firebase storage and Cloud SQL (pgvector) for vector search.

## 🎯 Core Architecture

**Cloud-Triggered AI Processing**
- Single pass enrichment via Together AI using Qwen 2.5 32B Instruct (config via `TOGETHER_MODEL_STAGE1`, default `Qwen/Qwen2.5-32B-Instruct`).
- Processors (Python async) stream structured profiles to Firestore and add `analysis_confidence` + `quality_flags`.
- Embeddings generated for enriched text; vectors normalized in `candidate_embeddings`.
- Unified search blends ANN recall (pgvector planned) with structured skill/experience signals (one ranked list).

## Product UX Overview

- People Search (specific person): Search by name or LinkedIn URL; opens the Candidate Page directly.
- Job Search: Paste a JD; returns up to 50 top matches (expandable by 50). Rows stay minimal; click a row to open the Candidate Page.
- Candidate Page (deep view): Full Skill Map (explicit + inferred with confidence and “Needs verification” tags), Pre‑Interview Analysis (on‑demand), compact career Timeline, Resume Freshness, and LinkedIn link.

List row content (minimal): Name — Current role @ Company, years/level, composite score, freshness badge, LinkedIn link, and (if applicable) a small “Low profile depth” badge.

## Features

### Cloud AI Processing
- **Together AI API** with Qwen 2.5 32B Instruct (single pass)
- **Optional Cloud Run worker** for scalable processing via Pub/Sub (future)
- **Secure API key management** via environment/Secret Manager
- **Deep candidate analysis** including:
  - Career trajectory and progression patterns
  - Leadership scope and management experience
  - Company pedigree and tier analysis
  - Technical and soft skills with confidence scoring (0-100%)
  - Evidence-based skill validation with supporting arrays
  - Cultural fit signals and work style
  - Recruiter sentiment and insights
  - Skill-aware search with composite ranking algorithms

### Resume Text Extraction
Multi-format support for extracting text from:
- PDF files (PyPDF2 or pdftotext)
- Microsoft Word documents (.docx)
- Plain text files (.txt)
- Images with OCR (PNG, JPG using Tesseract)

### Processing Pipeline
- **JSON repair + schema validation** with quarantine metrics
- **Batch processing** with streaming to Firestore
- **Low‑certainty policy**: de‑rank low‑content profiles, keep searchable
- **Cost controls** via token caps, retries, and caching

### Data Storage & Search
- **Firebase Firestore** for structured profiles
- **Cloud SQL + pgvector** (planned) for scalable ANN search (Functions provides a basic fallback path for dev only)
- **VertexAI embeddings** baseline (no implicit mock fallbacks; use `EMBEDDING_PROVIDER=local` explicitly for dev-only deterministic vectors)
- **Unified search** with confidence‑weighted skill match, vector similarity, and experience (e.g., 40/25/25/10 default)
- **React SPA** (Firebase Hosting) with interactive rationale and top‑skills
- **Firebase Authentication** for secure access

### Recall Safeguards (thin profiles)
- Dual recall: ANN top‑K unioned with deterministic title/company matches, then re‑rank.
- Deterministic boost: modest boost when exact title or company matches; keep `analysis_confidence` demotion but raise the floor when deterministic signals are present.
- Optional small quota (e.g., 10–20%) for “Potential matches (low profile depth)” to avoid losing sparse but promising candidates.

### Documentation
- PRD (authoritative): `.taskmaster/docs/prd.txt`
- Handover (crash‑safe runbook): `docs/HANDOVER.md`
- Architecture visual: `docs/architecture-visual.html`
- Admin Page: Dedicated admin route in SPA (role‑gated) to manage `allowed_users` via Cloud Functions callables (`addAllowedUser`, `removeAllowedUser`, `listAllowedUsers`, `setAllowedUserRole`).
- Audit Logging: Backend writes `audit_logs` (admin‑read only) for health checks, job searches, and errors; batching and sanitization enabled. Cleanup via scheduled function recommended (90‑day retention).

### No Mock Fallbacks
- Production and staging do not serve mock or deterministic data when external services are unavailable.
- If an embedding or enrichment provider is disabled or unreachable, the API returns an explicit error.
- For development only, you may opt-in to deterministic vectors via `EMBEDDING_PROVIDER=local`.

## LLM Usage Philosophy

- Stage 1 enrichment (ingestion/update, single pass): Qwen 2.5 32B generates the structured profile used for embeddings and deterministic re‑rank. No “second pass” needed for search.
- Search time: no LLM calls; perform ANN recall + deterministic re‑rank only.
- Pre‑Interview Analysis: on‑demand LLM call for the Candidate Page; cached with TTL and invalidated on profile change.

## Candidate Essentials

- Inferred skills: Shown only on the Candidate Page, with confidence values and “Needs verification” tags below a threshold (default 0.75). Evidence tooltips present.
- LinkedIn: `linkedin_url` displayed in list and detail when available; extracted from CSV or resume text via regex.
- Freshness: Show `resume_updated_at` date with freshness badges — Recent (<6m), Stale (6–18m), Very stale (>18m). Provide a “Re‑upload latest resume” CTA in the Candidate Page.

## API Notes (planned)

- Pre‑Interview Analysis callables (backend):
  - `preInterviewAnalysis.generate` → generates and stores `pre_interview_analysis` under `candidates/{id}`
  - `preInterviewAnalysis.get` → returns latest stored analysis
- Search payload includes: `linkedin_url`, `resume_updated_at` (or `processed_at`), `analysis_confidence`, and a boolean `low_profile_depth` when applicable.

## Prerequisites

- **Google Cloud Project** with billing enabled
- **Together AI API Key** (for processing)
- **Firebase Project** configured
- **Python 3.x** (for local development/testing)
- **Node.js** (for web interface)
- **Firebase CLI** (for deployment)

## Quick Start

### 1. Cloud Setup

```bash
# Set your project
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable pubsub.googleapis.com
```

### 2. API Key Configuration

```bash
# Store Together AI API key in Secret Manager
echo "your-together-ai-key" | gcloud secrets create together-ai-credentials --data-file=-

# Grant Cloud Run access to the secret
gcloud secrets add-iam-policy-binding together-ai-credentials \
    --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### 3. Deploy Cloud Run Worker

```bash
# Deploy the processing worker
cd cloud_run_worker
gcloud run deploy candidate-enricher \
    --source . \
    --region=us-central1 \
    --platform=managed \
    --allow-unauthenticated \
    --memory=2Gi \
    --cpu=2 \
    --timeout=900
```

### 4. Firebase Setup

```bash
# Install Firebase CLI
npm install -g firebase-tools

# Login and initialize
firebase login
cd functions
npm install
npm run build
firebase deploy
```

## 🏗️ System Architecture

```
┌──────────────────────────────────────────────┐
│                INPUT LAYER                   │
├──────────────────────────────────────────────┤
│ CSVs │ Resumes (PDF/DOCX/TXT/Images) │ Notes │
└───────────────┬──────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────┐
│            STAGE 1 (SINGLE‑PASS)             │
├──────────────────────────────────────────────┤
│ Together AI – Qwen 2.5 32B Instruct          │
│ • Structured profile (skills+confidence)     │
│ • Evidence, executive summary, confidence    │
└───────────────┬──────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────┐
│           STORAGE & EMBEDDINGS               │
├──────────────────────────────────────────────┤
│ Firestore (profiles)                         │
│ candidate_embeddings (Vertex text-emb-004)   │
└───────────────┬──────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────┐
│                SEARCH PIPELINE               │
├──────────────────────────────────────────────┤
│ ANN recall (pgvector planned) ∪ deterministic│
│ re‑rank: skill/confidence/vector/experience  │
└───────────────┬──────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────┐
│                  WEB UI                      │
├──────────────────────────────────────────────┤
│ Minimal Job Search list → Candidate Page     │
│ Candidate Page: Skill Map + on‑demand PIA    │
└──────────────────────────────────────────────┘
```

## Running the System

### 1. Process Candidates

```bash
# Run performance test with 50 candidates
python3 scripts/performance_test_suite.py

# Validate workflow end-to-end
python3 scripts/prd_compliant_validation.py

# Test API connectivity
python3 scripts/api_key_validation.py
```

### 2. Batch Processing

```bash
# Upload candidates to trigger processing
python3 scripts/upload_candidates.py candidates.csv

# Monitor processing via Cloud Console
# Visit: https://console.cloud.google.com/run
```

### 3. Web Interface

```bash
# Start local development
cd headhunter-ui
npm start

# Deploy to Firebase
npm run build
firebase deploy
```

## Current Status

### ✅ Working
- Firebase Functions: CRUD, upload pipeline, unified skill‑aware search (composite re‑rank, confidence demotion).
- React SPA: Minimal Job Search list; deep Candidate Page view.
- Embeddings: Vertex text‑embedding‑004; stored in `candidate_embeddings`.

### 🚧 In Progress / Planned
- Pgvector ANN service (Cloud Run) and SPA integration.
- Deterministic recall + low‑depth bucket safeguards.
- Pre‑Interview Analysis (on‑demand) callables and Candidate Page panel.
- Optional Cloud Run enrichment worker for throughput (future).

## Security & Privacy

- API keys via environment/Secret Manager; no mock fallbacks in prod/staging.
- Access via Firebase Authentication; store only required fields; follow security rules.

## Support & Documentation

- PRD: `.taskmaster/docs/prd.txt`
- Handover: `docs/HANDOVER.md`
- Architecture Visual: `docs/architecture-visual.html`
- Architecture: `ARCHITECTURE.md`
