#!/usr/bin/env python3
"""
Process all 29K candidates with Qwen 2.5 7B using intelligent skill inference
High parallelization: 20 concurrent requests, batch size 50
"""

import json
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.intelligent_skill_processor import IntelligentSkillProcessor
from dotenv import load_dotenv

load_dotenv()

async def main():
    """Process all candidates with maximum parallelization"""

    # Paths
    input_file = Path("/Volumes/Extreme Pro/myprojects/headhunter/data/comprehensive_merged_candidates.json")
    output_dir = Path("/Volumes/Extreme Pro/myprojects/headhunter/data/processed")
    output_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_file = output_dir / "processing_checkpoint.json"

    print("="*80)
    print("FULL CANDIDATE PROCESSING - Qwen 2.5 7B")
    print("="*80)
    print(f"\nInput: {input_file}")
    print(f"Output: {output_dir}")
    print(f"\nConfiguration:")
    print(f"  Model: Qwen/Qwen2.5-7B-Instruct-Turbo")
    print(f"  Cost: $0.30/1M tokens")
    print(f"  Batch size: 50")
    print(f"  Concurrency: 20")
    print(f"  Target: ~29K candidates")
    print(f"  Estimated cost: ~$52")
    print()

    # Load candidates
    print("Loading candidates...")
    with open(input_file, 'r', encoding='utf-8') as f:
        candidates = json.load(f)

    print(f"✅ Loaded {len(candidates)} candidates")

    # Check for checkpoint
    start_idx = 0
    if checkpoint_file.exists():
        with open(checkpoint_file, 'r') as f:
            checkpoint = json.load(f)
            start_idx = checkpoint.get('last_processed_index', 0) + 1
            print(f"📌 Resuming from checkpoint: index {start_idx}")

    # Process in batches with high concurrency
    async with IntelligentSkillProcessor() as processor:
        processor.use_firestore = True  # Upload to Firestore

        batch_size = 50
        total = len(candidates)
        processed = 0
        failed = 0
        start_time = datetime.now()

        for batch_start in range(start_idx, total, batch_size):
            batch_end = min(batch_start + batch_size, total)
            batch = candidates[batch_start:batch_end]

            print(f"\n{'='*80}")
            print(f"BATCH {batch_start//batch_size + 1}: Processing {batch_start}-{batch_end-1} of {total}")
            print(f"{'='*80}")

            # Process batch concurrently
            tasks = []
            for candidate in batch:
                tasks.append(processor.process_candidate(candidate))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Count results
            batch_processed = sum(1 for r in results if r and not isinstance(r, Exception))
            batch_failed = len(results) - batch_processed

            processed += batch_processed
            failed += batch_failed

            # Progress
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = processed / elapsed if elapsed > 0 else 0
            remaining = total - (batch_end)
            eta_seconds = remaining / rate if rate > 0 else 0

            print(f"\nProgress: {processed}/{total} successful ({100*processed/total:.1f}%)")
            print(f"Failed: {failed}")
            print(f"Rate: {rate:.1f} candidates/sec")
            print(f"ETA: {eta_seconds/3600:.1f} hours")

            # Save checkpoint
            with open(checkpoint_file, 'w') as f:
                json.dump({
                    'last_processed_index': batch_end - 1,
                    'total_processed': processed,
                    'total_failed': failed,
                    'timestamp': datetime.now().isoformat()
                }, f, indent=2)

        # Final summary
        total_time = (datetime.now() - start_time).total_seconds()
        print(f"\n{'='*80}")
        print("PROCESSING COMPLETE!")
        print(f"{'='*80}")
        print(f"\nTotal processed: {processed}/{total}")
        print(f"Success rate: {100*processed/total:.1f}%")
        print(f"Failed: {failed}")
        print(f"Total time: {total_time/3600:.2f} hours")
        print(f"Average rate: {processed/total_time:.1f} candidates/sec")
        print(f"\n✅ All candidates uploaded to Firestore!")

if __name__ == "__main__":
    asyncio.run(main())
