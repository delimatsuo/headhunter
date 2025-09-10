#!/usr/bin/env python3
"""
Test models with REAL candidate data from CSV files
"""

import csv
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

def get_real_candidates_from_csv():
    """Get real candidates from CSV files"""
    csv_path = Path("/Users/delimatsuo/Documents/Coding/headhunter/CSV files/505039_Ella_Executive_Search_CSVs_1/Ella_Executive_Search_candidates_1-1.csv")
    
    candidates = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            if count >= 3:  # Get 3 candidates
                break
            if row.get('name') and row.get('headline'):
                # Parse the raw data
                name = row['name']
                headline = row.get('headline', '')
                experience = row.get('experience', '')
                education = row.get('education', '')
                
                candidates.append({
                    'name': name,
                    'headline': headline,
                    'experience': experience,
                    'education': education,
                    'raw_data': row
                })
                count += 1
    
    return candidates

def test_model_with_csv_candidate(model_name, candidate):
    """Test a model with real CSV candidate data"""
    
    # Build prompt from real data
    prompt = f"""Analyze this REAL candidate from our recruitment database:

Name: {candidate['name']}
Professional Headline: {candidate['headline'][:200] if candidate['headline'] else 'Not specified'}
Experience Summary: {candidate['experience'][:300] if candidate['experience'] else 'See headline'}
Education: {candidate['education'][:200] if candidate['education'] else 'See profile'}

This is ACTUAL DATA from a real candidate in our system. Provide a 150-word recruitment analysis:

1. Infer their career level from the information (Entry/Mid/Senior/Executive)
2. Estimate salary range based on the profile
3. Identify key strengths from their background
4. Recommend company types (startup/enterprise)
5. Give placement recommendation (Highly Recommended/Recommended/Consider/More Info Needed)

Be specific and realistic based on the actual data provided."""

    try:
        start = time.time()
        result = subprocess.run(
            ['ollama', 'run', model_name, prompt],
            capture_output=True,
            text=True,
            timeout=45
        )
        elapsed = time.time() - start
        
        return {
            "success": True,
            "response": result.stdout,
            "time": elapsed,
            "candidate_name": candidate['name']
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "time": 0,
            "candidate_name": candidate['name']
        }

def main():
    print("🎯 TESTING WITH REAL CSV CANDIDATE DATA")
    print("=" * 60)
    
    # Get real candidates from CSV
    print("📊 Loading REAL candidates from CSV files...")
    candidates = get_real_candidates_from_csv()
    
    if not candidates:
        print("❌ No candidates found in CSV")
        return
    
    print(f"✅ Loaded {len(candidates)} REAL candidates from CSV\n")
    
    # Use first candidate for testing
    test_candidate = candidates[0]
    
    print(f"Testing with ACTUAL candidate from database:")
    print(f"  Name: {test_candidate['name']}")
    print(f"  Headline: {test_candidate['headline'][:100] if test_candidate['headline'] else 'Not specified'}...")
    print()
    
    # Test models
    models = ["llama3.1:8b", "qwen2.5:7b", "deepseek-r1:8b"]
    results = {}
    
    for model in models:
        print(f"\n🤖 Testing {model} with REAL data...")
        result = test_model_with_csv_candidate(model, test_candidate)
        
        if result["success"]:
            print(f"✅ Success ({result['time']:.1f}s)")
            word_count = len(result['response'].split())
            print(f"   Output: {word_count} words")
        else:
            print(f"❌ Failed: {result.get('error')}")
        
        results[model] = result
    
    # Show complete outputs
    print("\n" + "=" * 60)
    print("📄 COMPLETE OUTPUTS - REAL CANDIDATE ANALYSIS")
    print("=" * 60)
    
    for model, result in results.items():
        if result["success"]:
            print(f"\n### {model.upper()} - Analysis of {result['candidate_name']} ###")
            print(f"Processing time: {result['time']:.1f} seconds")
            print("-" * 50)
            print(result['response'])
            print("\n" + "=" * 60)
    
    # Quality comparison
    print("\n📊 QUALITY METRICS")
    print("-" * 40)
    print(f"{'Model':<20} {'Time (s)':<12} {'Words':<10} {'Status'}")
    print("-" * 40)
    
    for model, result in results.items():
        if result["success"]:
            words = len(result['response'].split())
            print(f"{model:<20} {result['time']:<12.1f} {words:<10} ✅")
        else:
            print(f"{model:<20} {'N/A':<12} {'N/A':<10} ❌")
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"real_csv_candidate_test_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': timestamp,
            'candidate_tested': {
                'name': test_candidate['name'],
                'headline_preview': test_candidate['headline'][:200] if test_candidate['headline'] else None
            },
            'results': results
        }, f, indent=2)
    
    print(f"\n💾 Full results saved to: {output_file}")
    print("\n✅ Test complete with REAL candidate data from CSV!")

if __name__ == "__main__":
    main()