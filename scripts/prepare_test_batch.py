#!/usr/bin/env python3
"""
Prepare test batch of 10 candidates from CSV for intelligent skill processing
"""

import csv
import json
import os
from pathlib import Path

def load_candidates_from_csv(csv_path: str, limit: int = 10):
    """Load candidates from CSV file"""
    candidates = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= limit:
                break

            # Convert CSV row to candidate format
            candidate = {
                "id": row.get('id', ''),
                "name": row.get('name', 'Unknown'),
                "email": row.get('email', ''),
                "headline": row.get('headline', ''),
                "education": row.get('education', ''),
                "experience": row.get('experience', ''),
                "skills": row.get('skills', ''),
                "summary": row.get('summary', ''),
                "social_profiles": row.get('social_profiles', '[]'),
                "stage": row.get('stage', ''),
                "job": row.get('job', ''),
                "tags": row.get('tags', ''),
                "comments": []  # Will need to load from comments CSV separately
            }

            candidates.append(candidate)

    return candidates

def main():
    # Project root
    project_root = Path("/Volumes/Extreme Pro/myprojects/headhunter")

    # CSV file path
    csv_file = project_root / "CSV files" / "505039_Ella_Executive_Search_CSVs_1" / "Ella_Executive_Search_candidates_1-1.csv"

    # Output path
    output_file = project_root / "scripts" / "test_batch_10_candidates.json"

    print(f"📂 Loading 10 candidates from CSV...")
    candidates = load_candidates_from_csv(str(csv_file), limit=10)

    print(f"✅ Loaded {len(candidates)} candidates")
    print(f"📝 Sample candidate: {candidates[0]['name']}")

    # Save to JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(candidates, f, indent=2, ensure_ascii=False)

    print(f"💾 Saved test batch to: {output_file}")
    print(f"\n📊 Candidate names:")
    for i, c in enumerate(candidates, 1):
        print(f"   {i}. {c['name']} - {c.get('headline', 'No headline')[:50]}")

if __name__ == "__main__":
    main()
