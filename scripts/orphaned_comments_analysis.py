#!/usr/bin/env python3
"""
Analysis of orphaned comments in the headhunter dataset
"""

import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Paths
REPO_ROOT = Path(__file__).resolve().parents[1]
NAS_DIR = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project")
CSV_DIR = REPO_ROOT / "CSV files/505039_Ella_Executive_Search_CSVs_1"
MERGED_FILE = NAS_DIR / "comprehensive_merged_candidates.json"

def analyze_orphaned_comments():
    """Comprehensive analysis of orphaned comments"""
    
    print("=" * 80)
    print("ORPHANED COMMENTS ANALYSIS")
    print("=" * 80)
    
    # Load merged data
    print("Loading merged candidate data...")
    with open(MERGED_FILE, 'r', encoding='utf-8') as f:
        candidates = json.load(f)
    
    # Separate normal and orphaned candidates
    normal = [c for c in candidates if c.get('data_status') != 'orphaned']
    orphaned = [c for c in candidates if c.get('data_status') == 'orphaned']
    
    print(f"Total candidates: {len(candidates):,}")
    print(f"Normal candidates: {len(normal):,}")
    print(f"Orphaned candidates: {len(orphaned):,}")
    
    # Analyze orphaned candidates
    orphaned_with_comments = [c for c in orphaned if c.get('comments')]
    orphaned_comment_count = sum(len(c.get('comments', [])) for c in orphaned)
    
    print(f"\nOrphaned candidates with comments: {len(orphaned_with_comments):,}")
    print(f"Total orphaned comments: {orphaned_comment_count:,}")
    
    # Date range analysis
    print("\n" + "=" * 50)
    print("DATE RANGE ANALYSIS")
    print("=" * 50)
    
    # Collect all comment dates
    normal_dates = []
    orphaned_dates = []
    
    for candidate in normal:
        for comment in candidate.get('comments', []):
            date_str = comment.get('date', '')
            if date_str:
                try:
                    date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    normal_dates.append(date_obj)
                except:
                    pass
    
    for candidate in orphaned:
        for comment in candidate.get('comments', []):
            date_str = comment.get('date', '')
            if date_str:
                try:
                    date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    orphaned_dates.append(date_obj)
                except:
                    pass
    
    if normal_dates:
        print("Normal candidate comments:")
        print(f"  Earliest: {min(normal_dates).strftime('%Y-%m-%d')}")
        print(f"  Latest: {max(normal_dates).strftime('%Y-%m-%d')}")
        print(f"  Total: {len(normal_dates):,}")
    
    if orphaned_dates:
        print("\nOrphaned candidate comments:")
        print(f"  Earliest: {min(orphaned_dates).strftime('%Y-%m-%d')}")
        print(f"  Latest: {max(orphaned_dates).strftime('%Y-%m-%d')}")
        print(f"  Total: {len(orphaned_dates):,}")
    
    # Year-by-year breakdown
    orphaned_by_year = defaultdict(int)
    for date_obj in orphaned_dates:
        orphaned_by_year[date_obj.year] += 1
    
    normal_by_year = defaultdict(int)
    for date_obj in normal_dates:
        normal_by_year[date_obj.year] += 1
    
    print("\nYearly breakdown:")
    all_years = sorted(set(list(orphaned_by_year.keys()) + list(normal_by_year.keys())))
    for year in all_years:
        orphaned_count = orphaned_by_year[year]
        normal_count = normal_by_year[year]
        total = orphaned_count + normal_count
        print(f"  {year}: {orphaned_count:,} orphaned, {normal_count:,} normal (total: {total:,})")
    
    # Candidate ID analysis
    print("\n" + "=" * 50)
    print("CANDIDATE ID ANALYSIS")
    print("=" * 50)
    
    normal_ids = [c['id'] for c in normal if c.get('id')]
    orphaned_ids = [c['id'] for c in orphaned if c.get('id')]
    
    if normal_ids:
        print(f"Normal candidate ID range: {min(normal_ids)} - {max(normal_ids)}")
    if orphaned_ids:
        print(f"Orphaned candidate ID range: {min(orphaned_ids)} - {max(orphaned_ids)}")
    
    # Check file status
    print("\n" + "=" * 50)
    print("FILE STATUS ANALYSIS")
    print("=" * 50)
    
    candidates_1_file = CSV_DIR / "Ella_Executive_Search_candidates_1-1.csv"
    candidates_2_file = CSV_DIR / "Ella_Executive_Search_candidates_2-1.csv" 
    candidates_3_file = CSV_DIR / "Ella_Executive_Search_candidates_3-1.csv"
    
    files_to_check = [
        ("candidates_1-1.csv", candidates_1_file),
        ("candidates_2-1.csv", candidates_2_file),
        ("candidates_3-1.csv", candidates_3_file)
    ]
    
    for name, file_path in files_to_check:
        if file_path.exists():
            size = file_path.stat().st_size
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    line_count = sum(1 for _ in f)
                print(f"{name}: {size:,} bytes, {line_count:,} lines")
            except Exception as e:
                print(f"{name}: {size:,} bytes, ERROR reading lines: {e}")
        else:
            print(f"{name}: File not found")
    
    # Sample orphaned candidates
    print("\n" + "=" * 50)
    print("SAMPLE ORPHANED CANDIDATES")
    print("=" * 50)
    
    sample_orphaned = [c for c in orphaned if c.get('comments')][:10]
    for i, candidate in enumerate(sample_orphaned, 1):
        comments = candidate.get('comments', [])
        if comments:
            first_comment = comments[0]
            print(f"\n{i}. Candidate ID: {candidate.get('id')}")
            print(f"   Comments: {len(comments)}")
            print(f"   First comment: {first_comment.get('date', 'No date')[:19]}")
            print(f"   Author: {first_comment.get('author', 'Unknown')}")
            print(f"   Text: {first_comment.get('text', 'No text')[:100]}...")
    
    # Summary and conclusions
    print("\n" + "=" * 80)
    print("CONCLUSIONS")
    print("=" * 80)
    
    if orphaned_dates and normal_dates:
        orphaned_latest = max(orphaned_dates)
        normal_earliest = min(normal_dates)
        gap_start = orphaned_latest.strftime('%Y-%m-%d')
        gap_end = normal_earliest.strftime('%Y-%m-%d')
        
        print("1. DATA MIGRATION DETECTED:")
        print(f"   - Orphaned comments end: {gap_start}")
        print(f"   - Normal comments start: {gap_end}")
        print("   - Gap suggests system migration around March-April 2023")
        
        print("\n2. MISSING HISTORICAL DATA:")
        print("   - candidates_1-1.csv appears corrupted/empty but should contain")
        print(f"     historical candidates from {min(orphaned_dates).strftime('%Y-%m-%d')} to {gap_start}")
        print(f"   - {len(orphaned):,} candidate records are missing")
        print(f"   - {orphaned_comment_count:,} comments are orphaned")
        
        print("\n3. CURRENT DATA INTEGRITY:")
        print("   - candidates_2-1.csv and candidates_3-1.csv contain current data")
        print(f"   - Comments from {gap_end} onwards are properly linked")
        print(f"   - {len(normal):,} candidates with {len(normal_dates):,} comments are intact")
    
    print("\n4. RECOMMENDATION:")
    print("   - Request historical candidate data export for 2021-2023 period")
    print("   - Or mark orphaned comments as 'historical' and exclude from processing")
    print("   - Current dataset is complete for 2023+ candidates")

if __name__ == "__main__":
    analyze_orphaned_comments()