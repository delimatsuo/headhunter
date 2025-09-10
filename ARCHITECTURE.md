# Headhunter System Architecture

## 🎯 Core Design Principle

**100% Local AI Processing** - All LLM analysis and candidate insights generation happens locally using Ollama with Llama 3.1 8b. Cloud services are used only for data storage and API endpoints.

## System Components

### 1. Local Processing Layer (Python)

The heart of the system - where all AI intelligence resides:

```
┌──────────────────────────────────────────────────┐
│           LOCAL PROCESSING LAYER                  │
├──────────────────────────────────────────────────┤
│  Operating System: macOS/Linux                   │
│  Runtime: Python 3.10+                           │
│  LLM Engine: Ollama                              │
│  Model: Llama 3.1:8b (4.9 GB)                   │
│  Memory Required: 8GB+ RAM                       │
└──────────────────────────────────────────────────┘
```

**Key Scripts:**
- `llm_processor.py` - Main orchestrator
- `intelligent_batch_processor.py` - Resource-aware processing
- `enhanced_processor_full.py` - Comprehensive analysis
- `llm_prompts.py` - Resume analysis templates
- `recruiter_prompts.py` - Comment analysis templates
- `resume_extractor.py` - Multi-format text extraction

**Processing Flow:**
1. Extract text from resumes (PDF, DOCX, images)
2. Structure prompts for Ollama
3. Send to local Llama 3.1:8b model
4. Parse JSON response
5. Validate output quality
6. Store in Firestore

### 2. Data Storage Layer (Firebase/GCP)

Cloud services for persistence and access - NO AI processing:

```
┌──────────────────────────────────────────────────┐
│              STORAGE LAYER                        │
├──────────────────────────────────────────────────┤
│  Database: Firestore                             │
│  File Storage: Cloud Storage                     │
│  Authentication: Firebase Auth                   │
│  API: Cloud Functions (Node.js)                  │
│  Hosting: Firebase Hosting                       │
└──────────────────────────────────────────────────┘
```

**Cloud Functions (API endpoints only):**
- `healthCheck` - System monitoring
- `searchCandidates` - Query Firestore
- `uploadCandidates` - Batch upload
- `quickMatch` - Fast search

### 3. Web Interface Layer (React)

User-facing search application:

```
┌──────────────────────────────────────────────────┐
│              WEB INTERFACE                        │
├──────────────────────────────────────────────────┤
│  Framework: React                                │
│  Authentication: Firebase Auth                   │
│  API Client: Firebase SDK                        │
│  Hosting: Firebase Hosting                       │
└──────────────────────────────────────────────────┘
```

## Data Flow Architecture

```
Step 1: Input Processing (Local)
================================
CSV Files → Python Scripts → Text Extraction
                ↓
         Resume Text + Comments

Step 2: AI Analysis (Local Only)
=================================
        Structured Prompts
                ↓
    Ollama (localhost:11434)
                ↓
        Llama 3.1:8b Model
                ↓
    JSON Structured Output

Step 3: Storage (Cloud)
========================
    Validated JSON Profiles
                ↓
         Firestore Database
                ↓
        Search Indexing

Step 4: Search & Retrieval (Cloud + Web)
=========================================
    Job Description Input (Web)
                ↓
      Search API (Cloud Functions)
                ↓
        Firestore Query
                ↓
    Ranked Results (Web Display)
```

## JSON Data Structure

Generated locally by Llama 3.1:8b, stored in Firestore:

```json
{
  "candidate_id": "unique_id",
  "processing_metadata": {
    "processed_by": "ollama_llama3.1:8b",
    "processed_at": "2024-01-01T00:00:00Z",
    "processing_time_seconds": 45,
    "local_processing": true
  },
  "career_trajectory": {
    "current_level": "Senior/Principal/Executive",
    "progression_speed": "slow/steady/fast",
    "trajectory_type": "IC/management/hybrid",
    "years_experience": 10,
    "velocity": "accelerating/steady/plateauing"
  },
  "leadership_scope": {
    "has_leadership": true,
    "team_size": 15,
    "leadership_level": "lead/manager/director/vp",
    "leadership_style": "collaborative/directive"
  },
  "company_pedigree": {
    "company_tier": "startup/midmarket/enterprise/faang",
    "company_list": ["Company A", "Company B"],
    "stability_pattern": "stable/job_hopper"
  },
  "skill_assessment": {
    "technical_skills": {
      "core_competencies": ["Python", "AWS", "ML"],
      "skill_depth": "expert/advanced/intermediate"
    },
    "soft_skills": {
      "communication": "exceptional/strong/developing",
      "leadership": "exceptional/strong/developing"
    }
  },
  "cultural_signals": {
    "strengths": ["innovation", "collaboration"],
    "red_flags": [],
    "work_style": "independent/collaborative/hybrid"
  },
  "recruiter_insights": {
    "sentiment": "positive/neutral/negative",
    "placement_likelihood": "high/medium/low",
    "best_fit_roles": ["Tech Lead", "Engineering Manager"],
    "salary_expectations": "below_market/market/above_market"
  },
  "search_optimization": {
    "keywords": ["generated", "locally", "by", "llm"],
    "search_tags": ["senior", "technical_lead"],
    "matching_scores": {}
  },
  "executive_summary": {
    "one_line_pitch": "Generated by local LLM",
    "ideal_next_role": "Based on trajectory analysis",
    "overall_rating": 85
  }
}
```

## Security & Privacy Architecture

### Data Privacy Layers

1. **Local Processing Isolation**
   - All AI processing on local machine
   - No candidate data sent to external AI services
   - Ollama runs entirely offline capable

2. **Cloud Storage Security**
   - Firebase Authentication required
   - Firestore security rules enforced
   - Role-based access control

3. **Network Security**
   - HTTPS only for web interface
   - API authentication tokens
   - CORS policies enforced

### Data Flow Security

```
Local Machine (Trusted)
    ↓ [Processed Data Only]
Firebase/GCP (Encrypted)
    ↓ [Authenticated Access]
Web Client (HTTPS)
```

## Performance Characteristics

### Local Processing (Ollama + Llama 3.1:8b)
- **Startup Time**: 5-10 seconds (model loading)
- **Per Candidate**: 30-60 seconds comprehensive analysis
- **Batch Processing**: 50-100 candidates/hour
- **Memory Usage**: 5-6 GB when model loaded
- **CPU Usage**: 80-100% during inference

### Optimization Strategies
1. **Batch Processing**: Process multiple candidates in sequence
2. **Resource Monitoring**: `intelligent_batch_processor.py` adapts to system resources
3. **Parallel Extraction**: Text extraction can run in parallel
4. **Caching**: Model stays loaded between requests
5. **Retry Logic**: Automatic retries for transient failures

## Scalability Architecture

### Current Capacity
- Single machine: 50-100 candidates/hour
- Limited by local CPU/RAM
- No cloud AI costs

### Scaling Options

1. **Vertical Scaling**
   - Add more RAM (16GB+ recommended)
   - Use GPU acceleration (10x speedup possible)
   - Upgrade to faster CPU

2. **Horizontal Scaling**
   - Run multiple Ollama instances
   - Distribute processing across machines
   - Use job queue for coordination

3. **Future Architecture**
   ```
   Multiple Processing Nodes
           ↓
   Shared Firestore Database
           ↓
   Single Web Interface
   ```

## Cost Analysis

### Current Architecture Costs
- **AI Processing**: $0 (local Ollama)
- **Storage**: Firestore free tier or ~$0.18/GB/month
- **Hosting**: Firebase free tier or ~$10/month
- **Total**: Near zero for AI, minimal for storage

### Comparison with Cloud AI
- **OpenAI GPT-4**: ~$30/1000 candidates
- **Google Vertex AI**: ~$20/1000 candidates
- **Local Ollama**: $0/∞ candidates

## Development & Deployment

### Local Development
```bash
# Start Ollama
ollama serve

# Process candidates
python scripts/intelligent_batch_processor.py

# Start web interface
cd headhunter-ui && npm start
```

### Production Deployment
```bash
# Deploy Cloud Functions
cd functions && npm run deploy

# Deploy web interface
cd headhunter-ui && npm run build
firebase deploy --only hosting
```

### Monitoring
- Local: System resource monitoring via `psutil`
- Cloud: Firebase console for API usage
- Logs: Local Python logs + Cloud Function logs

## Technology Stack Summary

| Layer | Technology | Purpose |
|-------|------------|---------|
| AI Engine | Ollama + Llama 3.1:8b | Local LLM processing |
| Processing | Python 3.10+ | Orchestration & data handling |
| Text Extraction | PyPDF2, python-docx, Tesseract | Multi-format support |
| Database | Firestore | Structured data storage |
| API | Cloud Functions (Node.js) | Data access endpoints |
| Web UI | React | User interface |
| Auth | Firebase Auth | Security |
| Hosting | Firebase Hosting | Web deployment |

## Key Architectural Decisions

1. **Why Local LLM?**
   - Complete data privacy
   - Zero AI API costs
   - Full control over processing
   - No rate limits or quotas

2. **Why Ollama?**
   - Easy local deployment
   - Good performance
   - Model management
   - REST API interface

3. **Why Firestore?**
   - Serverless scaling
   - Real-time sync capable
   - Good query performance
   - Firebase integration

4. **Why React?**
   - Modern UI capabilities
   - Firebase SDK support
   - Developer familiarity
   - Component reusability

## Conclusion

This architecture prioritizes data privacy and cost efficiency by processing all AI workloads locally while leveraging cloud services only for storage and access. The system can analyze 50-100 candidates per hour with zero AI costs and complete data control.