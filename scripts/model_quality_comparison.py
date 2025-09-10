#!/usr/bin/env python3
"""
Quality comparison of Ollama models vs current Llama 3.1 8B output
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime

def get_sample_candidate():
    """Get a real candidate from our enhanced files"""
    enhanced_dir = Path(__file__).parent / "enhanced_analysis"
    
    # Get first enhanced file
    json_files = list(enhanced_dir.glob("*_enhanced.json"))
    if json_files:
        with open(json_files[0], 'r') as f:
            return json.load(f)
    return None

def extract_candidate_info(enhanced_data):
    """Extract key info from enhanced candidate"""
    return {
        "name": enhanced_data.get('personal_details', {}).get('name', 'John Smith'),
        "years": enhanced_data.get('personal_details', {}).get('years_of_experience', '8'),
        "role": enhanced_data.get('experience_analysis', {}).get('current_role', 'Senior Engineer'),
        "skills": ', '.join(enhanced_data.get('technical_assessment', {}).get('primary_skills', ['Python', 'AWS'])[:5]),
        "companies": ', '.join(enhanced_data.get('experience_analysis', {}).get('companies', ['Tech Company'])[:3])
    }

def test_model_quality(model_name, candidate_info):
    """Test model with recruitment analysis prompt"""
    
    prompt = f"""Analyze this tech professional for recruitment:

Name: {candidate_info['name']}
Experience: {candidate_info['years']} years
Current: {candidate_info['role']}
Skills: {candidate_info['skills']}
Companies: {candidate_info['companies']}

Provide a 150-word recruitment analysis covering:
1. Career trajectory assessment (Junior/Mid/Senior/Principal)
2. Estimated market value/salary range
3. Key competitive advantages
4. Best fit company types (startup/enterprise)
5. Placement recommendation (highly recommended/recommended/consider)

Be specific and data-driven."""

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
            "word_count": len(result.stdout.split())
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "time": 0
        }

def analyze_response_quality(response_text):
    """Score response quality based on key indicators"""
    score = 0
    
    # Check for specific analysis elements (10 points each)
    quality_indicators = [
        # Career level assessment
        any(level in response_text.lower() for level in ['junior', 'mid', 'senior', 'principal', 'staff']),
        # Salary mention
        '$' in response_text,
        # Company type recommendation
        any(comp in response_text.lower() for comp in ['startup', 'enterprise', 'corporate', 'faang']),
        # Specific skills mentioned
        any(skill in response_text.lower() for skill in ['python', 'java', 'aws', 'react', 'docker']),
        # Recommendation language
        any(rec in response_text.lower() for rec in ['recommend', 'strong', 'excellent', 'qualified']),
        # Years/experience mentioned
        any(word in response_text.lower() for word in ['years', 'experience', 'seasoned']),
        # Market insight
        any(market in response_text.lower() for market in ['market', 'demand', 'competitive']),
        # Trajectory/growth
        any(growth in response_text.lower() for growth in ['trajectory', 'growth', 'progression', 'advancement']),
        # Specific role suggestions
        any(role in response_text.lower() for role in ['engineer', 'developer', 'architect', 'manager', 'lead']),
        # Quantitative assessment
        any(char.isdigit() for char in response_text)
    ]
    
    score = sum(10 for indicator in quality_indicators if indicator)
    
    return score

def main():
    print("🎯 MODEL QUALITY COMPARISON FOR RECRUITMENT")
    print("=" * 50)
    
    # Get real candidate data
    print("📋 Loading sample candidate...")
    sample = get_sample_candidate()
    
    if not sample:
        print("Creating test candidate...")
        candidate_info = {
            "name": "Alex Chen",
            "years": "8",
            "role": "Senior Software Engineer",
            "skills": "Python, React, AWS, Docker, PostgreSQL",
            "companies": "Google, Meta, Series B Startup"
        }
    else:
        candidate_info = extract_candidate_info(sample)
    
    print(f"Testing with: {candidate_info['name']} ({candidate_info['years']} years experience)")
    print()
    
    # Models to test
    models = ["llama3.1:8b", "deepseek-r1:8b", "qwen2.5:7b"]
    results = {}
    
    for model in models:
        print(f"🤖 Testing {model}...")
        result = test_model_quality(model, candidate_info)
        
        if result["success"]:
            quality_score = analyze_response_quality(result["response"])
            result["quality_score"] = quality_score
            print(f"✅ Complete ({result['time']:.1f}s, Quality: {quality_score}/100)")
            print(f"Preview: {result['response'][:200]}...\\n")
        else:
            result["quality_score"] = 0
            print(f"❌ Failed: {result.get('error')}\\n")
        
        results[model] = result
    
    # Comparison summary
    print("\\n" + "=" * 50)
    print("📊 QUALITY COMPARISON RESULTS")
    print("=" * 50)
    
    print(f"\\n{'Model':<20} {'Time':<10} {'Words':<10} {'Quality':<10}")
    print("-" * 50)
    
    for model, result in results.items():
        if result["success"]:
            print(f"{model:<20} {result['time']:.1f}s{'':<5} {result['word_count']:<10} {result['quality_score']}/100")
        else:
            print(f"{model:<20} Failed{'':<5} 0{'':<10} 0/100")
    
    # Determine winner
    successful = [(m, r) for m, r in results.items() if r["success"]]
    if successful:
        best = max(successful, key=lambda x: x[1]["quality_score"])
        print(f"\\n🏆 BEST QUALITY: {best[0]} (Score: {best[1]['quality_score']}/100)")
        
        # Show full best response
        print(f"\\n📝 Best Response from {best[0]}:")
        print("-" * 40)
        print(best[1]["response"])
    
    # Save detailed comparison
    report_path = Path(__file__).parent / f"model_quality_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "candidate_tested": candidate_info,
            "results": results
        }, f, indent=2)
    
    print(f"\\n💾 Full comparison saved to: {report_path}")

if __name__ == "__main__":
    main()