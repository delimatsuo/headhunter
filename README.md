# Headhunter - AI-Powered Recruitment Analytics

An intelligent system for analyzing recruitment data using local LLMs to extract insights from unstructured candidate information.

## Features

- **Local LLM processing** using Ollama and Llama 3.1 8b
- **Resume text extraction** from multiple formats:
  - PDF files (using PyPDF2 or pdftotext)
  - Microsoft Word documents (.docx) 
  - Plain text files (.txt)
  - Images with OCR (PNG, JPG, etc. using Tesseract)
- **Integrated processing pipeline** with CSV input/JSON output
- **Resume analysis** with multi-dimensional assessment:
  - Career trajectory and progression speed
  - Leadership scope and experience
  - Company pedigree analysis
  - Technical and soft skills extraction
  - Cultural fit signals
- **Recruiter comment analysis**:
  - Sentiment and recommendation extraction
  - Strengths, concerns, and red flags identification
  - Leadership insights from feedback
  - Cultural fit assessment
  - Readiness evaluation
  - Competitive advantage identification
- **Batch processing capabilities**:
  - CSV file input with flexible schema
  - JSON structured output with metadata
  - Processing statistics and performance metrics
  - Health monitoring and error handling
- **Command-line interface** for automation
- **Python API** for integration

## Prerequisites

- macOS (tested on Darwin 24.6.0)
- Python 3.x
- Ollama installed locally
- At least 5GB free disk space for Llama 3.1 8b model
- Google Cloud Platform account (for cloud features)
- Firebase CLI (for deployment)

### Optional Dependencies for Resume Text Extraction

For full functionality, install these packages:

```bash
# For PDF extraction
pip install PyPDF2

# For DOCX extraction  
pip install python-docx

# For OCR from images
brew install tesseract  # or pip install pytesseract pillow

# For generating test files
pip install reportlab

# For Google Cloud Platform features
pip install google-cloud-aiplatform google-cloud-firestore google-cloud-storage
```

## Installation

### 1. Ollama Setup

Ollama is already installed on this system. To install on a new system:

```bash
# macOS
brew install ollama

# Or download from https://ollama.ai
```

### 2. Llama 3.1 8b Model

Pull the Llama 3.1 8b model (4.9 GB):

```bash
ollama pull llama3.1:8b
```

Verify installation:

```bash
ollama list
# Should show: llama3.1:8b with size ~4.9 GB
```

### 3. Test Model

```bash
ollama run llama3.1:8b "Hello, are you working?"
```

### 4. Google Cloud Platform Setup (Optional)

For cloud features like Vertex AI, Firestore, and Cloud Functions:

```bash
# Run automated setup script
./scripts/setup_gcp_infrastructure.sh

# Or follow manual setup in docs/gcp-infrastructure-setup.md

# Test connectivity
python scripts/test_gcp_connectivity.py
```

The GCP infrastructure includes:
- **Project ID**: `headhunter-ai-0088`
- **Vertex AI**: Enhanced LLM processing
- **Firestore**: Structured data storage
- **Cloud Storage**: File storage for resumes
- **Cloud Functions**: Serverless API endpoints
- **Firebase Hosting**: Web application deployment

## Testing

Run the test suites:

```bash
# Test Ollama setup
python3 tests/test_ollama_setup.py

# Test LLM prompts and resume analysis
python3 tests/test_llm_prompts.py

# Test LLM processing pipeline
PYTHONPATH=scripts python tests/test_llm_processor.py

# Test resume text extraction
python tests/test_resume_extractor.py

# Test GCP infrastructure connectivity
python scripts/test_gcp_connectivity.py
```

Tests include:
- Ollama installation verification
- Model availability check
- Integration test with model response
- API endpoint accessibility
- Performance benchmarks
- Resume analysis prompt validation
- JSON output structure verification
- Multi-level career assessment tests
- Resume text extraction from PDF, DOCX, TXT, and image files
- OCR functionality validation
- Batch file processing tests
- Error handling for unsupported formats
- GCP infrastructure connectivity and permissions
- Firestore database operations
- Cloud Storage access
- Vertex AI API functionality

## Project Structure

```
headhunter/
├── .taskmaster/         # Task management system
│   ├── tasks/          # Task definitions
│   └── docs/           # PRD and documentation
├── tests/              # Test suites
│   ├── test_ollama_setup.py    # Ollama installation tests
│   ├── test_llm_prompts.py     # Resume analysis tests  
│   ├── test_llm_processor.py   # Pipeline integration tests
│   ├── test_resume_extractor.py # Text extraction tests
│   ├── sample_resumes/         # Test resume files
│   └── sample_resumes.py       # Test data
├── scripts/            # Utility scripts
│   ├── llm_prompts.py          # Resume analysis prompts
│   ├── recruiter_prompts.py    # Recruiter comment analysis
│   ├── llm_processor.py        # Integrated processing pipeline
│   ├── resume_extractor.py     # Text extraction from files
│   ├── setup_gcp_infrastructure.sh  # GCP setup automation
│   └── test_gcp_connectivity.py     # Infrastructure testing
├── docs/               # Documentation
│   └── gcp-infrastructure-setup.md  # GCP setup guide
├── functions/          # Cloud Functions
│   ├── package.json           # Node.js dependencies
│   └── index.js              # Function implementations
├── public/             # Firebase Hosting files
│   └── index.html            # Web application
├── .gcp/              # GCP credentials (not in git)
│   └── headhunter-service-key.json  # Service account key
├── firebase.json      # Firebase configuration
├── .firebaserc        # Firebase project settings
├── firestore.rules    # Firestore security rules
├── firestore.indexes.json  # Database indexes
├── storage.rules      # Cloud Storage security rules
├── CSV files/          # Data directory
└── README.md           # This file
```

## Development Workflow

This project uses Task Master for task management:

```bash
# View next task
task-master next

# List all tasks
task-master list

# Mark task complete
task-master set-status --id=<task-id> --status=done
```

## Task Completion Protocol

For each completed task:
1. Run unit and integration tests
2. Update documentation
3. Commit changes with descriptive message
4. Push to remote repository
5. Move to next task

## Current Status

- ✅ Task #1: Ollama with Llama 3.1 8b setup complete
- ✅ Task #2: Create LLM prompts for resume analysis complete  
- ✅ Task #3: Create LLM prompts for recruiter comments complete
- ✅ Task #4: Implement Python LLM processor complete
- ✅ Task #5: Implement resume text extraction complete
- ✅ Task #6: Set up Google Cloud Platform infrastructure complete
- ⏳ Task #7: Implement quality validation system (next)

## Resume Analysis Usage

```python
from scripts.llm_prompts import ResumeAnalyzer

# Initialize analyzer
analyzer = ResumeAnalyzer()

# Analyze a resume
resume_text = "Your resume content here..."
analysis = analyzer.analyze_full_resume(resume_text)

# Access structured results
print(f"Career Level: {analysis.career_trajectory['current_level']}")
print(f"Years Experience: {analysis.years_experience}")
print(f"Has Leadership: {analysis.leadership_scope['has_leadership']}")
print(f"Top Skills: {analysis.technical_skills[:5]}")
```

## Recruiter Comment Analysis Usage

```python
from scripts.recruiter_prompts import RecruiterCommentAnalyzer

# Initialize analyzer
analyzer = RecruiterCommentAnalyzer()

# Analyze recruiter feedback
comments = "Recruiter notes and feedback here..."
insights = analyzer.analyze_full_feedback(comments, role_level="Senior Engineer")

# Access insights
print(f"Overall Sentiment: {insights.sentiment}")
print(f"Recommendation: {insights.recommendation}")
print(f"Key Strengths: {insights.strengths}")
print(f"Concerns: {insights.concerns}")
print(f"Cultural Fit: {insights.cultural_fit['cultural_alignment']}")
```

## Resume Text Extraction Usage

### Command Line Interface

Extract text from various resume formats:

```bash
# Extract from single file
python3 scripts/resume_extractor.py resume.pdf

# Extract from multiple files
python3 scripts/resume_extractor.py resume.pdf resume.docx resume.txt

# Extract and save to directory
python3 scripts/resume_extractor.py resume.pdf -o extracted_text/

# Supported formats: .pdf, .docx, .txt, .png, .jpg, .jpeg, .gif, .bmp, .tiff
```

### Python API

```python
from scripts.resume_extractor import ResumeTextExtractor

# Initialize extractor
extractor = ResumeTextExtractor()

# Extract from single file
result = extractor.extract_text_from_file('resume.pdf')
if result.success:
    print(f"Extracted {len(result.text)} characters")
    print(f"Method used: {result.metadata['method']}")
else:
    print(f"Failed: {result.error_message}")

# Extract from multiple files
results = extractor.extract_text_from_multiple_files([
    'resume1.pdf', 'resume2.docx', 'resume3.png'
])

# Get summary statistics
summary = extractor.get_extraction_summary(results)
print(f"Success rate: {summary['success_rate']:.1f}%")
```

## LLM Processing Pipeline Usage

The pipeline can now process resume files directly without pre-extracting text.

### CSV Format with File References

```csv
candidate_id,name,role_level,resume_file,recruiter_comments
1,John Doe,Senior,resumes/john_doe.pdf,"Great technical skills"
2,Jane Smith,Manager,resumes/jane_smith.docx,"Strong leadership potential"
3,Bob Wilson,Entry,resumes/bob_wilson.png,"New grad with promise"
```

### Command Line Interface

```bash
# Health check
python3 scripts/llm_processor.py --health-check

# Process CSV file
python3 scripts/llm_processor.py input_data.csv -o results.json

# Process with limits
python3 scripts/llm_processor.py input_data.csv --limit 10 -o results.json

# Use different model
python3 scripts/llm_processor.py input_data.csv -m llama3.1:8b -o results.json
```

### Python API

```python
from scripts.llm_processor import LLMProcessor

# Initialize processor
processor = LLMProcessor()

# Process single record
record = {
    'candidate_id': '001',
    'name': 'John Doe', 
    'resume_text': 'Resume content...',
    'recruiter_comments': 'Feedback...'
}
profile = processor.process_single_record(record)

# Process batch from CSV
profiles, stats = processor.process_batch('data.csv', output_file='results.json')
print(f"Processed {stats.successful}/{stats.total_records} records")
```

### Expected CSV Format

```csv
candidate_id,name,role_level,resume_text,recruiter_comments
1,John Doe,Senior,"Resume content here","Recruiter feedback here"
2,Jane Smith,Manager,"Resume content here","Recruiter feedback here"
```

## API Usage

Ollama provides a REST API at `http://localhost:11434`:

```bash
# Check API version
curl http://localhost:11434/api/version

# Generate completion
curl -X POST http://localhost:11434/api/generate -d '{
  "model": "llama3.1:8b",
  "prompt": "Analyze this resume..."
}'
```

## Performance

- Model load time: < 1 second (after initial load)
- Response generation: ~50-100 tokens/second
- Memory usage: ~5-6 GB when model is loaded

## License

[Your License Here]

## Contact

[Your Contact Information]