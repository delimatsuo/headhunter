# Headhunter System Architecture

> Canonical repository path: `/Volumes/Extreme Pro/myprojects/headhunter`.

## Overview

Headhunter AI is a recruitment platform running on Firebase Cloud Functions with a React frontend hosted on Firebase Hosting. The system manages 29,000+ candidate profiles with AI-powered analysis and multi-signal search.

## Current Production Architecture (Dec 2025)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Firebase Hosting                                │
│                        (React SPA + TypeScript)                          │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Firebase Cloud Functions                             │
│                        (Node.js 20, 2nd Gen)                             │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐          │
│  │ engineSearch │ analyzeJob   │ processFile  │ candidatesCRUD│          │
│  │ rerankCands  │ similarCands │ importCSV    │ orgManagement │          │
│  └──────────────┴──────────────┴──────────────┴──────────────┘          │
└────────────┬─────────────┬─────────────┬─────────────┬──────────────────┘
             │             │             │             │
             ▼             ▼             ▼             ▼
      ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
      │Firestore │   │ Cloud SQL│   │  Cloud   │   │ Vertex AI│
      │(Profiles)│   │(pgvector)│   │ Storage  │   │(Embeddings│
      └──────────┘   └──────────┘   └──────────┘   │ + Ranking)│
                                                    └──────────┘
```

## Multi-Signal Search Architecture

### Flow Diagram
```
Job Description
       │
       ▼
┌──────────────────┐
│ 1. Classify Job  │──→ function: product, level: c-level
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. Multi-Pronged Retrieval                                   │
│  ┌───────────────────┐    ┌───────────────────┐              │
│  │ Firestore Query   │    │ Vector Search     │              │
│  │ function=product  │    │ pgvector cosine   │              │
│  │ → 500 candidates  │    │ → 300 candidates  │              │
│  └─────────┬─────────┘    └─────────┬─────────┘              │
│            │                        │                        │
│            └────────────┬───────────┘                        │
│                         ▼                                    │
│             ┌───────────────────────┐                        │
│             │ Merge & Deduplicate   │ → 600-800 unique       │
│             └───────────────────────┘                        │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. Score & Rank                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Function Match: 60 pts (product→product)                │ │
│  │ Level Match:    25 pts (director≈c-level)               │ │
│  │ Company Boost:  30 pts (FAANG, top startups)            │ │
│  │ Vector Score:   15 pts (0.0-1.0 → 0-15)                 │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. Cross-Encoder Rerank (Top 50)                             │
│  Vertex AI Ranking API or Gemini 2.5 Flash                   │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
              Final Ranked Results (50)
```

## Data Storage

| Store | Purpose | Key Collections/Tables |
|-------|---------|------------------------|
| **Firestore** | Primary data store | `candidates`, `users`, `organizations`, `upload_sessions` |
| **Cloud SQL (pgvector)** | Vector similarity | `candidate_embeddings` (768-dim) |
| **Cloud Storage** | File storage | `headhunter-files` bucket (resumes) |

### Candidate Document Schema
```typescript
{
  candidate_id: string,
  org_id: string,               // Primary org
  org_ids: string[],            // Multi-org access
  name: string,
  email?: string,
  canonical_email?: string,     // Deduplication key
  
  // AI Analysis
  intelligent_analysis: {
    career_trajectory_analysis: {
      current_level: string,    // "Director of Product"
      progression_speed: string,
      trajectory_type: string,
    },
    work_history: Array<{company, role, duration}>,
    extracted_skills: string[],
    leadership_indicators: string[],
    recruiter_insights: {...},
  },
  
  // Multi-Signal Search Indexes (v4.0)
  searchable: {
    function: 'product' | 'engineering' | 'data' | 'design' | 
              'sales' | 'marketing' | 'hr' | 'finance' | 
              'operations' | 'general',
    level: 'c-level' | 'vp' | 'director' | 'manager' | 
           'senior' | 'mid' | 'junior' | 'intern',
    title_keywords: string[],
    companies: string[],
    domain: string[],
  },
  
  // Original Data
  original_data: {
    experience: string,         // Raw experience text
    education: string,
  },
  
  // Documents
  documents: {
    resume_file_url: string,
    resume_file_name: string,
    resume_text: string,
  },
}
```

## Cloud Functions

| Function | Trigger | Purpose | Memory |
|----------|---------|---------|--------|
| `engineSearch` | HTTP Callable | Multi-signal search | 2GB |
| `analyzeJob` | HTTP Callable | AI job analysis | 1GB |
| `processUploadedFile` | Storage | Resume processing | 2GB |
| `generateUploadUrl` | HTTP Callable | Signed URL for upload | 256MB |
| `confirmUpload` | HTTP Callable | Trigger processing | 256MB |
| `rerankCandidates` | HTTP Callable | LLM reranking | 1GB |
| `findSimilarCandidates` | HTTP Callable | Vector similarity | 512MB |
| `importCandidatesCSV` | HTTP Callable | Bulk import | 2GB |
| `createCandidate` | HTTP Callable | CRUD | 512MB |
| `updateCandidate` | HTTP Callable | CRUD | 512MB |
| `deleteCandidate` | HTTP Callable | CRUD | 512MB |
| `onboardUser` | Auth | User registration | 512MB |
| `backfillClassifications` | HTTP | Migration script | 2GB |

## AI Models

| Model | Provider | Purpose |
|-------|----------|---------|
| `gemini-2.5-flash` | Google AI | Resume analysis, job analysis |
| `text-embedding-004` | Vertex AI | 768-dim embeddings |
| Ranking API | Vertex AI | Cross-encoder reranking |

## Key Directories

```
headhunter/
├── functions/
│   └── src/
│       ├── engines/           # Search engine implementations
│       │   ├── legacy-engine.ts    # Multi-signal retrieval v4.0
│       │   ├── agentic-engine.ts   # Experimental agentic search
│       │   └── types.ts       # Shared types
│       ├── engine-search.ts   # Engine orchestration
│       ├── file-upload-pipeline.ts  # Resume processing
│       ├── candidates-crud.ts # CRUD operations
│       ├── vector-search.ts   # pgvector queries
│       ├── backfill-classifications.ts  # Migration
│       └── index.ts           # Function exports
├── headhunter-ui/
│   └── src/
│       ├── components/
│       │   ├── Dashboard/     # Main dashboard
│       │   ├── Search/        # Search interface
│       │   ├── Candidate/     # Candidate cards
│       │   └── Upload/        # File upload
│       └── services/
│           ├── api.ts         # API client
│           └── firestore-direct.ts
└── docs/                      # Documentation
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `GOOGLE_CLOUD_PROJECT` | GCP project ID |
| `GOOGLE_API_KEY` | Gemini API key |
| `PGVECTOR_*` | Cloud SQL connection |
| `BUCKET_FILES` | Cloud Storage bucket |

## Monitoring & Observability

- **Cloud Logging**: All function logs
- **Cloud Monitoring**: Function metrics, latency
- **Error Reporting**: Automatic error grouping

## Security

- Firebase Auth for user authentication
- Firestore security rules for data access
- org_id-based multi-tenancy
- Signed URLs for file uploads (15-minute expiry)

---

## Legacy Reference

The Fastify microservices mesh (`docker-compose.local.yml`) was an architectural direction that was not fully implemented. Current production runs entirely on Firebase Cloud Functions. Fastify documentation is preserved for potential future migration.
