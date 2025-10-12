#!/usr/bin/env python3
"""
Phase 1 Test: Process 10 candidates with Together AI intelligent skill analysis
Validates output includes explicit_skills + inferred_skills with confidence scores
"""

import json
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.intelligent_skill_processor import IntelligentSkillProcessor
from dotenv import load_dotenv

# Load environment
load_dotenv()

async def main():
    """Phase 1: Test with 10 candidates"""

    # Input file (prepared test batch)
    INPUT_FILE = Path(__file__).parent / "test_batch_10_candidates.json"

    # Output file for results
    OUTPUT_FILE = Path(__file__).parent / "phase1_test_results.json"

    print("=" * 80)
    print("PHASE 1 TEST: Together AI Intelligent Skill Analysis")
    print("=" * 80)
    print(f"\n📂 Input: {INPUT_FILE}")
    print(f"💾 Output: {OUTPUT_FILE}")
    print(f"\n🧠 Using Together AI Qwen 2.5 32B Instruct for skill inference")
    print(f"📊 Expected output: explicit_skills + inferred_skills with confidence\n")

    # Load candidates
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        candidates = json.load(f)

    print(f"✅ Loaded {len(candidates)} candidates for testing")

    # Process with intelligent analysis
    async with IntelligentSkillProcessor() as processor:
        # Process batch WITHOUT uploading to Firestore (test mode)
        processor.use_firestore = False  # Disable Firestore for testing

        results = []
        for i, candidate in enumerate(candidates, 1):
            print(f"\n{'=' * 60}")
            print(f"Processing candidate {i}/{len(candidates)}: {candidate.get('name', 'Unknown')}")
            print(f"{'=' * 60}")

            result = await processor.process_candidate(candidate)

            if result:
                results.append(result)

                # Validate structure
                has_explicit = "explicit_skills" in result
                has_inferred = "inferred_skills_high_confidence" in result
                has_analysis = "intelligent_analysis" in result

                print(f"✅ Success!")
                print(f"   - Explicit skills: {has_explicit} ({len(result.get('explicit_skills', []))} skills)")
                print(f"   - Inferred skills (high confidence): {has_inferred} ({len(result.get('inferred_skills_high_confidence', []))} skills)")
                print(f"   - Intelligent analysis: {has_analysis}")

                # Show sample skills
                if has_explicit and result.get('explicit_skills'):
                    print(f"   - Sample explicit: {result['explicit_skills'][:3]}")
                if has_inferred and result.get('inferred_skills_high_confidence'):
                    print(f"   - Sample inferred: {result['inferred_skills_high_confidence'][:3]}")

                if has_analysis:
                    ia = result["intelligent_analysis"]

                    # Check for inferred skills with confidence
                    inferred = ia.get("inferred_skills", {})
                    hp = inferred.get("highly_probable_skills", [])
                    p = inferred.get("probable_skills", [])

                    print(f"\n   📊 Detailed analysis:")
                    print(f"      - Highly probable skills (>90%): {len(hp)}")
                    print(f"      - Probable skills (75-90%): {len(p)}")

                    # Sample output
                    if hp:
                        sample = hp[0]
                        print(f"\n   🔍 Sample highly probable skill:")
                        print(f"      Skill: {sample.get('skill', 'N/A')}")
                        print(f"      Confidence: {sample.get('confidence', 'N/A')}%")
                        evidence = sample.get('evidence', sample.get('reasoning', 'N/A'))
                        if evidence and evidence != 'N/A' and evidence is not None:
                            print(f"      Evidence: {str(evidence)[:100]}")
            else:
                print(f"❌ Failed to process")

        # Save results
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n{'=' * 80}")
        print(f"PHASE 1 TEST COMPLETE")
        print(f"{'=' * 80}")
        print(f"\n✅ Successfully processed: {len(results)}/{len(candidates)}")
        print(f"💾 Results saved to: {OUTPUT_FILE}")
        print(f"\n📊 Validation:")

        # Validate all results have required fields
        valid_count = 0
        for r in results:
            has_explicit = "explicit_skills" in r and isinstance(r["explicit_skills"], list)
            has_inferred = "inferred_skills_high_confidence" in r and isinstance(r["inferred_skills_high_confidence"], list)
            has_ia = "intelligent_analysis" in r and isinstance(r["intelligent_analysis"], dict)

            if has_explicit and has_inferred and has_ia:
                valid_count += 1

        print(f"   - Valid structure: {valid_count}/{len(results)} ({100*valid_count/len(results) if results else 0:.1f}%)")

        # Cost estimate
        avg_tokens = 6000  # Average tokens per candidate
        cost_per_token = 0.10 / 1_000_000
        total_cost = len(results) * avg_tokens * cost_per_token

        print(f"\n💰 Cost estimate: ${total_cost:.4f}")

        if valid_count == len(results):
            print(f"\n🎉 ALL TESTS PASSED - Ready for Phase 2")
        else:
            print(f"\n⚠️ Some results missing required fields - Review before Phase 2")

if __name__ == "__main__":
    asyncio.run(main())
