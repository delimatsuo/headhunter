# Headhunter AI - Complete API Documentation

## Overview

This document provides comprehensive documentation for the Headhunter AI cloud API endpoints. The system maintains 100% local AI processing while providing cloud-based storage, CRUD operations, and real-time collaboration features.

## Base URL
```
https://us-central1-headhunter-ai-0088.cloudfunctions.net
```

## Authentication

All API endpoints require Firebase Authentication. Include the ID token in the Authorization header:

```http
Authorization: Bearer <firebase_id_token>
```

### Organization Access
All data is scoped to organizations. Users must be members of an organization to access its data.

## API Endpoints

### 🧑‍💼 Candidates API

#### Create Candidate
```http
POST /createCandidate
```

**Request Body:**
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "+1-555-0123",
  "location": "San Francisco, CA",
  "resume_text": "Software Engineer with 5 years...",
  "notes": "Initial screening completed"
}
```

**Response:**
```json
{
  "success": true,
  "candidate_id": "candidate_12345",
  "data": {
    "candidate_id": "candidate_12345",
    "personal": {
      "name": "John Doe",
      "email": "john@example.com",
      "phone": "+1-555-0123",
      "location": "San Francisco, CA"
    },
    "processing": {
      "status": "pending",
      "local_analysis_completed": false
    },
    "created_at": "2025-01-15T10:30:00Z"
  }
}
```

#### Get Candidate
```http
POST /getCandidate
```

**Request Body:**
```json
{
  "candidate_id": "candidate_12345"
}
```

**Response:** Complete candidate profile with analysis results if available.

#### Update Candidate
```http
POST /updateCandidate
```

**Request Body:**
```json
{
  "candidate_id": "candidate_12345",
  "name": "John Smith",
  "status": "interviewing",
  "notes": "Technical interview scheduled"
}
```

#### Delete Candidate
```http
POST /deleteCandidate
```

**Request Body:**
```json
{
  "candidate_id": "candidate_12345"
}
```

#### Search Candidates
```http
POST /searchCandidates
```

**Request Body:**
```json
{
  "query": "React developer",
  "filters": {
    "experience_level": "senior",
    "skills": ["React", "Node.js", "TypeScript"],
    "location": "San Francisco",
    "min_years_experience": 5,
    "leadership_experience": true
  },
  "sort": {
    "field": "updated_at",
    "direction": "desc"
  },
  "pagination": {
    "page": 1,
    "limit": 20
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "candidates": [
      {
        "id": "candidate_12345",
        "personal": {
          "name": "John Doe",
          "location": "San Francisco, CA"
        },
        "analysis": {
          "career_trajectory": {
            "current_level": "senior",
            "years_experience": 7
          },
          "skill_assessment": {
            "technical_skills": {
              "core_competencies": ["React", "Node.js", "TypeScript"]
            }
          }
        }
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total_count": 45,
      "total_pages": 3,
      "has_next_page": true
    }
  }
}
```

#### Get Candidates List
```http
POST /getCandidates
```

**Request Body:**
```json
{
  "page": 1,
  "limit": 20,
  "sort_by": "updated_at",
  "sort_order": "desc"
}
```

#### Add Candidate Note
```http
POST /addCandidateNote
```

**Request Body:**
```json
{
  "candidate_id": "candidate_12345",
  "note": "Great cultural fit, very enthusiastic about the role"
}
```

#### Toggle Candidate Bookmark
```http
POST /toggleCandidateBookmark
```

**Request Body:**
```json
{
  "candidate_id": "candidate_12345"
}
```

#### Bulk Candidate Operations
```http
POST /bulkCandidateOperations
```

**Request Body:**
```json
{
  "operation": "update_status",
  "candidate_ids": ["candidate_1", "candidate_2", "candidate_3"],
  "data": {
    "status": "reviewed"
  }
}
```

**Supported Operations:**
- `delete` - Delete multiple candidates
- `update_status` - Update status for multiple candidates
- `add_tag` - Add tag to multiple candidates

#### Get Candidate Statistics
```http
POST /getCandidateStats
```

**Response:**
```json
{
  "success": true,
  "stats": {
    "total_candidates": 150,
    "processed_candidates": 120,
    "pending_processing": 30,
    "recent_candidates": 15,
    "experience_levels": {
      "entry": 25,
      "mid": 45,
      "senior": 35,
      "lead": 10,
      "executive": 5
    },
    "processing_completion_rate": 80
  }
}
```

### 💼 Jobs API

#### Create Job
```http
POST /createJob
```

**Request Body:**
```json
{
  "title": "Senior React Developer",
  "company": "TechCorp Inc",
  "department": "Engineering",
  "location": "San Francisco, CA",
  "remote_policy": "hybrid",
  "employment_type": "full-time",
  "seniority_level": "senior",
  "overview": "We're looking for a senior React developer...",
  "responsibilities": [
    "Build and maintain React applications",
    "Mentor junior developers",
    "Collaborate with design team"
  ],
  "required_skills": ["React", "TypeScript", "Node.js"],
  "preferred_skills": ["GraphQL", "AWS", "Docker"],
  "min_years_experience": 5,
  "max_years_experience": 10,
  "salary_min": 120000,
  "salary_max": 180000,
  "currency": "USD",
  "benefits": ["Health insurance", "401k", "Flexible PTO"],
  "equity": true,
  "team_size": 8,
  "positions_available": 2,
  "urgency": "high"
}
```

**Response:**
```json
{
  "success": true,
  "job_id": "job_67890",
  "data": {
    "job_id": "job_67890",
    "details": {
      "title": "Senior React Developer",
      "company": "TechCorp Inc",
      "location": "San Francisco, CA",
      "remote_policy": "hybrid"
    },
    "status": {
      "is_active": true,
      "applications_open": true,
      "urgency": "high"
    },
    "created_at": "2025-01-15T10:30:00Z"
  }
}
```

#### Get Job
```http
POST /getJob
```

**Request Body:**
```json
{
  "job_id": "job_67890"
}
```

#### Update Job
```http
POST /updateJob
```

**Request Body:**
```json
{
  "job_id": "job_67890",
  "title": "Senior Full-Stack Developer",
  "required_skills": ["React", "TypeScript", "Node.js", "PostgreSQL"],
  "is_active": true
}
```

#### Delete Job
```http
POST /deleteJob
```

**Request Body:**
```json
{
  "job_id": "job_67890"
}
```

#### Search Jobs
```http
POST /searchJobs
```

**Request Body:**
```json
{
  "query": "React developer",
  "filters": {
    "location": "San Francisco",
    "remote_policy": "remote",
    "seniority_level": "senior",
    "employment_type": "full-time",
    "min_salary": 100000,
    "is_active": true
  },
  "sort": {
    "field": "created_at",
    "direction": "desc"
  },
  "pagination": {
    "page": 1,
    "limit": 20
  }
}
```

#### Get Jobs List
```http
POST /getJobs
```

**Request Body:**
```json
{
  "page": 1,
  "limit": 20,
  "sort_by": "updated_at",
  "sort_order": "desc",
  "active_only": true
}
```

#### Duplicate Job
```http
POST /duplicateJob
```

**Request Body:**
```json
{
  "job_id": "job_67890"
}
```

#### Get Job Statistics
```http
POST /getJobStats
```

**Response:**
```json
{
  "success": true,
  "stats": {
    "total_jobs": 25,
    "active_jobs": 18,
    "inactive_jobs": 7,
    "urgent_jobs": 5,
    "recent_jobs": 3,
    "seniority_levels": {
      "entry": 2,
      "mid": 8,
      "senior": 12,
      "lead": 3,
      "executive": 0
    },
    "employment_types": {
      "full-time": 20,
      "part-time": 2,
      "contract": 3,
      "internship": 0
    }
  }
}
```

### 📁 File Upload API

#### Generate Upload URL
```http
POST /generateUploadUrl
```

**Request Body:**
```json
{
  "candidate_id": "candidate_12345",
  "file_name": "john_doe_resume.pdf",
  "file_size": 2048576,
  "content_type": "application/pdf",
  "metadata": {
    "original_name": "John Doe - Software Engineer Resume.pdf",
    "tags": ["resume", "senior"]
  }
}
```

**Response:**
```json
{
  "success": true,
  "upload_url": "https://storage.googleapis.com/headhunter-ai-0088-files/...",
  "upload_session_id": "upload_1642247400_candidate_12345",
  "file_path": "organizations/org_123/candidates/candidate_12345/resumes/1642247400_john_doe_resume.pdf",
  "expires_in_minutes": 15
}
```

**Usage:**
1. Get signed upload URL from this endpoint
2. Upload file directly to Google Cloud Storage using the provided URL
3. Call `confirmUpload` to process the file

#### Confirm Upload
```http
POST /confirmUpload
```

**Request Body:**
```json
{
  "upload_session_id": "upload_1642247400_candidate_12345"
}
```

**Response:**
```json
{
  "success": true,
  "candidate_id": "candidate_12345",
  "file_path": "organizations/org_123/candidates/candidate_12345/resumes/1642247400_john_doe_resume.pdf",
  "processing_queued": true
}
```

#### Process File (Manual)
```http
POST /processFile
```

**Request Body:**
```json
{
  "file_path": "organizations/org_123/candidates/candidate_12345/resumes/resume.pdf",
  "candidate_id": "candidate_12345",
  "file_type": "pdf",
  "processing_options": {
    "extract_text": true,
    "ocr_enabled": true,
    "auto_trigger_analysis": true
  }
}
```

#### Delete File
```http
POST /deleteFile
```

**Request Body:**
```json
{
  "candidate_id": "candidate_12345",
  "file_path": "organizations/org_123/candidates/candidate_12345/resumes/resume.pdf"
}
```

#### Get Upload Statistics
```http
POST /getUploadStats
```

**Response:**
```json
{
  "success": true,
  "stats": {
    "candidates_with_files": 85,
    "candidates_with_extracted_text": 78,
    "text_extraction_rate": 92,
    "processing_queue": {
      "total_in_queue": 7,
      "by_stage": {
        "text_extraction": 3,
        "awaiting_analysis": 4
      },
      "by_status": {
        "queued": 5,
        "processing": 2
      }
    }
  }
}
```

### 🔍 Search & Analytics API

#### Semantic Search
```http
POST /semanticSearch
```

**Request Body:**
```json
{
  "query_text": "experienced React developer with leadership skills",
  "filters": {
    "min_years_experience": 5,
    "current_level": "senior"
  },
  "limit": 20
}
```

#### Job-Candidate Matching
```http
POST /searchJobCandidates
```

**Request Body:**
```json
{
  "job_description": {
    "title": "Senior React Developer",
    "description": "Looking for an experienced React developer...",
    "required_skills": ["React", "TypeScript", "Node.js"],
    "years_experience": 5,
    "location": "San Francisco, CA"
  },
  "limit": 20
}
```

#### Quick Match
```http
POST /quickMatch
```

**Request Body:**
```json
{
  "job_title": "Senior React Developer",
  "skills": ["React", "TypeScript"],
  "experience_years": 5,
  "limit": 10
}
```

### 🛠️ System API

#### Health Check
```http
POST /healthCheck
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00Z",
  "services": {
    "firestore": "connected",
    "storage": "bucket_exists",
    "vertex_ai": "configured"
  },
  "project": "headhunter-ai-0088",
  "region": "us-central1"
}
```

#### Vector Search Statistics
```http
POST /vectorSearchStats
```

**Response:**
```json
{
  "success": true,
  "stats": {
    "total_embeddings": 150,
    "avg_vector_dimension": 1536,
    "last_generated": "2025-01-15T09:15:00Z"
  },
  "health": {
    "status": "healthy",
    "last_check": "2025-01-15T10:30:00Z"
  }
}
```

## Error Handling

All endpoints return errors in this format:

```json
{
  "error": {
    "code": "invalid-argument",
    "message": "Candidate ID is required",
    "details": "Additional error context if available"
  }
}
```

**Common Error Codes:**
- `unauthenticated` - Missing or invalid authentication
- `permission-denied` - Insufficient permissions
- `invalid-argument` - Invalid request parameters
- `not-found` - Resource not found
- `internal` - Internal server error

## Rate Limits

- **File Upload**: 10 uploads per minute per user
- **Search Operations**: 30 requests per minute per user
- **CRUD Operations**: 60 requests per minute per user
- **Analytics**: 10 requests per minute per user

## Data Processing Pipeline

### Stage 1: Pre-processing (Raw → Structured JSON)
1. User uploads resume file
2. System extracts text using appropriate parser (PDF, DOCX, OCR)
3. Creates structured JSON with metadata
4. Queues for Stage 2 processing

### Stage 2: Analysis (JSON + Local LLM → Enhanced Profile)
1. System creates webhook payload for local processing
2. Local system (with Ollama) receives webhook
3. Llama 3.1 8b processes resume text (11 LLM calls)
4. Enhanced analysis posted back to cloud via webhook
5. Results stored in Firestore

### Stage 3: Embeddings (Enhanced Profile → Vector Database)
1. System generates embedding text from analysis
2. Creates vector representation for semantic search
3. Stores embedding in Firestore collection
4. Makes candidate searchable via vector similarity

## Client SDK Examples

### JavaScript/TypeScript
```typescript
import { initializeApp } from 'firebase/app';
import { getAuth, signInWithEmailAndPassword } from 'firebase/auth';
import { getFunctions, httpsCallable } from 'firebase/functions';

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const functions = getFunctions(app, 'us-central1');

// Authenticate
await signInWithEmailAndPassword(auth, email, password);

// Call API functions
const createCandidate = httpsCallable(functions, 'createCandidate');
const result = await createCandidate({
  name: 'John Doe',
  email: 'john@example.com',
  location: 'San Francisco, CA'
});

console.log('Created candidate:', result.data);
```

### Python
```python
import requests
import json

# Get Firebase ID token (implement authentication separately)
id_token = get_firebase_id_token()

headers = {
    'Authorization': f'Bearer {id_token}',
    'Content-Type': 'application/json'
}

# Create candidate
response = requests.post(
    'https://us-central1-headhunter-ai-0088.cloudfunctions.net/createCandidate',
    headers=headers,
    json={
        'name': 'John Doe',
        'email': 'john@example.com',
        'location': 'San Francisco, CA'
    }
)

result = response.json()
print(f"Created candidate: {result['candidate_id']}")
```

### React Hook Example
```typescript
import { useAuthState } from 'react-firebase-hooks/auth';
import { httpsCallable } from 'firebase/functions';

export function useCandidates() {
  const [user, loading] = useAuthState(auth);
  const [candidates, setCandidates] = useState([]);
  
  const createCandidate = async (candidateData) => {
    const create = httpsCallable(functions, 'createCandidate');
    const result = await create(candidateData);
    
    // Update local state
    setCandidates(prev => [...prev, result.data.data]);
    
    return result.data;
  };
  
  const searchCandidates = async (searchParams) => {
    const search = httpsCallable(functions, 'searchCandidates');
    const result = await search(searchParams);
    
    setCandidates(result.data.data.candidates);
    return result.data;
  };
  
  return {
    candidates,
    createCandidate,
    searchCandidates,
    loading: loading
  };
}
```

## Webhook Integration

For local LLM processing integration, implement these webhook endpoints:

### Receive Processing Request
```http
POST /webhook/process-candidate
```

**Payload:**
```json
{
  "candidate_id": "candidate_12345",
  "resume_text": "Software Engineer with 5 years...",
  "callback_url": "https://us-central1-headhunter-ai-0088.cloudfunctions.net/receiveAnalysis",
  "processing_id": "processing_67890"
}
```

### Send Results Back
```http
POST /receiveAnalysis
```

**Payload:**
```json
{
  "candidate_id": "candidate_12345",
  "processing_id": "processing_67890",
  "analysis_results": {
    "career_trajectory": { ... },
    "leadership_scope": { ... },
    "skill_assessment": { ... }
  }
}
```

This comprehensive API provides everything needed to build a complete headhunter application with cloud storage, local AI processing, and real-time collaboration features.