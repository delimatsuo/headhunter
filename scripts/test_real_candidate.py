#!/usr/bin/env python3
"""
Test models with REAL candidate data from the database
"""

import json
import sqlite3
import subprocess
import time
from datetime import datetime

def get_real_candidates():
    """Get real candidates from the database with complete information"""
    conn = sqlite3.connect('candidates.db')
    cur = conn.cursor()
    
    # Get candidates with the most complete data
    query = """
    SELECT 
        candidate_id, 
        name, 
        current_role, 
        current_company,
        years_experience,
        skills,
        education,
        experience_json,
        enriched_content
    FROM candidates 
    WHERE skills IS NOT NULL 
        AND current_role IS NOT NULL 
        AND years_experience IS NOT NULL
        AND length(skills) > 50
    ORDER BY length(skills) DESC
    LIMIT 3
    """
    
    cur.execute(query)
    candidates = cur.fetchall()
    conn.close()
    
    return candidates

def test_model_with_real_data(model_name, candidate_data):
    """Test a model with real candidate data"""
    
    name = candidate_data[1]
    role = candidate_data[2] or "Software Engineer"
    company = candidate_data[3] or "Tech Company"
    years = candidate_data[4] or 5
    skills = candidate_data[5][:200] if candidate_data[5] else "Python, AWS"
    
    prompt = f"""Analyze this REAL candidate for recruitment:

Name: {name}
Current Role: {role}
Company: {company}
Experience: {years} years
Skills: {skills}

Provide a 150-word recruitment analysis covering:
1. Career level (Junior/Mid/Senior/Principal)
2. Estimated salary range (be specific with numbers)
3. Key strengths that make them competitive
4. Best company types (startup/scaleup/enterprise)
5. Placement recommendation (Highly Recommended/Recommended/Consider)

Focus on actionable insights for recruitment."""

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
            "candidate_name": name,
            "candidate_role": role
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "time": 0,
            "candidate_name": name
        }

def main():
    print("🎯 REAL CANDIDATE MODEL COMPARISON")
    print("=" * 50)
    
    # Get real candidates
    print("📊 Loading REAL candidates from database...")
    candidates = get_real_candidates()
    
    if not candidates:
        print("❌ No suitable candidates found in database")
        return
    
    print(f"✅ Found {len(candidates)} candidates with complete data\n")
    
    # Test each model with first candidate
    models = ["llama3.1:8b", "qwen2.5:7b", "deepseek-r1:8b"]
    test_candidate = candidates[0]
    
    print(f"Testing with REAL candidate:")
    print(f"  Name: {test_candidate[1]}")
    print(f"  Role: {test_candidate[2]}")
    print(f"  Company: {test_candidate[3]}")
    print(f"  Years: {test_candidate[4]}")
    print(f"  Skills preview: {test_candidate[5][:100]}...")
    print()
    
    results = {}
    
    for model in models:
        print(f"🤖 Testing {model}...")
        result = test_model_with_real_data(model, test_candidate)
        
        if result["success"]:
            print(f"✅ Success ({result['time']:.1f}s)")
            print(f"Output preview:\n{result['response'][:300]}...\n")
        else:
            print(f"❌ Failed: {result.get('error')}\n")
        
        results[model] = result
    
    # Show full outputs
    print("\n" + "=" * 50)
    print("📄 FULL MODEL OUTPUTS WITH REAL DATA")
    print("=" * 50)
    
    for model, result in results.items():
        if result["success"]:
            print(f"\n### {model.upper()} ###")
            print(f"Time: {result['time']:.1f} seconds")
            print(f"Analysis for: {result['candidate_name']} ({result['candidate_role']})")
            print("-" * 40)
            print(result['response'])
            print()
    
    # Save comparison
    with open(f"real_candidate_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    print("✅ Comparison complete with REAL candidate data!")

if __name__ == "__main__":
    main()