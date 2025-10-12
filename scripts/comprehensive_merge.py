#!/usr/bin/env python3
"""
Comprehensive merge that captures ALL candidates from all sources
Including orphaned candidates only found in comments
"""

import json
import csv
from pathlib import Path
from typing import Dict, Set
from datetime import datetime
import time
import os

from data_paths import csv_dir, repo_root, resumes_dir

# Constants
REPO_ROOT = repo_root()
CSV_DIR = csv_dir()
RESUME_DIR = resumes_dir()

# Output to local data directory
OUTPUT_DIR = Path(os.getenv(
    "OUTPUT_DIRECTORY",
    str(REPO_ROOT / "data"),
))
OUTPUT_FILE = OUTPUT_DIR / "comprehensive_merged_candidates.json"
STATS_FILE = OUTPUT_DIR / "comprehensive_merge_statistics.json"
MISSING_IDS_FILE = OUTPUT_DIR / "missing_candidate_ids.json"

def find_all_candidate_ids():
    """Find ALL unique candidate IDs from every source"""
    print("\n🔍 Step 1: Finding ALL unique candidate IDs from every source...")
    
    all_ids = set()
    id_sources = {}  # Track where each ID comes from
    
    # 1. Check candidates_1 file (RESTORED)
    file1 = CSV_DIR / "Ella_Executive_Search_candidates_1-1.csv"
    if file1.exists():
        print(f"  Scanning {file1.name}...")
        file1_ids = set()
        with open(file1, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row.get('id', '').strip()
                if cid:
                    file1_ids.add(cid)
                    all_ids.add(cid)
                    if cid not in id_sources:
                        id_sources[cid] = []
                    id_sources[cid].append('candidates_1')
        print(f"    Found {len(file1_ids)} IDs in candidates_1")
    
    # 2. Check candidates_2 file
    file2 = CSV_DIR / "Ella_Executive_Search_candidates_2-1.csv"
    if file2.exists():
        print(f"  Scanning {file2.name}...")
        file2_ids = set()
        with open(file2, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row.get('id', '').strip()
                if cid:
                    file2_ids.add(cid)
                    all_ids.add(cid)
                    if cid not in id_sources:
                        id_sources[cid] = []
                    id_sources[cid].append('candidates_2')
        print(f"    Found {len(file2_ids)} IDs in candidates_2")
    
    # 2. Check candidates_3 file
    file3 = CSV_DIR / "Ella_Executive_Search_candidates_3-1.csv"
    if file3.exists():
        print(f"  Scanning {file3.name}...")
        file3_ids = set()
        with open(file3, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row.get('id', '').strip()
                if cid:
                    file3_ids.add(cid)
                    all_ids.add(cid)
                    if cid not in id_sources:
                        id_sources[cid] = []
                    id_sources[cid].append('candidates_3')
        print(f"    Found {len(file3_ids)} IDs in candidates_3")
    
    # 3. Check talent_pool file
    talent_file = CSV_DIR / "Ella_Executive_Search_talent_pool_candidates_1-1.csv"
    if talent_file.exists():
        print(f"  Scanning {talent_file.name}...")
        talent_ids = set()
        with open(talent_file, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row.get('id', '').strip()
                if cid:
                    talent_ids.add(cid)
                    all_ids.add(cid)
                    if cid not in id_sources:
                        id_sources[cid] = []
                    id_sources[cid].append('talent_pool')
        print(f"    Found {len(talent_ids)} IDs in talent_pool")
    
    # 4. Check ALL comment files for candidate IDs
    comment_files = [
        "Ella_Executive_Search_comments-1.csv",
        "Ella_Executive_Search_comments-2.csv",
        "Ella_Executive_Search_comments-3.csv",
        "Ella_Executive_Search_comments-4.csv", 
        "Ella_Executive_Search_comments-5.csv",
        "Ella_Executive_Search_comments-6.csv",
        "Ella_Executive_Search_comments-7.csv",
        "Ella_Executive_Search_comments-8.csv"
    ]
    
    comment_only_ids = set()
    for comment_file in comment_files:
        file_path = CSV_DIR / comment_file
        if file_path.exists():
            print(f"  Scanning {comment_file}...")
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cid = row.get('candidate_id', '').strip()
                    if cid:
                        if cid not in all_ids:
                            comment_only_ids.add(cid)
                        all_ids.add(cid)
                        if cid not in id_sources:
                            id_sources[cid] = []
                        if 'comments' not in id_sources[cid]:
                            id_sources[cid].append('comments')
    
    print(f"    Found {len(comment_only_ids)} IDs ONLY in comments (orphaned)")
    
    # 5. Check job_candidates files
    job_files = [
        "Ella_Executive_Search_job_candidates-1.csv",
        "Ella_Executive_Search_job_candidates_4-1.csv"
    ]
    
    job_only_ids = set()
    for job_file in job_files:
        file_path = CSV_DIR / job_file
        if file_path.exists():
            print(f"  Scanning {job_file}...")
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cid = row.get('candidate_id', '').strip()
                    if not cid:
                        cid = row.get('id', '').strip()
                    if cid:
                        if cid not in all_ids:
                            job_only_ids.add(cid)
                        all_ids.add(cid)
                        if cid not in id_sources:
                            id_sources[cid] = []
                        if 'job_candidates' not in id_sources[cid]:
                            id_sources[cid].append('job_candidates')
    
    print(f"    Found {len(job_only_ids)} additional IDs in job_candidates")
    
    print(f"\n📊 Total unique candidate IDs found: {len(all_ids)}")
    print(f"  - In candidate files: {len(all_ids - comment_only_ids - job_only_ids)}")
    print(f"  - Only in comments: {len(comment_only_ids)}")
    print(f"  - Only in job files: {len(job_only_ids)}")
    
    return all_ids, id_sources, comment_only_ids

def load_all_candidate_data(all_ids: Set[str], id_sources: Dict):
    """Load all candidate data, creating skeleton records for orphaned IDs"""
    print("\n📁 Step 2: Loading candidate data for ALL IDs...")
    
    candidates = {}
    
    # Initialize all candidates with skeleton data
    for cid in all_ids:
        candidates[cid] = {
            'id': cid,
            'name': '',
            'email': '',
            'phone': '',
            'headline': '',
            'address': '',
            'summary': '',
            'education': '',
            'experience': '',
            'skills': '',
            'source': ','.join(id_sources.get(cid, [])),
            'data_status': 'orphaned' if 'comments' in id_sources.get(cid, []) and len(id_sources.get(cid, [])) == 1 else 'normal',
            'comments': [],
            'resume_files': []
        }
    
    # Load actual data from candidates_1 (RESTORED)
    file1 = CSV_DIR / "Ella_Executive_Search_candidates_1-1.csv"
    if file1.exists():
        print(f"  Loading data from {file1.name}...")
        updated = 0
        with open(file1, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row.get('id', '').strip()
                if cid and cid in candidates:
                    candidates[cid].update({
                        'name': row.get('name', ''),
                        'email': row.get('email', ''),
                        'phone': row.get('phone', ''),
                        'headline': row.get('headline', ''),
                        'address': row.get('address', ''),
                        'summary': row.get('summary', ''),
                        'education': row.get('education', ''),
                        'experience': row.get('experience', ''),
                        'skills': row.get('skills', ''),
                        'data_status': 'normal'
                    })
                    updated += 1
        print(f"    Updated {updated} candidates from candidates_1")
    
    # Load actual data from candidates_2
    file2 = CSV_DIR / "Ella_Executive_Search_candidates_2-1.csv"
    if file2.exists():
        print(f"  Loading data from {file2.name}...")
        updated = 0
        with open(file2, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row.get('id', '').strip()
                if cid and cid in candidates:
                    candidates[cid].update({
                        'name': row.get('name', ''),
                        'email': row.get('email', ''),
                        'phone': row.get('phone', ''),
                        'headline': row.get('headline', ''),
                        'address': row.get('address', ''),
                        'summary': row.get('summary', ''),
                        'education': row.get('education', ''),
                        'experience': row.get('experience', ''),
                        'skills': row.get('skills', ''),
                        'data_status': 'normal'
                    })
                    updated += 1
        print(f"    Updated {updated} candidates with data")
    
    # Load/merge from candidates_3
    file3 = CSV_DIR / "Ella_Executive_Search_candidates_3-1.csv"
    if file3.exists():
        print(f"  Loading data from {file3.name}...")
        updated = 0
        with open(file3, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row.get('id', '').strip()
                if cid and cid in candidates:
                    # Update with any non-empty fields
                    if row.get('name'):
                        candidates[cid]['name'] = row.get('name', '')
                    if row.get('headline'):
                        candidates[cid]['headline'] = row.get('headline', '')
                    if row.get('summary'):
                        candidates[cid]['summary'] = row.get('summary', '')
                    if row.get('job'):
                        candidates[cid]['job'] = row.get('job', '')
                    if row.get('skills'):
                        candidates[cid]['skills'] = row.get('skills', '')
                    candidates[cid]['data_status'] = 'normal'
                    updated += 1
        print(f"    Updated {updated} candidates with additional data")
    
    # Load from talent_pool
    talent_file = CSV_DIR / "Ella_Executive_Search_talent_pool_candidates_1-1.csv"
    if talent_file.exists():
        print(f"  Loading data from {talent_file.name}...")
        updated = 0
        with open(talent_file, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row.get('id', '').strip()
                if cid and cid in candidates:
                    # Talent pool might have different fields
                    for key, value in row.items():
                        if value and key != 'id':
                            candidates[cid][key] = value
                    candidates[cid]['data_status'] = 'normal'
                    updated += 1
        print(f"    Updated {updated} candidates from talent pool")
    
    return candidates

def load_all_comments(candidates: Dict):
    """Load ALL comments and match to candidates"""
    print("\n💬 Step 3: Loading ALL comments...")
    
    comment_files = [
        "Ella_Executive_Search_comments-1.csv",
        "Ella_Executive_Search_comments-2.csv",
        "Ella_Executive_Search_comments-3.csv",
        "Ella_Executive_Search_comments-4.csv", 
        "Ella_Executive_Search_comments-5.csv",
        "Ella_Executive_Search_comments-6.csv",
        "Ella_Executive_Search_comments-7.csv",
        "Ella_Executive_Search_comments-8.csv"
    ]
    
    total_comments = 0
    matched_comments = 0
    orphaned_comments = 0
    
    for comment_file in comment_files:
        file_path = CSV_DIR / comment_file
        if file_path.exists():
            print(f"  Processing {comment_file}...")
            file_matched = 0
            file_orphaned = 0
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    total_comments += 1
                    cid = row.get('candidate_id', '').strip()
                    
                    comment = {
                        'date': row.get('created_at', ''),
                        'author': row.get('member_id', ''),  # No author field, use member_id
                        'text': row.get('body', ''),
                        'type': row.get('attachment_name', ''),  # Use attachment_name as type
                        'rating': row.get('rating_id', '')
                    }
                    
                    if cid in candidates:
                        candidates[cid]['comments'].append(comment)
                        matched_comments += 1
                        file_matched += 1
                        
                        # Update orphaned candidates with comment author names
                        if candidates[cid]['data_status'] == 'orphaned' and not candidates[cid]['name']:
                            # Try to extract name from member_id if it looks like a candidate name
                            member_id = row.get('member_id', '')
                            if member_id and not any(word in member_id.lower() for word in ['admin', 'system', 'bot']):
                                candidates[cid]['inferred_name'] = f"[From comments: {member_id}]"
                    else:
                        # This shouldn't happen now since we captured all IDs
                        orphaned_comments += 1
                        file_orphaned += 1
                        print(f"    WARNING: Comment for unknown candidate {cid}")
                        
            print(f"    ✓ Matched {file_matched} comments, {file_orphaned} orphaned")
    
    print(f"\n📊 Comments: {matched_comments}/{total_comments} matched")
    if orphaned_comments > 0:
        print(f"  ⚠️  {orphaned_comments} comments for unknown candidates")
    
    return total_comments, matched_comments

def match_resume_files(candidates: Dict):
    """Match resume files to candidates"""
    print("\n📄 Step 4: Matching resume files...")
    
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
    return matched_resumes

def analyze_missing_candidates(total_found: int, target_count: int = 29176):
    """Analyze why we might be missing candidates"""
    print("\n🔍 Step 5: Analyzing missing candidates...")
    print(f"  Target count: {target_count:,}")
    print(f"  Found count: {total_found:,}")
    print(f"  Difference: {target_count - total_found:,}")
    
    # Check all CSV files for any additional data
    print("\n  Scanning ALL CSV files for any additional candidate references...")
    
    all_csv_files = list(CSV_DIR.glob("*.csv"))
    print(f"  Found {len(all_csv_files)} CSV files to scan")
    
    additional_ids = set()
    for csv_file in all_csv_files:
        if csv_file.name not in ['Ella_Executive_Search_candidates_1-1.csv',
                                  'Ella_Executive_Search_candidates_2-1.csv', 
                                  'Ella_Executive_Search_candidates_3-1.csv',
                                  'Ella_Executive_Search_talent_pool_candidates_1-1.csv']:
            # Check for any ID-like columns
            try:
                with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                    reader = csv.DictReader(f)
                    first_row = next(reader, None)
                    if first_row:
                        # Look for ID columns
                        id_columns = [col for col in first_row.keys() if 'id' in col.lower()]
                        if id_columns:
                            f.seek(0)
                            reader = csv.DictReader(f)
                            for row in reader:
                                for col in id_columns:
                                    val = row.get(col, '').strip()
                                    if val and val.isdigit() and len(val) >= 5:
                                        additional_ids.add(val)
            except Exception as e:
                print(f"    Error reading {csv_file.name}: {e}")
    
    print(f"  Found {len(additional_ids)} potential candidate IDs in other files")
    
    return additional_ids

def comprehensive_merge():
    """Perform comprehensive merge capturing ALL candidates"""
    print("=" * 80)
    print("COMPREHENSIVE CANDIDATE DATA MERGE")
    print("=" * 80)
    
    start_time = time.time()
    
    # Step 1: Find ALL unique candidate IDs
    all_ids, id_sources, orphaned_ids = find_all_candidate_ids()
    
    # Step 2: Load all candidate data
    candidates = load_all_candidate_data(all_ids, id_sources)
    
    # Step 3: Load and match comments
    total_comments, matched_comments = load_all_comments(candidates)
    
    # Step 4: Match resume files
    matched_resumes = match_resume_files(candidates)
    
    # Step 5: Analyze missing candidates
    additional_ids = analyze_missing_candidates(len(candidates))
    
    # Step 6: Calculate statistics
    print("\n📈 Step 6: Calculating statistics...")
    
    normal_candidates = sum(1 for c in candidates.values() if c['data_status'] == 'normal')
    orphaned_candidates = sum(1 for c in candidates.values() if c['data_status'] == 'orphaned')
    
    stats = {
        'total_candidates': len(candidates),
        'normal_candidates': normal_candidates,
        'orphaned_candidates': orphaned_candidates,
        'candidates_with_name': sum(1 for c in candidates.values() if c.get('name')),
        'candidates_with_email': sum(1 for c in candidates.values() if c.get('email')),
        'candidates_with_phone': sum(1 for c in candidates.values() if c.get('phone')),
        'candidates_with_headline': sum(1 for c in candidates.values() if c.get('headline')),
        'candidates_with_summary': sum(1 for c in candidates.values() if c.get('summary')),
        'candidates_with_comments': sum(1 for c in candidates.values() if c.get('comments')),
        'candidates_with_resumes': sum(1 for c in candidates.values() if c.get('resume_files')),
        'total_comments': total_comments,
        'matched_comments': matched_comments,
        'total_resume_files': matched_resumes,
        'avg_comments_per_candidate': round(total_comments / max(len(candidates), 1), 2),
        'target_count': 29176,
        'missing_count': 29176 - len(candidates),
        'additional_ids_found_but_not_loaded': len(additional_ids),
        'merge_timestamp': datetime.now().isoformat(),
        'merge_duration_seconds': round(time.time() - start_time, 2)
    }
    
    # Step 7: Save comprehensive data
    print("\n💾 Step 7: Saving comprehensive merged data...")

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
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
    
    # Save list of orphaned candidate IDs for investigation
    if orphaned_ids:
        with open(MISSING_IDS_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'orphaned_candidate_ids': sorted(list(orphaned_ids)),
                'count': len(orphaned_ids),
                'description': 'Candidate IDs found only in comments, not in candidate files'
            }, f, indent=2)
        print(f"  ✓ Saved orphaned IDs to: {MISSING_IDS_FILE}")
    
    # Print final summary
    print("\n" + "=" * 80)
    print("COMPREHENSIVE MERGE COMPLETE!")
    print("=" * 80)
    print(f"Total candidates found: {stats['total_candidates']:,}")
    print(f"  - Normal candidates: {normal_candidates:,}")
    print(f"  - Orphaned (comments only): {orphaned_candidates:,}")
    print(f"Target count: {stats['target_count']:,}")
    print(f"Still missing: {stats['missing_count']:,}")
    
    if stats['total_candidates'] > 0:
        print("\nData completeness:")
        print(f"  With name: {stats['candidates_with_name']:,} ({stats['candidates_with_name']*100//stats['total_candidates']}%)")
        print(f"  With email: {stats['candidates_with_email']:,} ({stats['candidates_with_email']*100//stats['total_candidates']}%)")
        print(f"  With comments: {stats['candidates_with_comments']:,} ({stats['candidates_with_comments']*100//stats['total_candidates']}%)")
        print(f"  With resumes: {stats['candidates_with_resumes']:,} ({stats['candidates_with_resumes']*100//stats['total_candidates']}%)")
    
    print(f"\nTotal comments: {stats['total_comments']:,}")
    print(f"Total resume files: {stats['total_resume_files']:,}")
    print(f"Merge time: {stats['merge_duration_seconds']} seconds")
    
    print("\n📁 Output files saved to NAS:")
    print(f"  Data: {OUTPUT_FILE}")
    print(f"  Stats: {STATS_FILE}")
    if orphaned_ids:
        print(f"  Orphaned IDs: {MISSING_IDS_FILE}")
    
    print("\n🔍 Next steps to find missing candidates:")
    print("  1. Check if there are pagination issues in the original export")
    print("  2. Look for candidates in other database tables not yet exported")
    print("  3. Verify if 29,176 includes duplicates or test records")
    print("  4. Check for candidates in archived or deleted status")
    
    print("=" * 80)

if __name__ == "__main__":
    comprehensive_merge()
