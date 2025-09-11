# Headhunter - AI-Powered Recruitment Analytics

**Cloud-First Architecture** powered by Together AI with Firebase storage and Cloud SQL vector search.

## 🎯 Core Architecture

**Cloud-Triggered AI Processing** - Cloud Run workers process candidate data using Together AI (Meta Llama 3.2 3B Instruct Turbo). Results stored in Firebase, vectors in Cloud SQL + pgvector for semantic search.

## Features

### Cloud AI Processing
- **Together AI API** with Meta Llama 3.2 3B Instruct Turbo
- **Cloud Run workers** for scalable processing via Pub/Sub
- **Secure API key management** via Google Cloud Secret Manager
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

### Production-Ready Pipeline
- **Cloud Run Pub/Sub workers** for async processing
- **JSON schema validation** with automated repair
- **Batch processing** with performance monitoring
- **Quality validation** with 99.1% success rate
- **Cost optimization**: $54.28 for 29,000 candidates

### Data Storage & Search
- **Firebase Firestore** for structured profile storage
- **Cloud SQL + pgvector** for semantic vector search
- **VertexAI embeddings** for high-quality search
- **Skill-aware search** with confidence-weighted ranking
- **Composite scoring**: skill_match (40%) + confidence (25%) + vector_similarity (25%) + experience_match (10%)
- **React web interface** with interactive skill visualization
- **Firebase Authentication** for secure access

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
┌─────────────────────────────────────────────────────────┐
│                    INPUT LAYER                           │
├─────────────────────────────────────────────────────────┤
│  CSV Files │ Resume PDFs │ DOCX │ Images │ Comments     │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│              CLOUD RUN PROCESSING                        │
├─────────────────────────────────────────────────────────┤
│  • Pub/Sub triggers Cloud Run workers                   │
│  • resume_extractor.py - Multi-format text extraction   │
│  • candidate_processor.py - Pipeline orchestration      │
│  • together_ai_client.py - API integration              │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│            TOGETHER AI + LLAMA 3.2 3B                   │
├─────────────────────────────────────────────────────────┤
│  Structured Prompt → Deep Analysis → JSON Output        │
│  • Career trajectory analysis                           │
│  • Leadership scope assessment                          │
│  • Company pedigree evaluation                          │
│  • Skills extraction and categorization                 │
│  • Cultural fit and work style analysis                 │
│  • Recruiter insights synthesis                         │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│              STORAGE & SEARCH LAYER                      │
├─────────────────────────────────────────────────────────┤
│  • Firebase Firestore - Structured JSON profiles        │
│  • Cloud SQL + pgvector - Vector embeddings             │
│  • VertexAI embeddings - Semantic search                │
│  • Cloud Functions - API endpoints                      │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│                  WEB INTERFACE                           │
├─────────────────────────────────────────────────────────┤
│  • React application                                    │
│  • Job description input                                │
│  • Semantic candidate matching                          │
│  • Ranked results with explanations                     │
└─────────────────────────────────────────────────────────┘
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

## Production Deployment Status

### ✅ Completed Components

1. **Cloud Run Worker**: Deployed and operational
   - Service: `candidate-enricher`
   - Region: `us-central1`
   - API Integration: Together AI working
   - Secret Management: Google Cloud Secret Manager

2. **Performance Validation**: 110 candidates tested
   - Success Rate: **99.1%**
   - Average Processing Time: **3.96s**
   - Throughput: **15.0 candidates/minute**
   - Cost: **$54.28 for 29,000 candidates**

3. **API Configuration**:
   - Model: `meta-llama/Llama-3.2-3B-Instruct-Turbo`
   - Endpoint: `https://api.together.xyz/v1`
   - Authentication: Verified working

4. **Embedding Comparison**: VertexAI vs Deterministic
   - **Recommendation**: VertexAI for production
   - Quality: Higher semantic accuracy
   - Performance: 0.2s avg processing time

### 🔄 Ready for 50-Candidate Batch Test

All components are operational for large-scale testing:

```bash
# Run comprehensive 50-candidate test
python3 scripts/performance_test_suite.py --candidates=50

# Expected results based on validation:
# - Success Rate: >99%
# - Processing Time: <4s avg
# - Total Cost: <$0.10
```

## JSON Output Structure

The cloud AI generates comprehensive structured profiles:

```json
{
  "candidate_id": "123",
  "career_trajectory": {
    "current_level": "Senior",
    "progression_speed": "fast",
    "trajectory_type": "technical_leadership",
    "years_experience": 12
  },
  "leadership_scope": {
    "has_leadership": true,
    "team_size": 15,
    "leadership_level": "manager"
  },
  "company_pedigree": {
    "company_tier": "enterprise",
    "stability_pattern": "stable"
  },
  "skill_assessment": {
    "technical_skills": {
      "core_competencies": ["Python", "AWS", "ML"],
      "skill_depth": "expert"
    }
  },
  "recruiter_insights": {
    "placement_likelihood": "high",
    "best_fit_roles": ["Tech Lead", "Engineering Manager"]
  },
  "search_optimization": {
    "keywords": ["python", "aws", "leadership"],
    "search_tags": ["senior", "technical_lead"]
  },
  "executive_summary": {
    "one_line_pitch": "Senior technical leader with fintech expertise",
    "overall_rating": 92
  }
}
```

## Performance Metrics (Multi-Stage Pipeline)

**Stage 1 (Basic Enhancement)**:
- Processing Speed: 3.96s average per candidate
- Cost: $0.0006 per candidate (Llama 3.2 3B)
- Success Rate: 99.1% validated

**Stage 2 (Contextual Intelligence)**:
- Model: Qwen2.5 Coder 32B for technical specialization
- Cost: $0.002 per candidate (4x Stage 1 for superior reasoning)
- Contextual Analysis: Company patterns, industry intelligence, role progression

**Stage 3 (Vector Generation)**:
- VertexAI embeddings: 768 dimensions
- Cost: $0.0002 per candidate
- **Total Pipeline Cost: $0.0026 per candidate**

## Key Files

### Cloud Run Worker
- `cloud_run_worker/main.py` - FastAPI application
- `cloud_run_worker/config.py` - Configuration with Secret Manager
- `cloud_run_worker/candidate_processor.py` - Processing pipeline
- `cloud_run_worker/together_ai_client.py` - API integration

### Testing & Validation
- `scripts/performance_test_suite.py` - Comprehensive testing
- `scripts/api_key_validation.py` - API connectivity test
- `scripts/embedding_bakeoff.py` - Embedding model comparison
- `scripts/prd_compliant_validation.py` - End-to-end validation

### Documentation
- `docs/PRODUCTION_DEPLOYMENT_GUIDE.md` - Deployment instructions
- `docs/AI_AGENT_HANDOVER.md` - Technical handover
- `docs/HANDOVER.md` - Performance results
- `.taskmaster/docs/prd.txt` - Product requirements

## Security & Privacy

- **API Key Security**: Stored in Google Cloud Secret Manager
- **IAM Controls**: Proper service account permissions
- **Network Security**: VPC-native Cloud Run deployment
- **Data Encryption**: At rest and in transit
- **Access Controls**: Firebase Authentication

## Current Status - Ready for Production

### ✅ All Systems Operational
- **Cloud Run**: Deployed and tested
- **Together AI API**: Validated and working
- **Secret Management**: Configured and secure
- **Performance**: Exceeds requirements (99.1% success)
- **Cost**: Under budget ($54.28 for 29K candidates)

### 🚀 Next Step: 50-Candidate Batch Test

The system is fully operational and ready for your 50-candidate validation:

```bash
# Execute the batch test
python3 scripts/performance_test_suite.py --batch-size=50 --full-validation

# Monitor via Cloud Console
echo "View logs: https://console.cloud.google.com/run/detail/us-central1/candidate-enricher"
```

## Support & Documentation

- **Production Guide**: `docs/PRODUCTION_DEPLOYMENT_GUIDE.md`
- **Performance Results**: `docs/HANDOVER.md`
- **Technical Details**: `docs/AI_AGENT_HANDOVER.md`
- **Task Management**: `.taskmaster/docs/` directory

---

**System Status**: ✅ Production Ready | **Last Validated**: 2025-09-11 | **Success Rate**: 99.1%