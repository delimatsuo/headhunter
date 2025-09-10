#!/usr/bin/env python3
"""
Quick comparison of Ollama models for recruitment analysis
"""

import json
import time
import subprocess
from datetime import datetime

# Test with already installed models
MODELS = [
    "llama3.1:8b",
    "deepseek-r1:8b", 
    "qwen2.5:7b"
]

def test_model(model_name):
    """Quick test of a model"""
    prompt = """Analyze this candidate in 100 words or less:
Senior Software Engineer, 8 years experience, Python/React/AWS, worked at Google and Meta.
Provide: 1) Career level 2) Market value 3) Key strength"""
    
    try:
        start = time.time()
        result = subprocess.run(
            ['ollama', 'run', model_name, prompt],
            capture_output=True,
            text=True,
            timeout=30  # 30 second timeout per model
        )
        elapsed = time.time() - start
        
        return {
            "model": model_name,
            "success": True,
            "response": result.stdout[:500],
            "time": elapsed
        }
    except subprocess.TimeoutExpired:
        return {
            "model": model_name,
            "success": False,
            "error": "Timeout",
            "time": 30
        }
    except Exception as e:
        return {
            "model": model_name,
            "success": False,
            "error": str(e),
            "time": 0
        }

def main():
    print("🚀 QUICK MODEL COMPARISON")
    print("=" * 40)
    
    results = []
    
    for model in MODELS:
        print(f"\n📝 Testing {model}...")
        result = test_model(model)
        results.append(result)
        
        if result["success"]:
            print(f"✅ Success ({result['time']:.1f}s)")
            print(f"Response preview: {result['response'][:150]}...")
        else:
            print(f"❌ Failed: {result.get('error')}")
    
    # Summary
    print("\n📊 RESULTS SUMMARY")
    print("-" * 40)
    print(f"{'Model':<20} {'Time (s)':<10} {'Status':<10}")
    print("-" * 40)
    
    for r in results:
        status = "✅ Success" if r["success"] else "❌ Failed"
        print(f"{r['model']:<20} {r['time']:.1f}s{'':<5} {status}")
    
    # Save results
    with open(f"quick_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n✅ Comparison complete!")
    
    # Show best performer
    successful = [r for r in results if r["success"]]
    if successful:
        fastest = min(successful, key=lambda x: x["time"])
        print(f"\n⚡ Fastest: {fastest['model']} ({fastest['time']:.1f}s)")

if __name__ == "__main__":
    main()