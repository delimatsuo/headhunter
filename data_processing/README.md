# Headhunter Data Processing

This directory contains tools to process and prepare your Workable ATS export data for LLM analysis.

## 📊 Data Overview

Your export contains:
- **29,135 candidates** with comprehensive profiles
- **70,442 recruiter comments** with qualitative insights
- **67,606 resume files** (PDF, PNG, DOCX formats)
- Multiple CSV files with structured data

## 🚀 Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Process full dataset:**
   ```bash
   python data_processor.py
   ```

3. **Process sample (faster for testing):**
   ```python
   # Edit data_processor.py line 165 to change limit
   processor.process_and_save(limit=1000)  # Remove limit for full processing
   ```

## 📁 Output Files

- `output/enriched_candidates.jsonl` - Main processed data (JSON Lines format)
- `output/processing_stats.json` - Summary statistics

## 🔍 Data Structure

Each enriched candidate profile contains:

```json
{
  "candidate_id": "string",
  "name": "string",
  "email": "string",
  "headline": "string",
  "summary": "string",
  "education": [{"raw": "string"}],
  "experience": [{"raw": "string"}],
  "skills": "string",
  "social_profiles": [{"type": "linkedin", "url": "string"}],
  "recruiter_notes": ["detailed recruiter insights"],
  "stage": "Sourced|Reached Out|Interview",
  "source": "linkedin|unknown",
  "resume_path": "path/to/resume/file"
}
```

## 🎯 Best Practices for LLM Analysis

### 1. **Chunking Strategy**
- **Education + Experience**: Combine for career trajectory analysis
- **Recruiter Notes**: Process separately for qualitative insights
- **Resume Text**: Extract and chunk by sections

### 2. **Prompt Engineering**
```python
# For career analysis
prompt = f"""
Analyze this candidate's career trajectory:
Education: {profile['education']}
Experience: {profile['experience']}
Recruiter Notes: {profile['recruiter_notes']}

Extract:
- Career velocity (High/Moderate/Slow)
- Key transitions and patterns
- Leadership scope and team size
"""

# For role matching
prompt = f"""
Match candidate to job description:
JD: {job_description}
Candidate Profile: {json.dumps(profile)}
"""
```

### 3. **Data Quality Improvements**

**Current Issues:**
- Education/Experience stored as raw strings (need parsing)
- Resume paths not fully resolved
- Some fields have null values

**Enhancements to Consider:**
- Parse education/experience into structured JSON
- Extract resume text using OCR/PDF parsing
- Add data validation and cleaning
- Implement text embeddings for semantic search

## 🔧 Advanced Processing Options

### Resume Text Extraction
```python
# Add to data_processor.py
import PyPDF2
import pytesseract
from PIL import Image

def extract_resume_text(self, file_path: str) -> str:
    if file_path.endswith('.pdf'):
        with open(file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            return text
    elif file_path.endswith(('.png', '.jpg', '.jpeg')):
        image = Image.open(file_path)
        return pytesseract.image_to_string(image)
    return ""
```

### Structured Experience Parsing
```python
def parse_experience(self, exp_string: str) -> List[Dict]:
    # Use LLM or regex to parse into:
    # [{"company": "", "title": "", "dates": "", "description": ""}]
    pass
```

## 📈 Processing Statistics

From sample of 1,000 candidates:
- **Candidates with comments**: 501 (50.1%)
- **Resume files found**: 0 (need path resolution fix)
- **Most common stages**: Reached Out (47%), Sourced (37%)
- **Top sources**: LinkedIn, Hiring.cafe

## 🚀 Next Steps

1. **Fix Resume Paths**: Update `find_resume_path()` method for correct file resolution
2. **Add Text Extraction**: Implement resume OCR/PDF parsing
3. **Enhance Parsing**: Structure education/experience data
4. **Quality Validation**: Add data cleaning and validation
5. **LLM Integration**: Connect to Ollama for analysis pipeline

## 💡 Pro Tips

- Use JSON Lines format for memory-efficient streaming
- Process in batches to manage memory with large datasets
- Cache processed results to avoid re-processing
- Validate data quality before LLM analysis
- Consider using embeddings for semantic candidate search
