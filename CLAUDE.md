# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚨 MANDATORY PRE-WORK PROTOCOL (NEVER SKIP)

**THESE RULES ARE ENFORCED ON EVERY TASK. VIOLATION = SESSION TERMINATION.**

### Before ANY implementation work, Claude MUST:

1. **Run `task-master next`** - Check what task should be worked on
2. **Run `task-master show <id>`** - Read the full task details  
3. **Read PRD section** relevant to the task (cite specific line numbers from `.taskmaster/docs/prd.txt`)
4. Proceed directly after verifying PRD alignment; do not pause for confirmation unless scope changes.

### VIOLATION DETECTION RULES
- If user requests work that's NOT in the current task: **STOP immediately**
- Ask: "This seems outside the current task [ID]. Should we add this as a new task first?"
- **Don't implement** until task is updated in TaskMaster

### SCOPE CHANGE PROTOCOL  
- If request seems outside PRD scope: **Reference PRD line numbers** showing what's planned
- Ask: "This appears to be a scope change from PRD line [X]. Should we update the PRD first?"
- **Don't proceed** without explicit approval

### ARCHITECTURE COMPLIANCE
- **Firestore**: For operational data (profiles, CRUD, real-time updates)
- **Cloud SQL + pgvector**: For search and embeddings (PRD lines 74, 79, 143)
- **Together AI**: For production AI processing (PRD lines 77, 139-141)
- **Never suggest architectural changes** without referencing PRD and getting approval

### MANDATORY SESSION START TEMPLATE
```
🚨 WORK SESSION COMPLIANCE CHECK
Current Task: [from task-master next]
PRD Reference: [specific line numbers from prd.txt]
Alignment Status: [request matches PRD + task? yes/no]
Scope Status: [in scope / needs approval / scope change]
Architecture: [follows PRD design? yes/no]
Proceeding with: [only if all above are YES]
```

## Project Overview

Headhunter is an AI-powered recruitment analytics system that processes candidate data using **Together AI** (cloud chat completions) to generate enhanced profiles, with results stored in Firebase and vectors in **Cloud SQL + pgvector** for fast semantic search. The system extracts deep insights from resumes and recruiter comments and performs intelligent skill inference with confidence levels.

TDD is mandatory for all work. See `docs/TDD_PROTOCOL.md`.

## 🎯 Core Architecture Principle

**Cloud-Triggered AI Processing** - Batch processors or Cloud Run workers call Together AI with recruiter-grade prompts. Firestore persists enhanced profiles; Cloud SQL (pgvector) stores embeddings; Cloud Functions/Run exposes search APIs. Local-only processing is available for development/testing but is not used in production.

## Commands

### Testing
```bash
# Run all tests
python3 -m pytest tests/

# Test specific components
python3 tests/test_ollama_setup.py
python3 tests/test_llm_prompts.py
PYTHONPATH=scripts python tests/test_llm_processor.py
python tests/test_resume_extractor.py
python tests/test_quality_validator.py
python tests/test_integration.py
```

### Processing (Primary Pipeline)
```bash
# Together AI batch/streaming processors (cloud-oriented)
python3 scripts/together_ai_processor.py
python3 scripts/firebase_streaming_processor.py
python3 scripts/together_ai_firestore_processor.py
python3 scripts/intelligent_skill_processor.py     # Explicit vs inferred skills

# PRD Compliance Validation
python3 scripts/prd_compliant_validation.py        # Test actual Together AI architecture
```

### Cloud Functions / Cloud Run (Storage, API, Search)
```bash
# Navigate to functions directory first
cd functions

# Build TypeScript
npm run build

# Local testing
npm run serve  # Runs build + emulators
firebase emulators:start

# Deploy
npm run deploy

# Testing and linting
npm test
npm run lint
npm run lint:fix

# (Planned) Cloud Run worker for Pub/Sub-driven enrichment
# gcloud run deploy candidate-enricher --source . --region=us-central1 --project=<PROJECT>
```

## Architecture

### Processing Pipeline (Primary)
1. **Data Ingestion**: CSV + merged JSON uploaded to GCS
2. **Enrichment**: Cloud Run worker or batch processors call Together AI and produce structured JSON
3. **Skill Inference**: `intelligent_skill_processor.py` adds explicit vs inferred skills with confidence
4. **Validation**: JSON schema validation, parse-repair, retries
5. **Storage**: Firestore (`candidates/`, `enriched_profiles/`) + Cloud SQL (pgvector) for embeddings

### Technology Stack
- **AI**: Together AI (Qwen 2.5 32B Instruct) - PRIMARY PRODUCTION
- **Storage**: Firebase Firestore
- **Vector DB**: Cloud SQL (PostgreSQL + pgvector) OR VertexAI embeddings
- **API**: Firebase Cloud Functions / Cloud Run
- **Python**: Core processing (scripts in `/scripts`)
- **TypeScript**: Cloud Functions (`/functions`)
- **React**: UI (`/headhunter-ui`)
- **Cloud Run**: Pub/Sub worker for scalable processing

## TDD Protocol
- Always begin by writing/adjusting tests for the selected Task Master task.
- Use pytest/jest as appropriate; ensure tests fail before implementation.
- Implement, make tests pass, refactor, then document and commit.

### Key Local Processing Scripts

#### Primary Processors (Together AI Cloud Processing)
- `together_ai_processor.py`: Main Together AI batch processor
- `firebase_streaming_processor.py`: Streaming to Firebase
- `together_ai_firestore_processor.py`: Direct Firestore integration
- `intelligent_skill_processor.py`: Skill analysis and inference
- `prd_compliant_validation.py`: PRD architecture validation

#### Legacy Local Processors (Development Only)
- `llm_processor.py`: Local Ollama pipeline orchestrator
- `intelligent_batch_processor.py`: Resource-aware local processing
- `enhanced_batch_processor.py`: Local comprehensive analysis
- `enhanced_processor_full.py`: Local detailed analysis
- `high_throughput_processor.py`: Local parallel processing

#### Analysis Modules
- `llm_prompts.py`: Resume analysis prompts for Ollama
- `recruiter_prompts.py`: Comment analysis prompts for Ollama
- `resume_extractor.py`: Multi-format text extraction
- `quality_validator.py`: Output validation

## Data Flow

### Production Pipeline (Together AI)
1. **Input**: CSV files uploaded to GCS or processed locally
2. **Cloud Processing**: 
   - Extract text from resumes
   - Send to Together AI with structured prompts
   - meta-llama/Llama-3.1-8B-Instruct-Turbo analyzes and returns JSON
3. **Validation**: Schema validation, JSON repair, retries
4. **Storage**: Structured profiles to Firestore
5. **Embeddings**: VertexAI text-embedding-004 for search
6. **Access**: Cloud Functions provide search APIs

### Development Pipeline (Local Ollama)
1. **Input**: Local CSV files
2. **Local Processing**: 
   - Extract text from resumes
   - Send to local Ollama with structured prompts
   - Llama 3.1:8b analyzes and returns JSON
3. **Validation**: Quality checks on LLM output
4. **Storage**: Structured profiles to Firestore
5. **Access**: Cloud Functions provide API endpoints

## AI Processing Configuration

### Production (Together AI)
- **Model**: meta-llama/Llama-3.1-8B-Instruct-Turbo
- **Endpoint**: `https://api.together.xyz/v1/chat/completions`
- **API Key**: TOGETHER_API_KEY environment variable
- **Processing Time**: 5-15 seconds per candidate
- **Cost**: ~$0.10 per million tokens

### Development Fallback (Local Ollama)
- **Model**: Llama 3.1:8b via Ollama
- **Endpoint**: `http://localhost:11434`
- **Memory Usage**: ~5-6 GB when loaded
- **Processing Time**: 30-60 seconds per candidate
- **Use Case**: Development and testing only

## Development Patterns

### Production Processing Priority
- Use Together AI for production LLM tasks
- Cloud Run workers for scalable processing
- Pub/Sub for asynchronous task distribution
- Stream results directly to Firestore

### Development Processing
- Use Ollama for local development and testing
- Test locally before cloud deployment
- Monitor resource usage during batch processing

### Error Handling
- Retry logic for Ollama timeouts
- Graceful degradation for resource constraints
- Progress tracking for batch operations
- Automatic backups during processing

### Data Validation
- JSON schema validation for LLM outputs
- Quality metrics tracking
- Consistency checks across batches

## Processing Pipeline Usage

### CSV Input Format
```csv
candidate_id,name,role_level,resume_file,recruiter_comments
1,John Doe,Senior,resumes/john_doe.pdf,"Great technical skills"
```

### Production Processing Commands
```bash
# Process with Together AI (production)
python3 scripts/together_ai_processor.py

# Stream to Firebase
python3 scripts/firebase_streaming_processor.py

# Validate PRD compliance
python3 scripts/prd_compliant_validation.py
```

### Development Processing Commands
```bash
# Process with Ollama (development only)
python3 scripts/llm_processor.py input.csv -o results.json

# Resource-aware processing
python3 scripts/intelligent_batch_processor.py

# Comprehensive analysis
python3 scripts/enhanced_processor_full.py
```

### Python API
```python
# Production Together AI
from scripts.together_ai_processor import TogetherAIProcessor

async with TogetherAIProcessor(api_key) as processor:
    results = await processor.process_batch(candidates)

# Development Ollama
from scripts.llm_processor import LLMProcessor

processor = LLMProcessor()  # Uses Ollama locally
profiles, stats = processor.process_batch('data.csv', output_file='results.json')
```

## JSON Output Structure (Generated by Together AI or Local Llama 3.1:8b)

```json
{
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
  "cultural_signals": {
    "strengths": ["innovation", "collaboration"],
    "work_style": "hybrid"
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

## Important Notes

### Privacy & Security
- **Production uses Together AI** - Secure cloud processing per PRD
- **Development uses local Ollama** - Complete control during development
- **VertexAI for embeddings only** - No LLM processing
- **Firebase for storage and APIs** - Not for AI processing
- **Minimal PII in prompts** - Data privacy safeguards

### Performance Considerations
- Ollama needs ~8GB RAM for optimal performance
- Process in batches of 50-100 for stability
- Monitor system resources with `intelligent_batch_processor.py`
- Use `high_throughput_processor.py` for speed when resources allow

## Dependencies

### Python (Processing)
- aiohttp: For Together AI API calls
- requests: For HTTP requests
- subprocess: For calling local Ollama (dev only)
- PyPDF2, python-docx: Document processing
- pytesseract, Pillow: OCR
- google-cloud-firestore: Database storage
- google-cloud-aiplatform: VertexAI embeddings
- psutil: Resource monitoring
- pydantic: Data validation
- fastapi: Cloud Run service framework

### Node.js/TypeScript (API & Storage)
- firebase-admin, firebase-functions
- zod: Schema validation
- express, cors: API framework
- NO @google-cloud/aiplatform needed

## Task Master AI Instructions
**Import Task Master's development workflow commands and guidelines, treat as if import is in the main CLAUDE.md file.**
@./.taskmaster/CLAUDE.md
