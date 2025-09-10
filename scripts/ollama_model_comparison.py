#!/usr/bin/env python3
"""
Compare different Ollama models for recruitment analysis
Tests: Llama 3.1 8B vs DeepSeek-R1 8B vs Qwen 2.5 7B vs Gemma2 9B
"""

import json
import time
import subprocess
from pathlib import Path
from datetime import datetime
import random

# Models to test (will install if not present)
MODELS_TO_TEST = [
    {"name": "llama3.1:8b", "display": "Llama 3.1 8B"},
    {"name": "deepseek-r1:8b", "display": "DeepSeek-R1 8B"},
    {"name": "qwen2.5:7b", "display": "Qwen 2.5 7B"},
    {"name": "gemma2:9b", "display": "Gemma2 9B"},
    {"name": "llama3.3:latest", "display": "Llama 3.3 Latest"}
]

def check_and_install_model(model_name):
    """Check if model is installed, install if not"""
    print(f"🔍 Checking for {model_name}...")
    
    # Check if model exists
    result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
    if model_name.split(':')[0] in result.stdout:
        print(f"✅ {model_name} is installed")
        return True
    
    print(f"📦 Installing {model_name}... (this may take a while)")
    result = subprocess.run(['ollama', 'pull', model_name], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ {model_name} installed successfully")
        return True
    else:
        print(f"❌ Failed to install {model_name}: {result.stderr}")
        return False

def test_model(model_name, candidate_data):
    """Test a specific model with candidate data"""
    prompt = f"""You are an expert recruiter analyzing a candidate profile. Provide a comprehensive JSON analysis.

Candidate Information:
- Name: {candidate_data['name']}
- Years of Experience: {candidate_data['years_experience']}
- Current Role: {candidate_data['current_role']}
- Skills: {', '.join(candidate_data['skills'])}
- Companies: {', '.join(candidate_data['companies'])}
- Education: {candidate_data['education']}

Provide analysis in this exact JSON format:
{{
  "career_trajectory": {{
    "current_level": "Junior/Mid/Senior/Principal/Director",
    "progression_speed": "slow/steady/rapid",
    "next_logical_role": "specific role title",
    "years_to_next_level": number
  }},
  "market_positioning": {{
    "competitive_score": 1-100,
    "salary_range": "$XXX,000 - $XXX,000",
    "demand_level": "low/moderate/high/very high",
    "unique_strengths": ["strength1", "strength2"]
  }},
  "company_tier_analysis": {{
    "current_tier": "Tier1/Tier2/Tier3",
    "brand_strength": "weak/moderate/strong",
    "network_value": "low/medium/high"
  }},
  "ai_recommendation": {{
    "hire_score": 1-100,
    "best_fit_roles": ["role1", "role2"],
    "development_areas": ["area1", "area2"],
    "retention_risk": "low/medium/high"
  }},
  "summary": "One paragraph professional assessment"
}}

Respond with ONLY the JSON, no additional text."""

    try:
        # Run ollama with the model
        start_time = time.time()
        result = subprocess.run(
            ['ollama', 'run', model_name, prompt],
            capture_output=True,
            text=True,
            timeout=60
        )
        end_time = time.time()
        
        response = result.stdout.strip()
        
        # Try to parse JSON from response
        try:
            # Find JSON in response (in case model adds text)
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                parsed = json.loads(json_str)
                
                return {
                    "success": True,
                    "response": parsed,
                    "raw_response": response,
                    "processing_time": end_time - start_time,
                    "response_length": len(response)
                }
            else:
                raise ValueError("No JSON found in response")
                
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON parse error: {e}",
                "raw_response": response[:500],
                "processing_time": end_time - start_time
            }
            
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Model timeout (60s)",
            "processing_time": 60
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "processing_time": 0
        }

def create_test_candidates():
    """Create test candidate profiles"""
    return [
        {
            "name": "Sarah Chen",
            "years_experience": 8,
            "current_role": "Senior Software Engineer",
            "skills": ["Python", "React", "AWS", "Docker", "Machine Learning", "PostgreSQL"],
            "companies": ["Google", "Meta", "Startup (Series B)"],
            "education": "MS Computer Science, Stanford"
        },
        {
            "name": "Michael Rodriguez",
            "years_experience": 5,
            "current_role": "Data Scientist",
            "skills": ["Python", "TensorFlow", "SQL", "Spark", "Statistics", "A/B Testing"],
            "companies": ["Amazon", "Uber"],
            "education": "BS Mathematics, MIT"
        },
        {
            "name": "Emily Johnson",
            "years_experience": 12,
            "current_role": "Engineering Manager",
            "skills": ["Leadership", "Agile", "Java", "System Design", "Team Building"],
            "companies": ["Microsoft", "Netflix", "Apple"],
            "education": "BS Computer Engineering, UC Berkeley"
        }
    ]

def calculate_quality_score(response):
    """Calculate quality score for a model response"""
    if not response.get("success"):
        return 0
    
    score = 0
    data = response.get("response", {})
    
    # Check completeness (40 points)
    expected_keys = ["career_trajectory", "market_positioning", "company_tier_analysis", "ai_recommendation", "summary"]
    for key in expected_keys:
        if key in data:
            score += 8
    
    # Check depth of analysis (30 points)
    if data.get("career_trajectory", {}).get("next_logical_role"):
        score += 10
    if data.get("market_positioning", {}).get("salary_range"):
        score += 10
    if data.get("ai_recommendation", {}).get("best_fit_roles"):
        score += 10
    
    # Check specificity (20 points)
    summary = data.get("summary", "")
    if len(summary) > 100:
        score += 10
    if any(company in summary for company in ["Google", "Meta", "Amazon", "Microsoft"]):
        score += 10
    
    # Speed bonus (10 points)
    if response.get("processing_time", 100) < 10:
        score += 10
    elif response.get("processing_time", 100) < 20:
        score += 5
    
    return score

def main():
    print("🧪 OLLAMA MODEL COMPARISON FOR RECRUITMENT ANALYSIS")
    print("=" * 60)
    
    # Check available models
    print("\\n📋 Checking available models...")
    available_models = []
    
    for model_info in MODELS_TO_TEST:
        if check_and_install_model(model_info["name"]):
            available_models.append(model_info)
    
    if not available_models:
        print("❌ No models available for testing")
        return False
    
    print(f"\\n✅ Testing {len(available_models)} models")
    
    # Create test candidates
    candidates = create_test_candidates()
    print(f"📊 Using {len(candidates)} test candidates")
    
    # Test each model
    results = {}
    
    for model_info in available_models:
        model_name = model_info["name"]
        display_name = model_info["display"]
        
        print(f"\\n🤖 Testing {display_name}...")
        model_results = []
        
        for i, candidate in enumerate(candidates, 1):
            print(f"  Candidate {i}/{len(candidates)}: {candidate['name']}")
            result = test_model(model_name, candidate)
            result["candidate"] = candidate["name"]
            model_results.append(result)
            
            if result["success"]:
                print(f"    ✅ Success ({result['processing_time']:.1f}s)")
            else:
                print(f"    ❌ Failed: {result.get('error', 'Unknown error')}")
        
        results[display_name] = model_results
    
    # Generate comparison report
    print("\\n📊 COMPARISON RESULTS")
    print("=" * 60)
    
    comparison_table = []
    
    for model_name, model_results in results.items():
        successful = [r for r in model_results if r["success"]]
        
        if successful:
            avg_time = sum(r["processing_time"] for r in successful) / len(successful)
            avg_quality = sum(calculate_quality_score(r) for r in successful) / len(successful)
            success_rate = len(successful) / len(model_results) * 100
        else:
            avg_time = 0
            avg_quality = 0
            success_rate = 0
        
        comparison_table.append({
            "model": model_name,
            "success_rate": success_rate,
            "avg_time": avg_time,
            "quality_score": avg_quality
        })
    
    # Sort by quality score
    comparison_table.sort(key=lambda x: x["quality_score"], reverse=True)
    
    # Print results
    print(f"{'Model':<20} {'Success Rate':<15} {'Avg Time (s)':<15} {'Quality Score':<15}")
    print("-" * 65)
    
    for row in comparison_table:
        print(f"{row['model']:<20} {row['success_rate']:.1f}%{'':<10} {row['avg_time']:.1f}s{'':<10} {row['quality_score']:.1f}/100")
    
    # Save detailed results
    report_path = Path(__file__).parent / f"ollama_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, 'w') as f:
        json.dump({
            "test_date": datetime.now().isoformat(),
            "models_tested": [m["display"] for m in available_models],
            "candidates_tested": candidates,
            "detailed_results": results,
            "summary": comparison_table
        }, f, indent=2)
    
    print(f"\\n💾 Detailed report saved to: {report_path}")
    
    # Recommendation
    if comparison_table:
        best_model = comparison_table[0]
        print(f"\\n🏆 RECOMMENDATION: {best_model['model']}")
        print(f"   Quality Score: {best_model['quality_score']:.1f}/100")
        print(f"   Processing Time: {best_model['avg_time']:.1f}s per candidate")
        print(f"   Success Rate: {best_model['success_rate']:.1f}%")
        
        if best_model['quality_score'] > 70:
            print("\\n✅ This model is suitable for production recruitment analysis")
        elif best_model['quality_score'] > 50:
            print("\\n⚠️ This model provides adequate analysis but could be improved")
        else:
            print("\\n❌ Consider using Vertex AI for better quality analysis")
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)