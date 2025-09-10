# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
- **AI**: Together AI (Llama 3.1 8B Instruct Turbo)
- **Storage**: Firebase Firestore
- **Vector DB**: Cloud SQL (PostgreSQL + pgvector)
- **API**: Firebase Cloud Functions / Cloud Run
- **Python**: Core processing (scripts in `/scripts`)
- **TypeScript**: Cloud Functions (`/functions`)
- **React**: UI (`/headhunter-ui`)

## TDD Protocol
- Always begin by writing/adjusting tests for the selected Task Master task.
- Use pytest/jest as appropriate; ensure tests fail before implementation.
- Implement, make tests pass, refactor, then document and commit.

### Key Local Processing Scripts

#### Primary Processors (All use Ollama locally)
- `llm_processor.py`: Main pipeline orchestrator
- `intelligent_batch_processor.py`: Resource-aware processing with system monitoring
- `enhanced_batch_processor.py`: Comprehensive analysis with all data fields
- `enhanced_processor_full.py`: Most detailed analysis with complete prompts
- `high_throughput_processor.py`: Optimized for speed with parallel processing

#### Analysis Modules
- `llm_prompts.py`: Resume analysis prompts for Ollama
- `recruiter_prompts.py`: Comment analysis prompts for Ollama
- `resume_extractor.py`: Multi-format text extraction
- `quality_validator.py`: Output validation

## Data Flow

1. **Input**: CSV files in `CSV files/` directory
2. **Local Processing**: 
   - Extract text from resumes
   - Send to Ollama with structured prompts
   - Llama 3.1:8b analyzes and returns JSON
3. **Validation**: Quality checks on LLM output
4. **Storage**: Structured profiles to Firestore
5. **Access**: Cloud Functions provide API endpoints (no AI processing)

## Local LLM Configuration

- **Model**: Llama 3.1:8b via Ollama
- **Endpoint**: `http://localhost:11434`
- **Memory Usage**: ~5-6 GB when loaded
- **Processing Time**: 30-60 seconds per candidate
- **No External APIs**: All AI processing is local

## Development Patterns

### Local Processing Priority
- Always use Ollama for LLM tasks
- Never send candidate data to external AI services
- Test locally before any deployment
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

### Local Processing Command
```bash
# Process with Ollama (no cloud AI)
python3 scripts/llm_processor.py input.csv -o results.json

# Resource-aware processing
python3 scripts/intelligent_batch_processor.py

# Comprehensive analysis
python3 scripts/enhanced_processor_full.py
```

### Python API
```python
from scripts.llm_processor import LLMProcessor

processor = LLMProcessor()  # Uses Ollama locally
profiles, stats = processor.process_batch('data.csv', output_file='results.json')
```

## JSON Output Structure (Generated by Local Llama 3.1:8b)

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
- **All AI processing is local** - No data leaves your machine for AI analysis
- **Ollama runs locally** - Complete control over the LLM
- **No Vertex AI** - Despite old references in code, we don't use it
- **Firebase is storage only** - Not for AI processing

### Performance Considerations
- Ollama needs ~8GB RAM for optimal performance
- Process in batches of 50-100 for stability
- Monitor system resources with `intelligent_batch_processor.py`
- Use `high_throughput_processor.py` for speed when resources allow

## Dependencies

### Python (Local Processing)
- subprocess: For calling Ollama
- PyPDF2, python-docx: Document processing
- pytesseract, Pillow: OCR
- google-cloud-firestore: Database storage only
- psutil: Resource monitoring

### Node.js/TypeScript (API & Storage)
- firebase-admin, firebase-functions
- zod: Schema validation
- express, cors: API framework
- NO @google-cloud/aiplatform needed

## Task Master AI Instructions
**Import Task Master's development workflow commands and guidelines, treat as if import is in the main CLAUDE.md file.**
@./.taskmaster/CLAUDE.md
