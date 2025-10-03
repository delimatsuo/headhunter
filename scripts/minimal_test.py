#!/usr/bin/env python3
"""
Minimal test with just 5 candidates to measure timing
"""

import json
import time
import requests
from pathlib import Path

# Constants
NAS_DIR = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project")
MERGED_FILE = NAS_DIR / "comprehensive_merged_candidates.json"

def test_5_candidates():
    print("=" * 60)
    print("MINIMAL TEST: 5 Candidates with Llama 3.1:8b")
    print("=" * 60)
    
    # Load 5 candidates
    print("Loading first 5 candidates...")
    with open(MERGED_FILE, 'r', encoding='utf-8') as f:
        all_candidates = json.load(f)
    
    # Get first 5 normal candidates
    normal_candidates = [c for c in all_candidates if c.get('data_status') != 'orphaned' and c.get('name')]
    candidates = normal_candidates[:5]
    
    print(f"Selected {len(candidates)} candidates")
    
    # Process each candidate
    total_start = time.time()
    results = []
    
    for i, candidate in enumerate(candidates, 1):
        print(f"\n[{i}/5] Processing: {candidate.get('name')}")
        
        candidate_start = time.time()
        
        # Simple prompt
        prompt = f"""Candidate: {candidate.get('name')}
Title: {candidate.get('headline', 'N/A')}
Skills: {candidate.get('skills', 'N/A')}
Comments: {len(candidate.get('comments', []))} total

Rate this candidate from 1-10 and list 3 key skills. Respond in JSON format:
{{"rating": 8, "skills": ["skill1", "skill2", "skill3"]}}"""

        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3.1:8b",
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                processing_time = time.time() - candidate_start
                
                results.append({
                    'name': candidate.get('name'),
                    'time': processing_time,
                    'response': result.get('response', '')[:200] + '...'  # Truncate
                })
                
                print(f"  ✓ {processing_time:.2f}s")
            else:
                print(f"  ✗ HTTP {response.status_code}")
                
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    total_time = time.time() - total_start
    avg_time = total_time / len(candidates)
    
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Total time: {total_time:.2f} seconds")
    print(f"Average per candidate: {avg_time:.2f} seconds")
    
    # Extrapolate
    total_candidates = 23594
    estimated_hours = (total_candidates * avg_time) / 3600
    
    print(f"\nExtrapolation to {total_candidates:,} candidates:")
    print(f"  Estimated time: {estimated_hours:.1f} hours")
    print(f"  Estimated days (24/7): {estimated_hours/24:.1f} days")
    print(f"  Estimated days (8hr/day): {estimated_hours/8:.1f} work days")
    
    print("\nIndividual results:")
    for result in results:
        print(f"  {result['name']}: {result['time']:.2f}s")

if __name__ == "__main__":
    test_5_candidates()