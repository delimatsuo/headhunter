# Headhunter AI - Cloud Architecture & CRUD System Design

## Overview

This document outlines the cloud architecture for deploying Headhunter AI to Firebase/GCP with comprehensive CRUD operations. AI processing is a hybrid model: **Vertex AI (Gemini 1.5 Pro)** is used for high-quality candidate reranking and embeddings, while **Together AI** handles candidate enrichment. Local-only processing references are historical.

## Architecture Principles

1. **Cloud AI Processing**: LLM analysis via Together AI from Python processors/Cloud Run
2. **Cloud Storage & APIs**: Firebase/Firestore for data persistence and REST APIs
3. **Scalable Design**: Multi-tenant, performant, and cost-effective
4. **Security First**: Proper authentication, authorization, and data protection
5. **Real-time Capability**: Live updates and collaborative features

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          HEADHUNTER AI CLOUD ARCHITECTURE                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│  │   React Web UI  │    │  Mobile App     │    │  Admin Dashboard│        │
│  │   (Firebase     │    │  (React Native) │    │  (Analytics)    │        │
│  │   Hosting)      │    │                 │    │                 │        │
│  └─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘        │
│            │                      │                      │                │
│            └──────────────────────┼──────────────────────┘                │
│                                   │                                       │
│  ┌─────────────────────────────────┼─────────────────────────────────────┐ │
│  │                    FIREBASE CLOUD FUNCTIONS                           │ │
│  │                                 │                                     │ │
│  │  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐     │ │
│  │  │   File Upload   │   │   CRUD APIs     │   │   Job Search    │     │ │
│  │  │   & Processing  │   │   & Management  │   │   & Matching    │     │ │
│  │  └─────────────────┘   └─────────────────┘   └─────────────────┘     │ │
│  │                                                                       │ │
│  │  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐     │ │
│  │  │   Vector Search │   │   Analytics &   │   │   Webhooks &    │     │ │
│  │  │   (pgvector)    │   │   Reporting     │   │   Integrations  │     │ │
│  │  └─────────────────┘   └─────────────────┘   └─────────────────┘     │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                   │                                       │
│  ┌─────────────────────────────────┼─────────────────────────────────────┐ │
│  │                          FIRESTORE DATABASE                           │ │
│  │                                 │                                     │ │
│  │  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐     │ │
│  │  │   Candidates    │   │   Job Postings  │   │   User Profiles │     │ │
│  │  │   Collection    │   │   Collection    │   │   Collection    │     │ │
│  │  └─────────────────┘   └─────────────────┘   └─────────────────┘     │ │
│  │                                                                       │ │
│  │  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐     │ │
│  │  │   Embeddings    │   │   Search Cache  │   │   Activity Logs │     │ │
│  │  │   (Cloud SQL)   │   │   Collection    │   │   Collection    │     │ │
│  │  └─────────────────┘   └─────────────────┘   └─────────────────┘     │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                   │                                       │
│  ┌─────────────────────────────────┼─────────────────────────────────────┐ │
│  │                        CLOUD STORAGE                                  │ │
│  │                                 │                                     │ │
│  │  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐     │ │
│  │  │   Resume Files  │   │   Profile Images│   │   Report PDFs   │     │ │
│  │  │   (PDF/DOCX)    │   │   & Assets     │   │   & Exports     │     │ │
│  │  └─────────────────┘   └─────────────────┘   └─────────────────┘     │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      LOCAL PROCESSING PIPELINE                       │   │
│  │  ┌─────────────────┐              ┌─────────────────┐                │   │
│  │  │   Together AI   │  ◄───────────┤   Python        │                │   │
│  │  │   (Chat Comp.)  │              │   Processors     │               │   │
│  │  │                 │              │   (aiohttp)      │               │   │
│  │  └─────────────────┘              └─────────────────┘                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 📊 Database Schema Design

### Collections Structure

```javascript
// Core Collections
candidates/           // Main candidate profiles
jobs/                // Job postings and descriptions  
users/               // User accounts and preferences
organizations/       // Multi-tenant organization data

// Search & Analytics
embeddings/          // Vector embeddings for semantic search
search_cache/        // Cached search results for performance
activity_logs/       // User activity and audit trail
analytics/           // Usage metrics and insights

// Processing & Queue
processing_queue/    // File processing job queue
processing_status/   // Real-time processing updates
notifications/       // User notifications and alerts
```

### Detailed Schema

#### 1. Candidates Collection
```typescript
interface Candidate {
  candidate_id: string;          // Unique identifier
  org_id: string;               // Organization for multi-tenancy
  created_by: string;           // User who added candidate
  created_at: Timestamp;        // Creation timestamp
  updated_at: Timestamp;        // Last update timestamp
  
  // Basic Information
  personal: {
    name: string;
    email?: string;
    phone?: string;
    location?: string;
    profile_image_url?: string;
  };
  
  // Resume & Files
  documents: {
    resume_file_url?: string;     // Cloud Storage URL
    resume_file_name?: string;    // Original filename
    resume_text?: string;         // Extracted text
    additional_docs?: Array<{
      name: string;
      url: string;
      type: string;
    }>;
  };
  
  // Processing Status
  processing: {
    status: 'pending' | 'processing' | 'completed' | 'failed';
    local_analysis_completed: boolean;
    embedding_generated: boolean;
    last_processed: Timestamp;
    error_message?: string;
  };
  
  // Analysis Results (from local processing)
  analysis: {
    career_trajectory: {
      current_level: string;
      progression_speed: string;
      trajectory_type: string;
      years_experience: number;
      velocity: string;
    };
    
    leadership_scope: {
      has_leadership: boolean;
      team_size: number;
      leadership_level: string;
      leadership_style?: string;
    };
    
    company_pedigree: {
      company_tier: string;
      company_tiers: string[];
      stability_pattern: string;
    };
    
    cultural_signals: {
      strengths: string[];
      red_flags: string[];
      work_style: string;
    };
    
    skill_assessment: {
      technical_skills: {
        core_competencies: string[];
        skill_depth: string;
      };
      soft_skills: {
        communication: string;
        leadership: string;
      };
    };
    
    recruiter_insights: {
      placement_likelihood: string;
      best_fit_roles: string[];
      salary_expectations: string;
      availability: string;
    };
    
    search_optimization: {
      keywords: string[];
      search_tags: string[];
    };
    
    executive_summary: {
      one_line_pitch: string;
      ideal_next_role: string;
      overall_rating: number;
    };
  };
  
  // Search & Discovery
  searchable_data: {
    skills_combined: string[];     // Flattened for queries
    experience_level: string;      // Normalized level
    industries: string[];          // Industry experience
    locations: string[];           // Location preferences
  };
  
  // User Interactions
  interactions: {
    views: number;
    bookmarks: string[];           // User IDs who bookmarked
    notes: Array<{
      user_id: string;
      note: string;
      created_at: Timestamp;
    }>;
    status_updates: Array<{
      status: string;
      updated_by: string;
      updated_at: Timestamp;
    }>;
  };
  
  // Privacy & Compliance
  privacy: {
    is_public: boolean;
    consent_given: boolean;
    gdpr_compliant: boolean;
    data_retention_until?: Timestamp;
  };
}
```

#### 2. Jobs Collection
```typescript
interface Job {
  job_id: string;               // Unique identifier
  org_id: string;              // Organization for multi-tenancy
  created_by: string;          // User who created job
  created_at: Timestamp;       // Creation timestamp
  updated_at: Timestamp;       // Last update timestamp
  
  // Job Details
  details: {
    title: string;
    company: string;
    department?: string;
    location: string;
    remote_policy: 'remote' | 'hybrid' | 'onsite';
    employment_type: 'full-time' | 'part-time' | 'contract' | 'internship';
    seniority_level: 'entry' | 'mid' | 'senior' | 'lead' | 'executive';
  };
  
  // Job Description
  description: {
    overview: string;
    responsibilities: string[];
    requirements: {
      required_skills: string[];
      preferred_skills: string[];
      years_experience: {
        min: number;
        max?: number;
      };
      education_level?: string;
      certifications?: string[];
    };
    compensation: {
      salary_range?: {
        min: number;
        max: number;
        currency: string;
      };
      benefits?: string[];
      equity?: boolean;
    };
  };
  
  // Team & Culture
  team_info: {
    team_size?: number;
    reporting_structure?: string;
    work_culture: string[];
    growth_opportunities?: string[];
  };
  
  // Job Status
  status: {
    is_active: boolean;
    applications_open: boolean;
    urgency: 'low' | 'medium' | 'high';
    positions_available: number;
    deadline?: Timestamp;
  };
  
  // Search & Matching
  matching_criteria: {
    deal_breakers: string[];      // Must-have requirements
    nice_to_haves: string[];     // Preferred but not required
    cultural_fit_indicators: string[];
    personality_traits: string[];
  };
  
  // Analytics
  analytics: {
    views: number;
    applications: number;
    matches_generated: number;
    avg_candidate_score: number;
  };
}
```

#### 3. Users Collection
```typescript
interface User {
  user_id: string;              // Firebase Auth UID
  org_id: string;              // Organization membership
  created_at: Timestamp;       // Account creation
  last_active: Timestamp;      // Last activity
  
  // Profile
  profile: {
    display_name: string;
    email: string;
    profile_image_url?: string;
    job_title?: string;
    department?: string;
    phone?: string;
  };
  
  // Permissions & Role
  permissions: {
    role: 'admin' | 'recruiter' | 'hiring_manager' | 'viewer';
    can_create_jobs: boolean;
    can_view_candidates: boolean;
    can_edit_candidates: boolean;
    can_export_data: boolean;
    can_manage_users: boolean;
  };
  
  // Preferences
  preferences: {
    notification_settings: {
      email_notifications: boolean;
      push_notifications: boolean;
      new_candidates: boolean;
      job_matches: boolean;
      system_updates: boolean;
    };
    ui_preferences: {
      theme: 'light' | 'dark';
      language: string;
      timezone: string;
      items_per_page: number;
    };
    search_defaults: {
      preferred_filters: object;
      saved_searches: Array<{
        name: string;
        query: object;
        created_at: Timestamp;
      }>;
    };
  };
  
  // Activity Tracking
  activity: {
    total_searches: number;
    total_candidates_viewed: number;
    total_jobs_created: number;
    favorite_candidates: string[];    // Candidate IDs
    recent_activity: Array<{
      action: string;
      resource_type: string;
      resource_id: string;
      timestamp: Timestamp;
    }>;
  };
}
```

#### 4. Organizations Collection
```typescript
interface Organization {
  org_id: string;              // Unique identifier
  created_at: Timestamp;       // Organization creation
  updated_at: Timestamp;       // Last update
  
  // Organization Details
  details: {
    name: string;
    domain: string;             // Company domain for email validation
    industry: string;
    size: 'startup' | 'small' | 'medium' | 'large' | 'enterprise';
    location: {
      headquarters: string;
      offices: string[];
    };
    website?: string;
    logo_url?: string;
  };
  
  // Subscription & Billing
  subscription: {
    plan: 'free' | 'pro' | 'enterprise';
    status: 'active' | 'suspended' | 'cancelled';
    billing_cycle: 'monthly' | 'yearly';
    next_billing_date?: Timestamp;
    usage_limits: {
      max_candidates: number;
      max_jobs: number;
      max_users: number;
    };
    current_usage: {
      candidates_count: number;
      jobs_count: number;
      users_count: number;
    };
  };
  
  // Configuration
  settings: {
    branding: {
      primary_color?: string;
      logo_url?: string;
      custom_domain?: string;
    };
    data_retention: {
      candidate_data_retention_months: number;
      activity_log_retention_months: number;
    };
    integrations: {
      ats_integration?: {
        provider: string;
        api_key_hash: string;
        last_sync: Timestamp;
      };
      slack_webhook?: string;
      email_notifications_from?: string;
    };
  };
  
  // Analytics
  analytics: {
    total_searches_this_month: number;
    total_candidates_processed: number;
    avg_time_to_hire?: number;
    user_engagement_score: number;
  };
}
```

#### 5. Embeddings Collection
```typescript
interface Embedding {
  embedding_id: string;        // Unique identifier
  candidate_id: string;        // Reference to candidate
  org_id: string;             // Organization for security
  created_at: Timestamp;      // Generation timestamp
  
  // Vector Data
  vector_data: {
    embedding_vector: number[];  // High-dimensional vector
    vector_dimension: number;    // Vector size (e.g., 1536)
    model_used: string;         // Model that generated embedding
    generation_method: 'local' | 'cloud';
  };
  
  // Source Content
  source_content: {
    embedding_text: string;     // Text used to generate embedding
    content_hash: string;       // Hash for change detection
    content_source: 'resume' | 'analysis' | 'combined';
  };
  
  // Metadata for Search
  metadata: {
    searchable_keywords: string[];
    category_tags: string[];
    experience_level: string;
    skills_mentioned: string[];
    industries: string[];
  };
  
  // Performance Tracking
  performance: {
    search_count: number;       // How often used in searches
    match_success_rate: number; // Success rate in matching
    last_used: Timestamp;      // Last search usage
  };
}
```

## 🔐 Security & Authentication

### Firebase Authentication Rules
```typescript
// Authentication Strategy
- Firebase Authentication with email/password
- Organization-based multi-tenancy
- Role-based access control (RBAC)
- Session management with secure tokens

// Security Rules Example
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Helper functions
    function isAuthenticated() {
      return request.auth != null;
    }
    
    function belongsToOrg(orgId) {
      return isAuthenticated() && 
             get(/databases/$(database)/documents/users/$(request.auth.uid)).data.org_id == orgId;
    }
    
    // Candidates - org-scoped access
    match /candidates/{candidateId} {
      allow read: if belongsToOrg(resource.data.org_id);
      allow write: if belongsToOrg(resource.data.org_id) && 
                      get(/databases/$(database)/documents/users/$(request.auth.uid)).data.permissions.can_edit_candidates == true;
    }
    
    // Jobs - org-scoped access
    match /jobs/{jobId} {
      allow read: if belongsToOrg(resource.data.org_id);
      allow create: if belongsToOrg(request.resource.data.org_id) && 
                       get(/databases/$(database)/documents/users/$(request.auth.uid)).data.permissions.can_create_jobs == true;
    }
  }
}
```

## 🚀 API Design

### RESTful Endpoints Structure

#### Candidates CRUD
```typescript
// Base URL: https://us-central1-headhunter-ai-0088.cloudfunctions.net/api

// Candidates
GET    /candidates                    // List candidates with pagination & filters
GET    /candidates/:id               // Get single candidate
POST   /candidates                   // Create new candidate
PUT    /candidates/:id               // Update candidate
DELETE /candidates/:id               // Delete candidate
POST   /candidates/:id/notes         // Add note to candidate
PUT    /candidates/:id/status        // Update candidate status

// File Management
POST   /candidates/:id/upload-resume // Upload resume file
DELETE /candidates/:id/documents/:docId // Delete document

// Search & Discovery
POST   /candidates/search            // Advanced search with filters
POST   /candidates/semantic-search  // AI-powered semantic search
GET    /candidates/:id/similar      // Find similar candidates

// Bulk Operations
POST   /candidates/bulk-import       // Bulk import candidates
POST   /candidates/bulk-export       // Export candidates to CSV/Excel
POST   /candidates/bulk-process      // Trigger batch processing
```

#### Jobs CRUD
```typescript
// Jobs
GET    /jobs                         // List jobs with pagination
GET    /jobs/:id                    // Get single job
POST   /jobs                        // Create new job
PUT    /jobs/:id                    // Update job
DELETE /jobs/:id                    // Delete job
POST   /jobs/:id/duplicate          // Duplicate existing job

// Job Matching
POST   /jobs/:id/find-candidates    // Find matching candidates
GET    /jobs/:id/matches           // Get cached matches
POST   /jobs/:id/match-score       // Score specific candidate against job

// Job Analytics
GET    /jobs/:id/analytics         // Job performance metrics
GET    /jobs/:id/candidate-pipeline // Candidate funnel for job
```

#### Search & Analytics
```typescript
// Search
POST   /search/candidates          // Unified candidate search
POST   /search/jobs               // Job search
GET    /search/suggestions        // Search suggestions/autocomplete
GET    /search/filters            // Available filter options

// Analytics
GET    /analytics/dashboard       // Organization dashboard metrics
GET    /analytics/usage          // Usage statistics
GET    /analytics/performance    // System performance metrics
POST   /analytics/custom-report  // Generate custom reports

// Vector Search
POST   /vector/search             // Semantic vector search
POST   /vector/generate-embedding // Generate embeddings for text
GET    /vector/stats              // Vector database statistics
```

## 📱 Frontend Integration

### React Web App Structure
```typescript
// Component Architecture
src/
├── components/
│   ├── candidates/
│   │   ├── CandidateList.tsx
│   │   ├── CandidateDetail.tsx
│   │   ├── CandidateForm.tsx
│   │   └── CandidateSearch.tsx
│   ├── jobs/
│   │   ├── JobList.tsx
│   │   ├── JobDetail.tsx
│   │   ├── JobForm.tsx
│   │   └── JobMatching.tsx
│   ├── search/
│   │   ├── SearchInterface.tsx
│   │   ├── SearchFilters.tsx
│   │   └── SearchResults.tsx
│   └── shared/
│       ├── FileUpload.tsx
│       ├── DataTable.tsx
│       └── Charts.tsx
├── services/
│   ├── api.ts              // API client with authentication
│   ├── firebase.ts         // Firebase configuration
│   └── auth.ts            // Authentication service
├── hooks/
│   ├── useAuth.ts         // Authentication hook
│   ├── useCandidates.ts   // Candidates data hook
│   └── useJobs.ts         // Jobs data hook
└── utils/
    ├── validation.ts      // Form validation schemas
    ├── formatting.ts      // Data formatting utilities
    └── constants.ts       // App constants
```

### Real-time Features
```typescript
// Real-time Updates with Firebase
const useCandidateUpdates = (orgId: string) => {
  const [candidates, setCandidates] = useState([]);
  
  useEffect(() => {
    const unsubscribe = firestore
      .collection('candidates')
      .where('org_id', '==', orgId)
      .onSnapshot((snapshot) => {
        const updates = snapshot.docChanges().map(change => ({
          type: change.type,
          candidate: { id: change.doc.id, ...change.doc.data() }
        }));
        
        // Update local state based on changes
        handleRealtimeUpdates(updates);
      });
      
    return unsubscribe;
  }, [orgId]);
  
  return candidates;
};

// File Upload with Progress
const useFileUpload = () => {
  const uploadResume = async (file: File, candidateId: string) => {
    const storage = getStorage();
    const storageRef = ref(storage, `resumes/${candidateId}/${file.name}`);
    
    const uploadTask = uploadBytesResumable(storageRef, file);
    
    return new Promise((resolve, reject) => {
      uploadTask.on('state_changed',
        (snapshot) => {
          const progress = (snapshot.bytesTransferred / snapshot.totalBytes) * 100;
          onProgress?.(progress);
        },
        (error) => reject(error),
        async () => {
          const downloadURL = await getDownloadURL(uploadTask.snapshot.ref);
          resolve(downloadURL);
        }
      );
    });
  };
  
  return { uploadResume };
};
```

## 🔄 Data Processing Pipeline

### 3-Stage Pipeline Implementation

#### Stage 1: Pre-processing (Raw → Structured JSON)
```typescript
// Cloud Function: preprocessCandidate
export const preprocessCandidate = onCall(async (request) => {
  const { candidateId, resumeUrl } = request.data;
  
  // 1. Download resume from Cloud Storage
  const file = storage.bucket().file(resumeUrl);
  const [fileBuffer] = await file.download();
  
  // 2. Extract text based on file type
  let resumeText = '';
  if (file.name.endsWith('.pdf')) {
    resumeText = await extractPdfText(fileBuffer);
  } else if (file.name.endsWith('.docx')) {
    resumeText = await extractDocxText(fileBuffer);
  }
  
  // 3. Create structured JSON
  const structuredData = {
    candidate_id: candidateId,
    raw_text: resumeText,
    extracted_at: new Date().toISOString(),
    file_metadata: {
      filename: file.name,
      size: fileBuffer.length,
      type: file.metadata.contentType
    }
  };
  
  // 4. Store in processing queue for Stage 2
  await firestore.collection('processing_queue').add({
    candidate_id: candidateId,
    stage: 'awaiting_analysis',
    structured_data: structuredData,
    created_at: FieldValue.serverTimestamp()
  });
  
  return { success: true, candidate_id: candidateId };
});
```

#### Stage 2: Analysis (JSON + LLM → Enhanced Profile)
```typescript
// Cloud Function: triggerLocalAnalysis
export const triggerLocalAnalysis = onCall(async (request) => {
  const { candidateId } = request.data;
  
  // 1. Get structured data from Stage 1
  const queueDoc = await firestore
    .collection('processing_queue')
    .where('candidate_id', '==', candidateId)
    .where('stage', '==', 'awaiting_analysis')
    .limit(1)
    .get();
    
  if (queueDoc.empty) {
    throw new HttpsError('not-found', 'Candidate not in processing queue');
  }
  
  const structuredData = queueDoc.docs[0].data().structured_data;
  
  // 2. Create webhook for local processing
  const webhookPayload = {
    candidate_id: candidateId,
    resume_text: structuredData.raw_text,
    callback_url: `https://us-central1-headhunter-ai-0088.cloudfunctions.net/receiveAnalysis`,
    processing_id: queueDoc.docs[0].id
  };
  
  // 3. Send to local processing system
  // This would be a webhook to the user's local system running Ollama
  await sendWebhookToLocalSystem(webhookPayload);
  
  // 4. Update status
  await queueDoc.docs[0].ref.update({
    stage: 'processing_with_local_llm',
    webhook_sent_at: FieldValue.serverTimestamp()
  });
  
  return { success: true, processing_id: queueDoc.docs[0].id };
});

// Webhook receiver for completed analysis
export const receiveAnalysis = onRequest(async (req, res) => {
  const { candidate_id, processing_id, analysis_results } = req.body;
  
  // 1. Validate and store analysis results
  const validatedAnalysis = CandidateAnalysisSchema.parse(analysis_results);
  
  // 2. Update candidate document
  await firestore.collection('candidates').doc(candidate_id).set({
    analysis: validatedAnalysis,
    processing: {
      status: 'completed',
      local_analysis_completed: true,
      last_processed: FieldValue.serverTimestamp()
    }
  }, { merge: true });
  
  // 3. Move to Stage 3 queue for embedding generation
  await firestore.collection('processing_queue').add({
    candidate_id,
    stage: 'awaiting_embedding',
    analysis_ready: true,
    created_at: FieldValue.serverTimestamp()
  });
  
  // 4. Clean up processing queue
  await firestore.collection('processing_queue').doc(processing_id).delete();
  
  res.status(200).json({ success: true });
});
```

#### Stage 3: Embeddings (Enhanced Profile → Vector Database)
```typescript
// Cloud Function: generateEmbeddings
export const generateEmbeddings = onCall(async (request) => {
  const { candidateId } = request.data;
  
  // 1. Get completed analysis
  const candidateDoc = await firestore.collection('candidates').doc(candidateId).get();
  const candidateData = candidateDoc.data();
  
  if (!candidateData?.analysis) {
    throw new HttpsError('failed-precondition', 'Analysis not completed yet');
  }
  
  // 2. Create embedding text from analysis
  const embeddingText = createEmbeddingText(candidateData.analysis);
  
  // 3. Generate vector using local embeddings or cloud service
  const embeddingVector = await generateVector(embeddingText);
  
  // 4. Store in embeddings collection
  const embeddingDoc = {
    candidate_id: candidateId,
    org_id: candidateData.org_id,
    vector_data: {
      embedding_vector: embeddingVector,
      vector_dimension: embeddingVector.length,
      model_used: 'local-sentence-transformers',
      generation_method: 'local'
    },
    source_content: {
      embedding_text: embeddingText,
      content_hash: hashContent(embeddingText),
      content_source: 'combined'
    },
    metadata: {
      searchable_keywords: candidateData.analysis.search_optimization.keywords,
      category_tags: candidateData.analysis.search_optimization.search_tags,
      experience_level: candidateData.analysis.career_trajectory.current_level,
      skills_mentioned: candidateData.analysis.skill_assessment.technical_skills.core_competencies,
      industries: candidateData.analysis.company_pedigree.company_tiers
    },
    created_at: FieldValue.serverTimestamp()
  };
  
  await firestore.collection('embeddings').add(embeddingDoc);
  
  // 5. Update candidate processing status
  await candidateDoc.ref.update({
    'processing.embedding_generated': true,
    'processing.status': 'completed',
    'searchable_data': {
      skills_combined: [
        ...candidateData.analysis.skill_assessment.technical_skills.core_competencies,
        ...candidateData.analysis.search_optimization.keywords
      ],
      experience_level: candidateData.analysis.career_trajectory.current_level,
      industries: candidateData.analysis.company_pedigree.company_tiers
    }
  });
  
  return { success: true, candidate_id: candidateId };
});
```

## 🔍 Advanced Search Implementation

### Hybrid Search Strategy
```typescript
// Combines traditional filters with semantic search
export const hybridSearch = onCall(async (request) => {
  const { query, filters, limit = 20, useSemanticSearch = true } = request.data;
  
  let results = [];
  
  // 1. Traditional filtered search
  let firestoreQuery = firestore.collection('candidates')
    .where('org_id', '==', request.auth.token.org_id);
    
  // Apply filters
  if (filters.experience_level) {
    firestoreQuery = firestoreQuery.where('analysis.career_trajectory.current_level', '==', filters.experience_level);
  }
  
  if (filters.skills && filters.skills.length > 0) {
    firestoreQuery = firestoreQuery.where('searchable_data.skills_combined', 'array-contains-any', filters.skills);
  }
  
  const traditionalResults = await firestoreQuery.limit(limit * 2).get();
  
  // 2. Semantic search if enabled
  if (useSemanticSearch && query) {
    const semanticResults = await performSemanticSearch(query, filters, limit);
    
    // 3. Merge and rank results
    results = mergeSearchResults(traditionalResults.docs, semanticResults);
  } else {
    results = traditionalResults.docs.map(doc => ({
      id: doc.id,
      data: doc.data(),
      score: 1.0
    }));
  }
  
  // 4. Apply final ranking and limit
  const rankedResults = results
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
    
  return {
    results: rankedResults,
    total_found: results.length,
    search_method: useSemanticSearch ? 'hybrid' : 'traditional'
  };
});
```

This comprehensive cloud architecture provides:

1. **Complete CRUD Operations** - Full create, read, update, delete functionality for all entities
2. **Local AI Processing Integration** - Maintains 100% local LLM processing while providing cloud storage
3. **Scalable Multi-tenancy** - Organization-based data isolation and user management
4. **Advanced Search Capabilities** - Hybrid traditional + semantic search
5. **Real-time Updates** - Live data synchronization across clients
6. **Security & Compliance** - Proper authentication, authorization, and data protection
7. **File Management** - Complete file upload/storage pipeline
8. **Analytics & Monitoring** - Comprehensive usage tracking and performance monitoring

The next step would be implementing these API endpoints and updating the frontend to use the cloud-based CRUD operations. Would you like me to continue with any specific component?
