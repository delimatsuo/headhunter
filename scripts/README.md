# Headhunter Candidate Processing Scripts

## Overview
This directory contains Python scripts for processing and enhancing candidate data with AI-powered recruitment analysis using local LLM (Ollama with Llama 3.1:8b).

## Prerequisites

### Required Software
- Python 3.8+
- Ollama installed and running locally
- Llama 3.1:8b model downloaded

### Installation
```bash
# Install Ollama (Mac)
brew install ollama

# Start Ollama service
ollama serve

# Pull the Llama 3.1:8b model
ollama pull llama3.1:8b

# Install Python dependencies
pip install psutil flask
```

## Available Scripts

### 1. `chunked_processor.py` (RECOMMENDED)
**Purpose**: Processes candidates in manageable chunks to avoid memory issues with large databases.

**Features**:
- Processes 100 candidates at a time
- Saves progress automatically (can resume if interrupted)
- Efficient memory usage
- Comprehensive error handling

**Usage**:
```bash
python chunked_processor.py
```

**Resume after interruption**:
```bash
# The script automatically resumes from where it left off
python chunked_processor.py
```

### 2. `recruiter_enhanced_processor.py`
**Purpose**: Processes a small batch (20 candidates) for quality review.

**Features**:
- Detailed analysis with comprehensive prompts
- Best for testing and quality assurance
- Rich data extraction

**Usage**:
```bash
python recruiter_enhanced_processor.py
```

### 3. `high_throughput_processor.py`
**Purpose**: High-performance parallel processing with multiple workers.

**Features**:
- 6 parallel workers
- Batch processing (100 candidates per batch)
- Optimized for speed with quality

**Usage**:
```bash
python high_throughput_processor.py
```

**Note**: May experience memory issues with very large databases.

### 4. `candidate_viewer.py`
**Purpose**: Web-based dashboard to view processing progress and candidate data.

**Features**:
- Real-time progress monitoring
- Search and filter capabilities
- REST API endpoints

**Usage**:
```bash
python candidate_viewer.py
# Open browser to http://localhost:5000
```

## Data Locations

### Input Database
```
/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json
```

### Output Directory
```
/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis/
```

### Progress Tracking
```
./processor_progress.json  # Created by chunked_processor.py
```

## Processing Workflow

### For Full Database Processing (29,138 candidates)

1. **Start the chunked processor**:
```bash
cd "/Volumes/Extreme Pro/myprojects/headhunter/scripts"
python chunked_processor.py
```

2. **Monitor progress** (in another terminal):
```bash
python candidate_viewer.py
# Open http://localhost:5000
```

3. **Check processing status**:
```bash
# Count processed files
ls -1 "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis"/*.json | wc -l
```

### For Quality Testing (20 candidates)

```bash
python recruiter_enhanced_processor.py
```

## Output Format

Each processed candidate generates a JSON file with:

```json
{
  "candidate_id": "123456",
  "name": "John Doe",
  "recruiter_analysis": {
    "personal_details": {},
    "education_analysis": {},
    "experience_analysis": {},
    "technical_assessment": {},
    "market_insights": {},
    "cultural_assessment": {},
    "recruiter_recommendations": {},
    "searchability": {},
    "executive_summary": {}
  },
  "timestamp": "2025-09-07T12:00:00"
}
```

## Troubleshooting

### Processor Stops/Hangs
- Use `chunked_processor.py` instead of other processors
- Check if Ollama is running: `ollama list`
- Monitor system resources: `top` or Activity Monitor

### Memory Issues
- The chunked processor handles this automatically
- Reduce batch_size in script if needed (default: 100)

### Resume After Interruption
```bash
# Chunked processor auto-resumes
python chunked_processor.py

# Check last processed index
cat processor_progress.json
```

### View Logs
```bash
# Check running processes
ps aux | grep python

# Kill stuck process
kill -9 <PID>
```

## Performance Metrics

- **Processing Speed**: ~1-2 candidates per minute (with quality analysis)
- **Memory Usage**: ~1-2GB per processor
- **Disk Space**: ~5-10KB per candidate file
- **Total Time Estimate**: ~300-400 hours for full database

## Best Practices

1. **Use chunked_processor.py** for production processing
2. **Monitor with candidate_viewer.py** to track progress
3. **Run overnight/continuously** for large datasets
4. **Backup progress regularly** (auto-saved in processor_progress.json)
5. **Check output quality** periodically by reviewing generated files

## Support Files

- `processor_progress.json`: Tracks processing progress
- `comprehensive_merged_candidates_backup_*.json`: Auto-created backups

## Notes

- The system processes candidates with education or experience data
- Candidates without IDs or names are skipped
- Each candidate takes 30-60 seconds to process with LLM analysis
- Files are saved individually and database is updated in batches