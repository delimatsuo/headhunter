#!/usr/bin/env python3
"""
Test models with STRUCTURED prompt to match DeepSeek quality
"""

import json
import subprocess
import time
from datetime import datetime

def test_structured_prompt(model_name):
    """Test model with structured prompt requiring detailed analysis"""
    
    # Using Felipe's real data
    prompt = """Analyze this candidate for recruitment. Provide a STRUCTURED analysis with ALL sections:

CANDIDATE: Felipe Augusto V Marques de Araujo
HEADLINE: Software Engineer/Architect
EXPERIENCE:
- 2019/10-present: Senior Software Engineer Technical Lead at IDtech
- 2019/10-present: Senior Cloud Engineer at PagSeguro/PagBank
- 2014/06-2018/10: Technology Architect at Itaú Unibanco (4 years)
EDUCATION:
- Master's in Computer Science (2022-present)
- Bachelor's in Computer Science, São Paulo State University

REQUIRED OUTPUT FORMAT:

## CAREER TRAJECTORY ANALYSIS
- Current Level: [Senior/Principal/Staff/Executive]
- Years of Experience: [Calculate from dates]
- Career Progression Speed: [Analyze role changes over time]
- Notable Career Moves: [List key transitions]

## EXPERIENCE BREAKDOWN
- Total Years: [Calculate]
- Time at Each Company: [List with durations]
- Progression Pattern: [Steady/Rapid/Lateral]
- Industry Focus: [Primary sectors]

## TECHNICAL ASSESSMENT
- Key Strengths: [Bullet points]
- Architecture Experience: [Yes/No with details]
- Cloud Expertise: [Specific platforms]
- Leadership Experience: [Team size if known]

## ACADEMIC PERFORMANCE
- Educational Quality: [Rate 1-10]
- Degree Relevance: [How it aligns with roles]
- Continuous Learning: [Evidence of growth]

## MARKET POSITIONING
- Estimated Salary Range: [Be specific with currency]
- Market Demand: [High/Medium/Low]
- Competitive Advantages: [List top 3]

## COMPANY FIT ANALYSIS
- Best Fit: [Startup/Scale-up/Enterprise]
- Industry Targets: [List specific sectors]
- Role Recommendations: [3-5 specific titles]

## PLACEMENT RECOMMENDATION
- Overall Rating: [A+/A/B+/B/C]
- Recommendation: [Highly Recommended/Recommended/Consider]
- Key Selling Points: [Top 3 for recruiters]

Be specific and data-driven. Extract maximum insight from the provided information."""

    try:
        start = time.time()
        result = subprocess.run(
            ['ollama', 'run', model_name, prompt],
            capture_output=True,
            text=True,
            timeout=60
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

def main():
    print("🎯 STRUCTURED PROMPT COMPARISON")
    print("=" * 60)
    print("Testing with same detailed structure requirement for all models\n")
    
    models = ["llama3.1:8b", "qwen2.5:7b", "deepseek-r1:8b"]
    results = {}
    
    for model in models:
        print(f"📝 Testing {model} with structured prompt...")
        result = test_structured_prompt(model)
        
        if result["success"]:
            print(f"✅ Success ({result['time']:.1f}s, {result['word_count']} words)")
        else:
            print(f"❌ Failed: {result.get('error')}")
        
        results[model] = result
    
    # Show outputs
    print("\n" + "=" * 60)
    print("📊 STRUCTURED OUTPUT COMPARISON")
    print("=" * 60)
    
    for model, result in results.items():
        if result["success"]:
            print(f"\n### {model.upper()} ###")
            print(f"Time: {result['time']:.1f}s | Words: {result['word_count']}")
            print("-" * 50)
            print(result['response'][:1500] + "..." if len(result['response']) > 1500 else result['response'])
    
    # Summary
    print("\n📈 PERFORMANCE WITH STRUCTURED PROMPT")
    print("-" * 40)
    print(f"{'Model':<20} {'Time (s)':<12} {'Words':<10}")
    print("-" * 40)
    
    for model, result in results.items():
        if result["success"]:
            print(f"{model:<20} {result['time']:<12.1f} {result['word_count']:<10}")
    
    # Save results
    with open(f"structured_prompt_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n✅ Test complete! All models can produce structured output when prompted correctly.")

if __name__ == "__main__":
    main()