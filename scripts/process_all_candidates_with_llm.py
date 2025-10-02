#!/usr/bin/env python3
"""
Process ALL candidates using existing LLM infrastructure
Uses Ollama with Llama 3.1:8b to process candidates in batches of 50
"""

import json
import csv
import os
import sys
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import time

# Import existing LLM processor
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from llm_processor import OllamaAPIClient, process_candidate_with_llm
from data_paths import csv_dir, repo_root, resumes_dir

# Constants
REPO_ROOT = repo_root()
CSV_DIR = csv_dir()
RESUME_DIR = resumes_dir()
CANDIDATE_FILE_CANDIDATES = [
    "CLEANED CANDIDATES - 1.csv",
    "Ella_Executive_Search_candidates_1-1.csv",
    "sample_candidates.csv",
]
# Use NAS for output storage
NAS_DIR = Path(os.getenv(
    "HEADHUNTER_NAS_DIR",
    "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project",
))
OUTPUT_DIR = Path(os.getenv("HEADHUNTER_OUTPUT_DIR", str(NAS_DIR / "processed_candidates")))
BATCH_SIZE = 50

def load_all_candidates() -> Dict[str, Dict]:
    """Load ALL candidates from CSV files without sampling"""
    print("Loading ALL candidates from CSV files...")
    candidates = {}
    
    # Load main candidate file
    candidates_file = None
    for file_name in CANDIDATE_FILE_CANDIDATES:
        candidate_path = CSV_DIR / file_name
        if candidate_path.exists():
            candidates_file = candidate_path
            break

    if candidates_file is None:
        csv_files = sorted(CSV_DIR.glob("*.csv"))
        if csv_files:
            candidates_file = csv_files[0]

    if candidates_file and candidates_file.exists():
        with open(candidates_file, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                candidate_id = row.get('ID', '').strip() or row.get('CandidateId', '').strip() or row.get('candidate_id', '').strip()
                if candidate_id:
                    candidates[candidate_id] = {
                        'id': candidate_id,
                        'name': row.get('Name', row.get('name', '')),
                        'title': row.get('Title', row.get('CurrentTitle', '')),
                        'company': row.get('Company', row.get('CurrentCompany', '')),
                        'email': row.get('Email', row.get('email', '')),
                        'phone': row.get('Phone', row.get('phone', '')),
                        'source_file': candidates_file.name,
                        'comments': [],
                        'resumes': []
                    }
    
    print(f"Loaded {len(candidates)} candidates from {candidates_file.name if candidates_file else 'CSV directory'}")
    
    # Load additional candidate data from file 3
    candidates_3_file = None
    for file_name in ["CLEANED CANDIDATES - 3.csv", "Ella_Executive_Search_candidates_3-1.csv"]:
        candidate_path = CSV_DIR / file_name
        if candidate_path.exists():
            candidates_3_file = candidate_path
            break

    if candidates_3_file and candidates_3_file.exists():
        with open(candidates_3_file, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            added = 0
            for row in reader:
                candidate_id = row.get('CandidateId', '').strip()
                if candidate_id and candidate_id not in candidates:
                    candidates[candidate_id] = {
                        'id': candidate_id,
                        'name': row.get('Name', ''),
                        'title': row.get('CurrentTitle', ''),
                        'company': row.get('CurrentCompany', ''),
                        'location': row.get('Location', ''),
                        'source_file': 'CLEANED CANDIDATES - 3.csv',
                        'comments': [],
                        'resumes': []
                    }
                    added += 1
        print(f"Added {added} additional candidates from file 3")
    
    print(f"Total candidates loaded: {len(candidates)}")
    return candidates

def load_all_comments(candidates: Dict[str, Dict]) -> None:
    """Load ALL comments and match to candidates"""
    print("Loading ALL comments...")
    comments_file = CSV_DIR / "CLEANED CANDIDATES - 2.csv"
    
    if not comments_file.exists():
        print("Comments file not found")
        return
    
    matched_comments = 0
    unmatched_comments = 0
    
    with open(comments_file, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            candidate_id = row.get('CandidateId', '').strip()
            if candidate_id in candidates:
                comment = {
                    'date': row.get('Date', ''),
                    'author': row.get('Author', ''),
                    'comment': row.get('Comment', ''),
                    'type': row.get('Type', '')
                }
                candidates[candidate_id]['comments'].append(comment)
                matched_comments += 1
            else:
                unmatched_comments += 1
    
    print(f"Matched {matched_comments} comments to candidates")
    print(f"Unmatched comments: {unmatched_comments}")

def load_all_resumes(candidates: Dict[str, Dict]) -> None:
    """Load ALL resume files and match to candidates"""
    print("Loading ALL resume files...")
    
    if not RESUME_DIR.exists():
        print("Resume directory not found")
        return
    
    matched_resumes = 0
    unmatched_resumes = 0
    
    for resume_file in RESUME_DIR.iterdir():
        if resume_file.is_file() and resume_file.suffix.lower() in ['.txt', '.pdf', '.doc', '.docx']:
            # Extract candidate ID from filename
            filename = resume_file.stem
            # Try to match by ID or name patterns
            matched = False
            
            for candidate_id, candidate in candidates.items():
                # Try matching by ID in filename
                if candidate_id in filename:
                    candidate['resumes'].append({
                        'filename': resume_file.name,
                        'path': str(resume_file),
                        'size': resume_file.stat().st_size
                    })
                    matched_resumes += 1
                    matched = True
                    break
                
                # Try matching by name
                if candidate['name'] and candidate['name'].lower() in filename.lower():
                    candidate['resumes'].append({
                        'filename': resume_file.name,
                        'path': str(resume_file),
                        'size': resume_file.stat().st_size
                    })
                    matched_resumes += 1
                    matched = True
                    break
            
            if not matched:
                unmatched_resumes += 1
    
    print(f"Matched {matched_resumes} resume files to candidates")
    print(f"Unmatched resumes: {unmatched_resumes}")

def process_batch_with_llm(batch: List[Dict], batch_num: int, ollama_client: OllamaAPIClient) -> List[Dict]:
    """Process a batch of candidates using the LLM"""
    print(f"\nProcessing batch {batch_num} with {len(batch)} candidates...")
    processed = []
    
    for i, candidate in enumerate(batch, 1):
        try:
            print(f"  Processing candidate {i}/{len(batch)}: {candidate.get('name', 'Unknown')}")
            
            # Prepare candidate data for LLM processing
            candidate_data = {
                'id': candidate['id'],
                'name': candidate.get('name', ''),
                'title': candidate.get('title', ''),
                'company': candidate.get('company', ''),
                'email': candidate.get('email', ''),
                'phone': candidate.get('phone', ''),
                'location': candidate.get('location', ''),
                'comments': candidate.get('comments', []),
                'resume_text': ''
            }
            
            # Read resume text if available
            if candidate.get('resumes'):
                resume_path = candidate['resumes'][0]['path']
                try:
                    with open(resume_path, 'r', encoding='utf-8', errors='ignore') as f:
                        candidate_data['resume_text'] = f.read()[:10000]  # Limit to 10K chars
                except Exception as e:
                    print(f"    Error reading resume: {e}")
            
            # Process with LLM
            llm_result = process_candidate_with_llm(candidate_data, ollama_client)
            
            # Combine original data with LLM analysis
            processed_candidate = {
                **candidate,
                'llm_analysis': llm_result,
                'processed_at': datetime.now().isoformat()
            }
            
            processed.append(processed_candidate)
            
            # Small delay to avoid overwhelming the LLM
            time.sleep(0.5)
            
        except Exception as e:
            print(f"    Error processing candidate {candidate['id']}: {e}")
            # Still include the candidate with error flag
            processed.append({
                **candidate,
                'llm_analysis': {'error': str(e)},
                'processed_at': datetime.now().isoformat()
            })
    
    return processed

def save_batch(batch_data: List[Dict], batch_num: int) -> None:
    """Save processed batch to file"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"batch_{batch_num:04d}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(batch_data, f, indent=2, ensure_ascii=False)
    
    print(f"  Saved batch {batch_num} to {output_file}")

def main():
    """Main processing function"""
    print("=" * 80)
    print("HEADHUNTER: Processing ALL Candidates with Local LLM")
    print("=" * 80)
    
    # Step 1: Load ALL candidates
    candidates = load_all_candidates()
    
    # Step 2: Match ALL comments
    load_all_comments(candidates)
    
    # Step 3: Match ALL resumes
    load_all_resumes(candidates)
    
    # Step 4: Initialize LLM client
    print("\nInitializing Ollama LLM client...")
    ollama_client = OllamaAPIClient(model="llama3.1:8b")
    
    # Verify Ollama is running
    if not ollama_client.verify_connection():
        print("ERROR: Ollama is not running or llama3.1:8b model is not available")
        print("Please ensure Ollama is running: ollama serve")
        print("And the model is pulled: ollama pull llama3.1:8b")
        return
    
    print("✓ Ollama connection verified")
    
    # Step 5: Process in batches
    candidate_list = list(candidates.values())
    total_candidates = len(candidate_list)
    num_batches = (total_candidates + BATCH_SIZE - 1) // BATCH_SIZE
    
    print(f"\nProcessing {total_candidates} candidates in {num_batches} batches of {BATCH_SIZE}")
    print("=" * 80)
    
    all_processed = []
    
    for batch_num in range(num_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, total_candidates)
        batch = candidate_list[start_idx:end_idx]
        
        # Process batch with LLM
        processed_batch = process_batch_with_llm(batch, batch_num + 1, ollama_client)
        all_processed.extend(processed_batch)
        
        # Save batch to file
        save_batch(processed_batch, batch_num + 1)
        
        # Progress update
        print(f"  Progress: {end_idx}/{total_candidates} candidates processed")
        
        # Optional: Take a break between batches to avoid overwhelming the system
        if batch_num < num_batches - 1:
            print("  Pausing between batches...")
            time.sleep(2)
    
    # Step 6: Save master file with all processed candidates
    print("\nSaving master file with all processed candidates...")
    master_file = OUTPUT_DIR / "all_candidates_processed.json"
    with open(master_file, 'w', encoding='utf-8') as f:
        json.dump(all_processed, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Saved {len(all_processed)} processed candidates to {master_file}")
    
    # Summary statistics
    print("\n" + "=" * 80)
    print("PROCESSING COMPLETE")
    print("=" * 80)
    print(f"Total candidates processed: {len(all_processed)}")
    print(f"Candidates with comments: {sum(1 for c in all_processed if c.get('comments'))}")
    print(f"Candidates with resumes: {sum(1 for c in all_processed if c.get('resumes'))}")
    print(f"Candidates with LLM analysis: {sum(1 for c in all_processed if c.get('llm_analysis') and 'error' not in c['llm_analysis'])}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 80)

if __name__ == "__main__":
    main()
