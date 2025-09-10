#!/usr/bin/env python3
"""
Fast merge of all candidate data into a single JSON file
No LLM processing - just combines CSVs, comments, and resume references
"""

import json
import csv
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import time

# Constants
BASE_DIR = Path("/Users/delimatsuo/Documents/Coding/headhunter")
CSV_DIR = BASE_DIR / "CSV files" / "505039_Ella_Executive_Search_CSVs_1"
RESUME_DIR = BASE_DIR / "CSV files" / "505039_Ella_Executive_Search_files_1"

# Output to NAS
NAS_DIR = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project")
OUTPUT_FILE = NAS_DIR / "merged_candidates.json"
STATS_FILE = NAS_DIR / "merge_statistics.json"

def merge_all_data():
    """Merge all candidate data from multiple sources"""
    print("=" * 80)
    print("HEADHUNTER DATA MERGE - Fast CSV/Comments/Resume Combination")
    print("=" * 80)
    
    start_time = time.time()
    
    # Step 1: Load candidates from CSV files
    print("\n📁 Step 1: Loading candidates from CSV files...")
    candidates = {}
    
    # Load from candidates file 2
    file2 = CSV_DIR / "Ella_Executive_Search_candidates_2-1.csv"
    if file2.exists():
        print(f"  Loading {file2.name}...")
        with open(file2, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row.get('id', '').strip()
                if cid:
                    candidates[cid] = {
                        'id': cid,
                        'name': row.get('name', ''),
                        'email': row.get('email', ''),
                        'phone': row.get('phone', ''),
                        'headline': row.get('headline', ''),
                        'address': row.get('address', ''),
                        'summary': row.get('summary', ''),
                        'education': row.get('education', ''),
                        'experience': row.get('experience', ''),
                        'skills': row.get('skills', ''),
                        'source': 'candidates_2',
                        'comments': [],
                        'resume_files': []
                    }
        print(f"  ✓ Loaded {len(candidates)} candidates from file 2")
    
    # Load/merge from candidates file 3
    file3 = CSV_DIR / "Ella_Executive_Search_candidates_3-1.csv"
    if file3.exists():
        print(f"  Loading {file3.name}...")
        added = 0
        updated = 0
        with open(file3, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row.get('id', '').strip()
                if cid:
                    if cid in candidates:
                        # Update existing - merge additional fields
                        if row.get('headline'):
                            candidates[cid]['headline'] = row.get('headline', '')
                        if row.get('summary'):
                            candidates[cid]['summary'] = row.get('summary', '')
                        if row.get('job'):
                            candidates[cid]['job'] = row.get('job', '')
                        candidates[cid].update({
                            'source': candidates[cid]['source'] + ',candidates_3'
                        })
                        updated += 1
                    else:
                        # Add new
                        candidates[cid] = {
                            'id': cid,
                            'name': row.get('name', ''),
                            'email': row.get('email', ''),
                            'phone': row.get('phone', ''),
                            'headline': row.get('headline', ''),
                            'summary': row.get('summary', ''),
                            'job': row.get('job', ''),
                            'skills': row.get('skills', ''),
                            'source': 'candidates_3',
                            'comments': [],
                            'resume_files': []
                        }
                        added += 1
        print(f"  ✓ Added {added} new, updated {updated} existing from file 3")
    
    print(f"\n📊 Total unique candidates: {len(candidates)}")
    
    # Step 2: Add comments
    print("\n💬 Step 2: Matching comments to candidates...")
    comment_files = [
        "Ella_Executive_Search_comments-1.csv",
        "Ella_Executive_Search_comments-3.csv", 
        "Ella_Executive_Search_comments-4.csv",
        "Ella_Executive_Search_comments-7.csv"
    ]
    
    total_comments = 0
    matched_comments = 0
    
    for comment_file in comment_files:
        file_path = CSV_DIR / comment_file
        if file_path.exists():
            print(f"  Processing {comment_file}...")
            file_matched = 0
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    total_comments += 1
                    cid = row.get('candidate_id', '').strip()
                    if cid in candidates:
                        comment = {
                            'date': row.get('Date', ''),
                            'author': row.get('Author', ''),
                            'text': row.get('Comment', ''),
                            'type': row.get('Type', ''),
                            'rating': row.get('Rating', '')
                        }
                        candidates[cid]['comments'].append(comment)
                        matched_comments += 1
                        file_matched += 1
            print(f"    ✓ Matched {file_matched} comments")
    
    print(f"\n📊 Comments: {matched_comments}/{total_comments} matched to candidates")
    
    # Step 3: Match resume files
    print("\n📄 Step 3: Matching resume files to candidates...")
    matched_resumes = 0
    
    if RESUME_DIR.exists():
        resume_files = list(RESUME_DIR.iterdir())
        print(f"  Found {len(resume_files)} files in resume directory")
        
        for resume_file in resume_files:
            if resume_file.is_file():
                filename = resume_file.name
                matched = False
                
                # Try to match by candidate ID in filename
                for cid in candidates:
                    if cid in filename:
                        candidates[cid]['resume_files'].append({
                            'filename': filename,
                            'path': str(resume_file),
                            'size_kb': round(resume_file.stat().st_size / 1024, 2)
                        })
                        matched_resumes += 1
                        matched = True
                        break
                
                # If not matched by ID, try by name (slower)
                if not matched:
                    filename_lower = filename.lower()
                    for cid, candidate in candidates.items():
                        name = candidate.get('name', '').lower()
                        if name and len(name) > 3 and name in filename_lower:
                            candidate['resume_files'].append({
                                'filename': filename,
                                'path': str(resume_file),
                                'size_kb': round(resume_file.stat().st_size / 1024, 2)
                            })
                            matched_resumes += 1
                            break
    
    print(f"  ✓ Matched {matched_resumes} resume files")
    
    # Step 4: Calculate statistics
    print("\n📈 Step 4: Calculating statistics...")
    stats = {
        'total_candidates': len(candidates),
        'candidates_with_email': sum(1 for c in candidates.values() if c.get('email')),
        'candidates_with_phone': sum(1 for c in candidates.values() if c.get('phone') or c.get('mobile')),
        'candidates_with_title': sum(1 for c in candidates.values() if c.get('title')),
        'candidates_with_company': sum(1 for c in candidates.values() if c.get('company')),
        'candidates_with_linkedin': sum(1 for c in candidates.values() if c.get('linkedin')),
        'candidates_with_comments': sum(1 for c in candidates.values() if c.get('comments')),
        'candidates_with_resumes': sum(1 for c in candidates.values() if c.get('resume_files')),
        'total_comments': sum(len(c.get('comments', [])) for c in candidates.values()),
        'total_resume_files': sum(len(c.get('resume_files', [])) for c in candidates.values()),
        'avg_comments_per_candidate': round(sum(len(c.get('comments', [])) for c in candidates.values()) / max(len(candidates), 1), 2),
        'merge_timestamp': datetime.now().isoformat(),
        'merge_duration_seconds': round(time.time() - start_time, 2)
    }
    
    # Step 5: Save merged data
    print("\n💾 Step 5: Saving merged data to NAS...")
    
    # Ensure NAS directory exists
    NAS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Convert to list for JSON serialization
    candidates_list = list(candidates.values())
    
    # Save main data file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(candidates_list, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Saved merged data to: {OUTPUT_FILE}")
    print(f"    File size: {round(OUTPUT_FILE.stat().st_size / (1024*1024), 2)} MB")
    
    # Save statistics
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    print(f"  ✓ Saved statistics to: {STATS_FILE}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("MERGE COMPLETE!")
    print("=" * 80)
    print(f"Total candidates: {stats['total_candidates']:,}")
    if stats['total_candidates'] > 0:
        print(f"With comments: {stats['candidates_with_comments']:,} ({stats['candidates_with_comments']*100//stats['total_candidates']}%)")
        print(f"With resumes: {stats['candidates_with_resumes']:,} ({stats['candidates_with_resumes']*100//stats['total_candidates']}%)")
    else:
        print("No candidates found - check CSV file column names")
    print(f"Total comments: {stats['total_comments']:,}")
    print(f"Total resume files: {stats['total_resume_files']:,}")
    print(f"Merge time: {stats['merge_duration_seconds']} seconds")
    print("\nOutput location (NAS):")
    print(f"  {OUTPUT_FILE}")
    print("\nView the data at: http://localhost:5555")
    print("=" * 80)

if __name__ == "__main__":
    merge_all_data()