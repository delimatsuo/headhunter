# Headhunter AI - Product Requirements Document

## 1. Executive Summary

Headhunter AI is an intelligent recruitment platform that helps executive recruiters find and evaluate candidates using AI-powered analysis, semantic search, and intelligent ranking. The platform manages 29,000+ candidate profiles and provides multi-signal search capabilities to match candidates to job descriptions.

**Current State (Dec 2025):** Production system running on Firebase Cloud Functions with React frontend.

## 2. User Roles

| Role | Access | Capabilities |
|------|--------|--------------|
| **Ella Recruiter** | Central database (`org_ella_main`, 29k+ candidates) | Full search, upload, edit, org management |
| **Client User** | Private organization only | View/search candidates shared to their org |

**Auto-Onboarding:**
- `@ella.com.br` / `@ellaexecutivesearch.com` → `org_ella_main`
- External emails → New private organization

## 3. Core Features

### 3.1 Candidate Management

#### Resume Upload & Processing
- **File Types:** PDF, DOCX, DOC, TXT, RTF, JPG, PNG
- **Upload Flow:** Signed URL generation → Direct upload to Cloud Storage → Processing trigger
- **AI Processing Pipeline:**
  1. Text extraction (PDF parsing, OCR for images)
  2. Gemini 2.5 Flash analysis (career trajectory, skills, experience)
  3. Embedding generation (VertexAI `text-embedding-004`, 768 dimensions)
  4. Searchable classification (function, level, companies)
- **Files:** `file-upload-pipeline.ts`, `processUploadedFile`

#### CSV Bulk Import
- Upload CSV with candidate data
- AI-powered column mapping suggestions
- Deduplication by canonical email
- **Files:** `import-candidates-csv.ts`

#### CRUD Operations
- Create, Read, Update, Delete candidates
- Fuzzy name matching for duplicate detection
- Status tracking: active, interviewing, hired, rejected, withdrawn
- **Files:** `candidates-crud.ts`

### 3.2 Search & Discovery

#### Multi-Signal Retrieval (v4.0 - Dec 2025)
- **Pre-Index Classification:** Candidates classified by:
  - `function`: product, engineering, data, design, sales, marketing, hr, finance, operations
  - `level`: c-level, vp, director, manager, senior, mid, junior, intern
  - `companies`: Past employers
  - `domain`: fintech, delivery, e-commerce, big-tech

- **Multi-Pronged Query:**
  - Pool A: Firestore function-filtered query (up to 500 candidates)
  - Pool B: Vector similarity (pgvector, 300 candidates)
  - Merge and deduplicate

- **Scoring Formula:**
  | Signal | Points |
  |--------|--------|
  | Function match | 60 |
  | Level match | 25 |
  | Company pedigree | 30 |
  | Vector similarity | 15 |

- **Files:** `engines/legacy-engine.ts`, `engine-search.ts`

#### AI Job Analysis
- One-click analysis of job descriptions
- Extracts: Skills, Level, Domain, Key Requirements
- Feeds into search strategy
- **Files:** `analyze-job.ts`

#### AI Reranking
- Vertex AI Ranking API (cross-encoder)
- Fallback: Gemini 2.5 Flash reasoning
- "Senior Recruiter" level judgment
- **Files:** `vertex-ranking-service.ts`, `rerank-candidates.ts`

#### Quick Find
- Keyword search by name, company, title
- Fuzzy matching with typo tolerance
- **Files:** Dashboard.tsx `handleQuickFind`

#### Similar Candidates
- Find candidates similar to a selected profile
- Vector similarity based
- **Files:** `similar-candidates.ts`

#### Saved Searches
- Save job descriptions with search parameters
- Quick re-run of previous searches
- **Files:** `saved-searches.ts`

### 3.3 User Interface

#### Dashboard
- Candidate count statistics
- Quick Find search bar
- Job Description form for full AI search
- Recent/saved searches
- **Files:** `Dashboard.tsx`

#### Search Results
- Skill-aware candidate cards
- Match score percentage
- AI-generated rationale (strengths, concerns)
- Find Similar button
- Engine selector (Legacy vs Agentic)
- **Files:** `SearchResults.tsx`, `SkillAwareCandidateCard.tsx`

#### Candidate Cards
- Profile summary
- Experience highlights
- Skills tags
- AI insights
- Edit/View actions
- **Files:** `CandidateCard.tsx`, `SkillAwareCandidateCard.tsx`

#### Upload Interface
- Drag-and-drop file upload
- Manual candidate creation form
- Progress indicators
- **Files:** `FileUpload.tsx`, `AddCandidateModal.tsx`

### 3.4 Organization Management

- **Agency Model:** Ella sees ALL candidates; clients see only their org
- **Organization Switching:** Users can switch between orgs they have access to
- **Client Creation:** Ella admins can create client organizations
- **Multi-Org Candidates:** `org_ids[]` array for multi-org access
- **Files:** `org-management.ts`, `user-onboarding.ts`

## 4. Technical Architecture

### 4.1 Current Production Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Frontend** | React + TypeScript + MUI | Single-page application |
| **Backend** | Firebase Cloud Functions (Node.js 20) | API endpoints |
| **Database** | Firestore | Candidate profiles, users, orgs |
| **Vector DB** | Cloud SQL PostgreSQL + pgvector | Embeddings for similarity search |
| **AI Models** | Gemini 2.5 Flash, VertexAI Ranking | Analysis, reranking |
| **Embeddings** | VertexAI `text-embedding-004` | 768-dimension vectors |
| **Storage** | Cloud Storage | Resume files |
| **Auth** | Firebase Auth | User authentication |
| **Hosting** | Firebase Hosting | Static frontend |

### 4.2 Key Cloud Functions

| Function | Purpose |
|----------|---------|
| `engineSearch` | Multi-signal candidate search |
| `analyzeJob` | AI job description analysis |
| `processUploadedFile` | Resume processing pipeline |
| `generateUploadUrl` / `confirmUpload` | Signed URL upload flow |
| `rerankCandidates` | LLM-based reranking |
| `findSimilarCandidates` | Vector similarity search |
| `importCandidatesCSV` | Bulk CSV import |
| `createCandidate` / `updateCandidate` / `deleteCandidate` | CRUD |
| `onboardUser` | User registration and org assignment |
| `backfillClassifications` | One-time classification migration |

### 4.3 Data Model

```typescript
// Candidate Document
{
  candidate_id: string,
  org_id: string,           // Primary org
  org_ids: string[],        // All orgs with access
  name: string,
  email?: string,
  canonical_email?: string, // For deduplication
  
  // AI Analysis
  intelligent_analysis: {
    career_trajectory_analysis: {...},
    work_history: [...],
    skills: [...],
  },
  
  // Multi-Signal Search Indexes
  searchable: {
    function: 'product' | 'engineering' | 'data' | ...,
    level: 'c-level' | 'vp' | 'director' | ...,
    title_keywords: string[],
    companies: string[],
    domain: string[],
  },
  
  // Documents
  documents: {
    resume_file_url: string,
    resume_text: string,
  },
}
```

## 5. Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Search Latency | < 30s | ~25s |
| Product candidates in CPO search | > 80% | 80% (16/20) |
| Candidate classification coverage | 100% | 98% |
| Active candidates | 29,000+ | 29,161 |

## 6. Classification Distribution

| Function | Count | Level | Count |
|----------|-------|-------|-------|
| Product | 1,836 | C-level | 2,367 |
| Engineering | 13,899 | VP | 278 |
| Data | 474 | Director | 999 |
| Sales | 406 | Manager | 5,182 |
| Marketing | 240 | Senior | 10,346 |
| HR | 161 | Mid | 9,043 |
| Finance | 137 | Junior | 285 |
| Operations | 191 | Intern | 44 |
| Design | 111 | | |
| General | 11,089 | | |

## 7. Future Roadmap

- [ ] Agentic Engine (deep reasoning for complex searches)
- [ ] Batch enrichment improvements
- [ ] Real-time collaboration features
- [ ] Advanced analytics dashboard
- [ ] LinkedIn integration
