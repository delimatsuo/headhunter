# AI Agent Handover Document - Headhunter Candidate Processing System

## Executive Summary
This document provides complete handover information for an AI agent to continue or maintain the Headhunter candidate processing system. The system uses local LLM (Ollama with Llama 3.1:8b) to analyze and enhance 29,138 candidate profiles for recruitment purposes.

## Current System Status

### Processing Progress
- **Total Candidates**: 29,138
- **Processed**: ~231 candidates (0.79%)
- **Remaining**: ~28,907 candidates
- **Estimated Time**: 300-400 hours of continuous processing

### Active Components
- **Chunked Processor**: Running/Ready (recommended processor)
- **Output Directory**: Contains 231+ enhanced JSON files
- **Database**: NAS-based JSON file (500MB+)

## Critical Context

### Problem Solved
The original processors were failing due to memory issues when loading the 500MB+ database file. The solution was to create `chunked_processor.py` which:
1. Processes candidates in 100-candidate chunks
2. Saves progress after each chunk
3. Can resume from interruptions
4. Updates the main database incrementally

### Data Quality Requirements
The user requires:
- **Complete data extraction** from resumes (education, experience, skills)
- **Comprehensive analysis** with searchable fields
- **No empty fields** - all analysis categories must be populated
- **Recruitment-focused insights** for candidate searching

## System Architecture

### File Structure
```
/Volumes/Extreme Pro/myprojects/headhunter/
├── scripts/
│   ├── chunked_processor.py         # MAIN - Use this for processing
│   ├── recruiter_enhanced_processor.py  # Quality testing (20 candidates)
│   ├── high_throughput_processor.py     # Fast but has memory issues
│   ├── candidate_viewer.py              # Web dashboard
│   ├── processor_progress.json          # Tracks processing state
│   └── README.md                         # User documentation
└── (NAS Drive via Synology)/
    └── Headhunter project/
        ├── comprehensive_merged_candidates.json  # Main database
        └── enhanced_analysis/                    # Output directory
            └── [candidate_id]_[name]_recruiter_enhanced.json
```

### Data Flow
1. **Input**: Read candidates from NAS database
2. **Processing**: Send to Ollama LLM for analysis
3. **Output**: Save individual JSON files + update main database
4. **Progress**: Track in processor_progress.json

## Continuation Instructions

### To Resume Processing

1. **Check current status**:
```bash
cd "/Volumes/Extreme Pro/myprojects/headhunter/scripts"
cat processor_progress.json  # See last processed index
ls -1 "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis"/*.json | wc -l
```

2. **Ensure Ollama is running**:
```bash
ollama list  # Check if llama3.1:8b is available
ollama serve  # Start if not running
```

3. **Start the chunked processor**:
```bash
python chunked_processor.py
# It will automatically resume from the last saved position
```

4. **Monitor progress** (optional):
```bash
# In another terminal
python candidate_viewer.py
# Open http://localhost:5000 in browser
```

### If Processing Stops

**Diagnosis Steps**:
1. Check if Python process is still running: `ps aux | grep chunked_processor`
2. Check Ollama status: `ollama list`
3. Check last output: `tail -f processor_progress.json`
4. Check disk space: `df -h`

**Recovery**:
```bash
# The chunked processor auto-recovers
python chunked_processor.py  # Will resume from last checkpoint
```

## Key Technical Details

### LLM Prompt Structure
The system sends comprehensive prompts containing:
- Candidate name
- Full education history
- Complete work experience
- Skills list
- Expects JSON response with 9 analysis categories

### Analysis Categories Required
1. **personal_details**: Name, location (inferred)
2. **education_analysis**: Degrees, institution quality
3. **experience_analysis**: Years, companies, progression
4. **technical_assessment**: Skills, depth, categories
5. **market_insights**: Salary range, demand, fit
6. **cultural_assessment**: Work preferences, flags
7. **recruiter_recommendations**: Placement difficulty, strategy
8. **searchability**: ATS keywords, search terms
9. **executive_summary**: Pitch, rating, strategy

### Performance Characteristics
- **Processing Rate**: 1-2 candidates/minute
- **Memory Usage**: 1-2GB
- **Timeout per candidate**: 120 seconds
- **Batch size**: 100 candidates
- **Save frequency**: Every batch

## Known Issues & Solutions

### Issue 1: Memory Problems
**Symptom**: Process hangs during database loading
**Solution**: Use chunked_processor.py (already implemented)

### Issue 2: Empty Fields in Output
**Symptom**: Analysis has empty arrays/strings
**Solution**: Use comprehensive prompts (fixed in current version)

### Issue 3: Ollama Timeouts
**Symptom**: Candidates fail with timeout
**Solution**: Processor retries 2 times automatically

## User Requirements Summary

1. **Process all 29,138 candidates** in the database
2. **Generate comprehensive, searchable profiles** for recruitment
3. **Extract ALL information** from resumes (not just names)
4. **Save individual JSON files** to NAS enhanced_analysis folder
5. **Update main database** with processing results
6. **Enable searching** by skills, experience, companies, etc.

## Maintenance Tasks

### Daily
- Check processing is still running
- Monitor output quality (spot check files)
- Verify disk space availability

### Weekly
- Backup processor_progress.json
- Review failed candidates
- Check processing rate

### If Completed
- Verify all 29,138 candidates processed
- Run quality checks on output
- Create search indices if needed

## Contact & Resources

### File Paths
- **Main Database**: `/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json`
- **Output Directory**: `/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis/`
- **Scripts**: `/Volumes/Extreme Pro/myprojects/headhunter/scripts/`

### Commands Reference
```bash
# Start processing
python chunked_processor.py

# View progress
python candidate_viewer.py

# Check file count
ls -1 [enhanced_analysis_path]/*.json | wc -l

# Check Ollama
ollama list
ollama serve

# Kill stuck process
ps aux | grep python
kill -9 [PID]
```

## Critical Success Factors

1. **Use chunked_processor.py** - It's the only stable solution for the large database
2. **Keep Ollama running** - The LLM service must be active
3. **Monitor processor_progress.json** - This tracks where to resume
4. **Don't modify the database during processing** - Can cause conflicts
5. **Check output quality periodically** - Ensure fields are populated

## Estimated Completion

At current rate (1-2 candidates/minute):
- **Remaining candidates**: ~28,900
- **Time needed**: 240-480 hours
- **If run continuously**: 10-20 days
- **Recommendation**: Run 24/7 with periodic checks

## Final Notes

The system is designed to be resilient and can recover from interruptions. The chunked approach solves the memory issue that plagued earlier versions. The comprehensive prompts ensure quality output with all required fields for recruitment searches.

**Priority**: Get the chunked_processor.py running continuously to complete the remaining 28,900+ candidates.

---
*Document prepared for AI agent handover on September 7, 2025*