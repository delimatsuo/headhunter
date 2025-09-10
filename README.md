# Headhunter - AI-Powered Recruitment Analytics

IMPORTANT UPDATE (2025-09-10): Processing now runs in the cloud via Together AI with results in Firebase and vectors in a managed vector database (Cloud SQL + pgvector). Previous references to “100% local processing” are historical and superseded by the new architecture. See docs/HANDOVER.md and .taskmaster/docs/prd.txt for the authoritative design.

## 🎯 Core Architecture

**100% Local Processing** - No cloud AI services required. All candidate analysis, profile generation, and insights extraction happens on your local machine using Ollama with Llama 3.1 8b.

## Features

### Local LLM Processing
- **Ollama with Llama 3.1 8b** for all AI analysis
- **Complete privacy** - No data sent to external AI services
- **Deep candidate analysis** including:
  - Career trajectory and progression patterns
  - Leadership scope and management experience
  - Company pedigree and tier analysis
  - Technical and soft skills extraction
  - Cultural fit signals and work style
  - Recruiter sentiment and insights

### Resume Text Extraction
Multi-format support for extracting text from:
- PDF files (PyPDF2 or pdftotext)
- Microsoft Word documents (.docx)
- Plain text files (.txt)
- Images with OCR (PNG, JPG using Tesseract)

### Comprehensive Analysis Pipeline
- **Structured prompt engineering** for consistent analysis
- **JSON output generation** with validated schemas
- **Batch processing** with resource management
- **Quality validation** for output consistency
- **60+ specialized processing scripts** for different use cases

### Data Storage & Search
- **Firestore** for structured profile storage
- **Local embeddings generation** for semantic search
- **React web interface** for searching candidates
- **Firebase Authentication** for secure access

## Prerequisites

- **macOS** (tested on Darwin 24.6.0) or Linux
- **Python 3.x**
- **Ollama** installed locally
- **5GB+ free disk space** for Llama 3.1 8b model
- **8GB+ RAM** recommended for optimal performance
- **Node.js** (for web interface)
- **Firebase CLI** (for deployment)

## Installation

### 1. Install Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh
```

### 2. Pull Llama 3.1 8b Model

```bash
# Download the model (4.9 GB)
ollama pull llama3.1:8b

# Verify installation
ollama list
# Should show: llama3.1:8b with size ~4.9 GB

# Test the model
ollama run llama3.1:8b "Hello, are you working?"
```

### 3. Python Dependencies

```bash
# Core dependencies
pip install -r requirements.txt

# Optional for enhanced features
pip install PyPDF2           # PDF extraction
pip install python-docx       # DOCX extraction
pip install pytesseract pillow # OCR from images
pip install reportlab         # Test file generation
```

### 4. Firebase Setup (for Web Interface)

```bash
# Install Firebase CLI
npm install -g firebase-tools

# Login to Firebase
firebase login

# Initialize project
firebase init

# Configure Firestore for data storage
# Select: Firestore, Functions, Hosting
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
│              LOCAL PROCESSING LAYER                      │
├─────────────────────────────────────────────────────────┤
│  • resume_extractor.py - Multi-format text extraction   │
│  • llm_processor.py - Pipeline orchestration            │
│  • intelligent_batch_processor.py - Resource management  │
│  • enhanced_processor_full.py - Comprehensive analysis  │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│               OLLAMA + LLAMA 3.1 8B                      │
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
│  • Firestore - Structured JSON profiles                 │
│  • Local embeddings - Semantic search capabilities      │
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

## Key Processing Scripts

### Core Pipeline
- `llm_processor.py` - Main orchestrator for candidate processing
- `llm_prompts.py` - Resume analysis prompt templates
- `recruiter_prompts.py` - Recruiter comment analysis
- `resume_extractor.py` - Multi-format text extraction
- `quality_validator.py` - Output validation and quality checks

### Batch Processing
- `intelligent_batch_processor.py` - Resource-aware batch processing
- `enhanced_batch_processor.py` - Enhanced analysis with all data
- `high_throughput_processor.py` - Optimized for speed
- `enhanced_processor_full.py` - Most comprehensive analysis

### Data Management
- `comprehensive_merge.py` - Merge multiple data sources
- `process_real_data_comprehensive.py` - Production data processing
- `upload_to_firestore.py` - Database upload utilities

## Usage Examples

### Process Candidates from CSV

```bash
# Basic processing
python3 scripts/llm_processor.py candidates.csv -o results.json

# With resource monitoring
python3 scripts/intelligent_batch_processor.py

# Enhanced comprehensive analysis
python3 scripts/enhanced_processor_full.py
```

### Extract Resume Text

```bash
# Single file
python3 scripts/resume_extractor.py resume.pdf

# Multiple files
python3 scripts/resume_extractor.py *.pdf -o extracted/
```

### Run Web Interface

```bash
# Start local development
cd headhunter-ui
npm start

# Deploy to Firebase
npm run build
firebase deploy
```

## JSON Output Structure

The local LLM generates comprehensive structured profiles:

```json
{
  "candidate_id": "123",
  "name": "John Doe",
  "career_trajectory": {
    "current_level": "Senior",
    "progression_speed": "fast",
    "trajectory_type": "technical_leadership",
    "years_experience": 12,
    "velocity": "accelerating"
  },
  "leadership_scope": {
    "has_leadership": true,
    "team_size": 15,
    "leadership_level": "manager",
    "leadership_style": "collaborative"
  },
  "company_pedigree": {
    "company_tier": "enterprise",
    "company_tiers": ["Google", "Meta", "Startup"],
    "stability_pattern": "stable"
  },
  "cultural_signals": {
    "strengths": ["innovation", "collaboration"],
    "red_flags": [],
    "work_style": "hybrid"
  },
  "skill_assessment": {
    "technical_skills": {
      "core_competencies": ["Python", "AWS", "ML"],
      "skill_depth": "expert"
    },
    "soft_skills": {
      "communication": "exceptional",
      "leadership": "strong"
    }
  },
  "recruiter_insights": {
    "placement_likelihood": "high",
    "best_fit_roles": ["Tech Lead", "Engineering Manager"],
    "salary_expectations": "above_market",
    "availability": "short_notice"
  },
  "search_optimization": {
    "keywords": ["python", "aws", "leadership", "fintech"],
    "search_tags": ["senior", "technical_lead", "high_performer"]
  },
  "executive_summary": {
    "one_line_pitch": "Senior technical leader with fintech expertise",
    "ideal_next_role": "VP Engineering at growth-stage startup",
    "overall_rating": 92
  }
}
```

## Testing

```bash
# Test Ollama setup
python3 tests/test_ollama_setup.py

# Test LLM prompts and analysis
python3 tests/test_llm_prompts.py

# Test complete pipeline
PYTHONPATH=scripts python tests/test_llm_processor.py

# Test text extraction
python tests/test_resume_extractor.py

# Integration tests
python tests/test_integration.py
```

## Performance Metrics

- **Processing Speed**: 30-60 seconds per candidate (comprehensive analysis)
- **Batch Processing**: 50-100 candidates per hour
- **Model Memory**: ~5-6 GB when loaded
- **Token Generation**: 50-100 tokens/second
- **Extraction Speed**: 1-5 seconds per resume file

## Project Structure

```
headhunter/
├── scripts/              # 60+ Python processing scripts
│   ├── Core Pipeline
│   ├── Batch Processors
│   ├── Data Management
│   └── Utilities
├── tests/                # Comprehensive test suite
├── headhunter-ui/        # React web interface
├── functions/            # Firebase Cloud Functions
├── CSV files/            # Input data directory
└── docs/                 # Documentation
```

## Privacy & Security

- **100% Local Processing**: All AI analysis happens on your machine
- **No External AI APIs**: No data sent to OpenAI, Anthropic, or Google
- **Secure Storage**: Firebase authentication and Firestore rules
- **Data Control**: Complete ownership of your candidate data

## Current Status

All core features implemented and tested:
- ✅ Ollama with Llama 3.1 8b integration
- ✅ Resume analysis prompts
- ✅ Recruiter comment analysis
- ✅ Complete processing pipeline
- ✅ Multi-format text extraction
- ✅ Batch processing with resource management
- ✅ Quality validation system
- ✅ Firestore integration
- ✅ React search interface
- ✅ Authentication system

## Contributing

This project uses local LLMs for complete data privacy. When contributing:
1. Ensure all processing remains local
2. Test with Ollama before committing
3. Maintain structured JSON output format
4. Document any new processing scripts

## License

[Your License Here]

## Contact

[Your Contact Information]
