#!/usr/bin/env python3
"""
Deep scan to find ALL unique candidate IDs across ALL CSV files
"""

import csv
from pathlib import Path
from typing import Set, Dict
import json

# Constants
BASE_DIR = Path("/Users/delimatsuo/Documents/Coding/headhunter")
CSV_DIR = BASE_DIR / "CSV files" / "505039_Ella_Executive_Search_CSVs_1"
NAS_DIR = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project")

def deep_scan_for_ids():
    """Deep scan ALL CSV files for any ID-like values"""
    print("=" * 80)
    print("DEEP SCAN FOR ALL CANDIDATE IDs")
    print("=" * 80)
    
    all_ids_by_file = {}
    all_unique_ids = set()
    
    # Get all CSV files
    csv_files = sorted(CSV_DIR.glob("*.csv"))
    print(f"\nFound {len(csv_files)} CSV files to scan")
    
    for csv_file in csv_files:
        print(f"\n📄 Scanning: {csv_file.name}")
        file_ids = set()
        
        try:
            with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                
                # Get column names
                first_row = next(reader, None)
                if not first_row:
                    print("  Empty file")
                    continue
                
                # Find ID-like columns
                id_columns = []
                for col in first_row.keys():
                    if col and ('id' in col.lower() or col.lower() in ['candidateid', 'candidate_id']):
                        id_columns.append(col)
                
                print(f"  ID columns found: {id_columns}")
                
                # Reset to beginning
                f.seek(0)
                reader = csv.DictReader(f)
                
                # Count rows and extract IDs
                row_count = 0
                for row in reader:
                    row_count += 1
                    for col in id_columns:
                        val = row.get(col, '').strip()
                        # Only consider numeric IDs with at least 5 digits
                        if val and val.isdigit() and len(val) >= 5:
                            file_ids.add(val)
                            all_unique_ids.add(val)
                
                print(f"  Rows: {row_count:,}")
                print(f"  Unique IDs found: {len(file_ids):,}")
                
                if file_ids:
                    # Show sample IDs
                    sample = sorted(list(file_ids))[:5]
                    print(f"  Sample IDs: {sample}")
                
                all_ids_by_file[csv_file.name] = {
                    'count': len(file_ids),
                    'ids': sorted(list(file_ids))
                }
                
        except Exception as e:
            print(f"  ERROR: {e}")
    
    # Analyze overlap between files
    print("\n" + "=" * 80)
    print("ANALYSIS SUMMARY")
    print("=" * 80)
    
    print(f"\nTotal unique candidate IDs across ALL files: {len(all_unique_ids):,}")
    
    # Find which files have the most IDs
    sorted_files = sorted(all_ids_by_file.items(), key=lambda x: x[1]['count'], reverse=True)
    
    print("\nTop files by candidate count:")
    for filename, data in sorted_files[:10]:
        if data['count'] > 0:
            print(f"  {filename}: {data['count']:,} IDs")
    
    # Check specific candidate files
    print("\n📊 Main candidate files:")
    candidate_files = ['Ella_Executive_Search_candidates_2-1.csv', 
                      'Ella_Executive_Search_candidates_3-1.csv',
                      'Ella_Executive_Search_talent_pool_candidates_1-1.csv']
    
    main_ids = set()
    for cf in candidate_files:
        if cf in all_ids_by_file:
            count = all_ids_by_file[cf]['count']
            main_ids.update(all_ids_by_file[cf]['ids'])
            print(f"  {cf}: {count:,} IDs")
    
    print(f"\nTotal in main candidate files: {len(main_ids):,}")
    
    # Find IDs not in main files
    orphaned_ids = all_unique_ids - main_ids
    print(f"IDs not in main candidate files: {len(orphaned_ids):,}")
    
    # Save detailed report
    report = {
        'total_unique_ids': len(all_unique_ids),
        'main_candidate_file_ids': len(main_ids),
        'orphaned_ids': len(orphaned_ids),
        'target_count': 29176,
        'difference': 29176 - len(all_unique_ids),
        'files_scanned': len(csv_files),
        'file_details': all_ids_by_file
    }
    
    report_file = NAS_DIR / "candidate_id_deep_scan_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n💾 Detailed report saved to: {report_file}")
    
    # Save all unique IDs
    all_ids_file = NAS_DIR / "all_unique_candidate_ids.json"
    with open(all_ids_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total': len(all_unique_ids),
            'ids': sorted(list(all_unique_ids))
        }, f, indent=2)
    
    print(f"💾 All unique IDs saved to: {all_ids_file}")
    
    print("\n" + "=" * 80)
    print(f"FINAL COUNT: {len(all_unique_ids):,} unique candidate IDs")
    print(f"TARGET: 29,176")
    print(f"DIFFERENCE: {29176 - len(all_unique_ids):,}")
    print("=" * 80)
    
    return all_unique_ids

if __name__ == "__main__":
    deep_scan_for_ids()