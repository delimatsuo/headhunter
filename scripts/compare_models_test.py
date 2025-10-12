#!/usr/bin/env python3
"""
Model Comparison Test: A/B/C Testing
Compare Llama 3.1 8B vs Qwen 2.5 7B vs Llama 3.1 70B
50 candidates per model to determine best cost-benefit
"""

import json
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.intelligent_skill_processor import IntelligentSkillProcessor
from dotenv import load_dotenv

load_dotenv()

def clean_for_json(obj):
    """Remove Firestore Sentinel objects and other non-serializable types for JSON serialization"""
    if obj is None:
        return None

    # Check for Firestore Sentinel objects by class name (avoid importing firestore)
    if hasattr(obj, '__class__') and 'Sentinel' in obj.__class__.__name__:
        return datetime.now().isoformat()

    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [clean_for_json(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()

    return obj

MODELS = {
    "A": {
        "name": "Llama 3.1 8B Instruct Turbo",
        "id": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        "cost_per_1m": 0.18,
        "description": "Current model - lowest cost"
    },
    "B": {
        "name": "Qwen 2.5 7B Instruct Turbo",
        "id": "Qwen/Qwen2.5-7B-Instruct-Turbo",
        "cost_per_1m": 0.30,
        "description": "Optimized for structured extraction"
    },
    "C": {
        "name": "Llama 3.1 70B Instruct Turbo",
        "id": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        "cost_per_1m": 0.88,
        "description": "Highest quality reasoning"
    }
}

async def test_model(model_key: str, candidates: list, output_dir: Path):
    """Test a single model with candidates"""

    model_info = MODELS[model_key]
    print(f"\n{'='*80}")
    print(f"TESTING MODEL {model_key}: {model_info['name']}")
    print(f"Cost: ${model_info['cost_per_1m']}/1M tokens")
    print(f"{model_info['description']}")
    print(f"{'='*80}\n")

    # Override model in environment
    os.environ['TOGETHER_MODEL_STAGE1'] = model_info['id']

    results = []

    async with IntelligentSkillProcessor() as processor:
        processor.use_firestore = False  # Test mode

        for i, candidate in enumerate(candidates, 1):
            print(f"[Model {model_key}] Processing {i}/{len(candidates)}: {candidate.get('name', 'Unknown')}")

            result = await processor.process_candidate(candidate)

            if result:
                results.append(result)

                # Quick quality check
                explicit = len(result.get('explicit_skills', []))
                inferred = len(result.get('inferred_skills_high_confidence', []))
                print(f"  ✅ Success - Explicit: {explicit}, Inferred: {inferred}")
            else:
                print(f"  ❌ Failed")

    # Save results
    output_file = output_dir / f"model_{model_key}_{model_info['id'].replace('/', '_')}_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(clean_for_json({
            "model_info": model_info,
            "test_timestamp": datetime.now().isoformat(),
            "total_candidates": len(candidates),
            "successful_results": len(results),
            "results": results
        }), f, indent=2, ensure_ascii=False)

    print(f"\n✅ Model {model_key} complete: {len(results)}/{len(candidates)} successful")
    print(f"📁 Results saved to: {output_file}\n")

    return {
        "model_key": model_key,
        "model_info": model_info,
        "successful_count": len(results),
        "total_count": len(candidates),
        "success_rate": len(results) / len(candidates) if candidates else 0,
        "results": results
    }

async def analyze_quality(model_results: dict):
    """Analyze quality metrics for comparison"""

    results = model_results['results']

    if not results:
        return {
            "avg_explicit_skills": 0,
            "avg_inferred_skills": 0,
            "avg_confidence": 0,
            "skill_diversity": 0
        }

    explicit_counts = [len(r.get('explicit_skills', [])) for r in results]
    inferred_counts = [len(r.get('inferred_skills_high_confidence', [])) for r in results]

    # Extract confidence scores
    confidences = []
    for r in results:
        ia = r.get('intelligent_analysis', {})
        inferred = ia.get('inferred_skills', {})
        for skill_list in inferred.get('highly_probable_skills', []):
            if isinstance(skill_list, dict):
                conf = skill_list.get('confidence')
                if conf:
                    confidences.append(conf)

    # Unique skills across all candidates
    all_skills = set()
    for r in results:
        all_skills.update(r.get('explicit_skills', []))
        all_skills.update(r.get('inferred_skills_high_confidence', []))

    return {
        "avg_explicit_skills": sum(explicit_counts) / len(explicit_counts) if explicit_counts else 0,
        "avg_inferred_skills": sum(inferred_counts) / len(inferred_counts) if inferred_counts else 0,
        "avg_confidence": sum(confidences) / len(confidences) if confidences else 0,
        "skill_diversity": len(all_skills),
        "total_skills_extracted": sum(explicit_counts) + sum(inferred_counts)
    }

async def main():
    """Run comprehensive model comparison"""

    # Load 50 candidates
    input_file = Path(__file__).parent / "test_batch_10_candidates.json"

    # We need to prepare 50 candidates first
    print("📂 Preparing 50 candidate test batch...")

    # For now, use the CSV to create 50 candidates
    import csv
    csv_file = project_root / "CSV files" / "505039_Ella_Executive_Search_CSVs_1" / "Ella_Executive_Search_candidates_1-1.csv"

    candidates = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= 50:
                break

            candidates.append({
                "id": row.get('id', ''),
                "name": row.get('name', 'Unknown'),
                "email": row.get('email', ''),
                "headline": row.get('headline', ''),
                "education": row.get('education', ''),
                "experience": row.get('experience', ''),
                "skills": row.get('skills', ''),
                "summary": row.get('summary', ''),
                "comments": []
            })

    print(f"✅ Loaded {len(candidates)} candidates for testing\n")

    # Create output directory
    output_dir = Path(__file__).parent / "model_comparison_results"
    output_dir.mkdir(exist_ok=True)

    # Test all three models
    all_results = {}

    for model_key in ["A", "B", "C"]:
        result = await test_model(model_key, candidates, output_dir)
        all_results[model_key] = result

    # Analyze quality for each model
    print(f"\n{'='*80}")
    print("QUALITY ANALYSIS")
    print(f"{'='*80}\n")

    comparison = {}

    for model_key, result in all_results.items():
        quality = await analyze_quality(result)
        comparison[model_key] = {
            "model_info": result['model_info'],
            "success_rate": result['success_rate'],
            "quality_metrics": quality
        }

        print(f"MODEL {model_key}: {result['model_info']['name']}")
        print(f"  Cost: ${result['model_info']['cost_per_1m']}/1M tokens")
        print(f"  Success Rate: {result['success_rate']*100:.1f}%")
        print(f"  Avg Explicit Skills: {quality['avg_explicit_skills']:.1f}")
        print(f"  Avg Inferred Skills: {quality['avg_inferred_skills']:.1f}")
        print(f"  Avg Confidence: {quality['avg_confidence']:.1f}%")
        print(f"  Skill Diversity: {quality['skill_diversity']} unique skills")
        print(f"  Total Skills: {quality['total_skills_extracted']}")
        print()

    # Cost estimate for 29K candidates
    print(f"\n{'='*80}")
    print("COST ESTIMATE FOR 29,000 CANDIDATES")
    print(f"{'='*80}\n")

    tokens_per_candidate = 6000
    total_tokens = 29000 * tokens_per_candidate / 1_000_000  # Convert to millions

    for model_key, data in comparison.items():
        cost = total_tokens * data['model_info']['cost_per_1m']
        print(f"Model {model_key}: ${cost:.2f}")

    # Save comparison report
    comparison_file = output_dir / "model_comparison_summary.json"
    with open(comparison_file, 'w', encoding='utf-8') as f:
        json.dump(clean_for_json({
            "test_timestamp": datetime.now().isoformat(),
            "test_size": len(candidates),
            "comparison": comparison,
            "cost_estimates_29k": {
                model_key: total_tokens * data['model_info']['cost_per_1m']
                for model_key, data in comparison.items()
            }
        }), f, indent=2)

    print(f"\n📊 Comparison report saved to: {comparison_file}")
    print(f"\n🎯 RECOMMENDATION WILL BE BASED ON:")
    print(f"  1. Quality metrics (explicit + inferred skills, confidence)")
    print(f"  2. Cost for 29K candidates")
    print(f"  3. Success rate")

if __name__ == "__main__":
    asyncio.run(main())
