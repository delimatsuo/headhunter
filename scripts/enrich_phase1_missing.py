#!/usr/bin/env python3
"""
Phase 1: Enrich Missing 11,173 Candidates
==========================================
Streamlined script to enrich the candidates missing from Phase 2.
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
from google.cloud import firestore

# Configuration
INPUT_FILE = Path("data/enriched/missing_candidates.json")
OUTPUT_FILE = Path("data/enriched/newly_enriched.json")
PROGRESS_FILE = Path("data/enriched/phase1_progress.json")
CHECKPOINT_FREQ = 50  # Save every 50 candidates
BATCH_SIZE = 50  # Process in batches
CONCURRENCY = 20  # Parallel requests

async def main():
    """Process missing candidates"""

    # Load API key
    api_key = os.getenv('TOGETHER_API_KEY')
    if not api_key:
        print("❌ TOGETHER_API_KEY not set!")
        sys.exit(1)

    # Load missing candidates
    print(f"📂 Loading {INPUT_FILE}...")
    with open(INPUT_FILE, 'r') as f:
        candidates = json.load(f)

    print(f"✅ Loaded {len(candidates):,} candidates")

    # Load progress if exists
    start_idx = 0
    enriched_results = []
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            progress = json.load(f)
            start_idx = progress.get('last_index', 0)
            print(f"📌 Resuming from index {start_idx}")

    # Initialize processor with context manager
    print("🔧 Initializing processor...")
    async with IntelligentSkillProcessor(api_key=api_key) as processor:
        # Get Firestore client
        db = firestore.Client()

        # Process candidates
        total = len(candidates)
        success_count = 0
        fail_count = 0
        start_time = datetime.now()

        for i in range(start_idx, total, BATCH_SIZE):
            batch = candidates[i:i+BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

            print(f"\n🔄 Processing batch {batch_num}/{total_batches} ({i+1}-{min(i+BATCH_SIZE, total)}/{total})")

            # Process batch in parallel (using correct method name)
            tasks = [processor.process_candidate(c) for c in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Collect results
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    fail_count += 1
                    print(f"  ✗ Failed {batch[idx]['id']}: {str(result)[:50]}")
                elif result:
                    success_count += 1
                    enriched_results.append(result)

                    # Upload to Firestore
                    try:
                        candidate_id = result.get('candidate_id')
                        db.collection(f'tenants/tenant-alpha/candidates').document(str(candidate_id)).set(result)
                    except Exception as e:
                        print(f"  ⚠️  Firestore upload failed for {candidate_id}: {str(e)[:50]}")
                else:
                    fail_count += 1

            # Save progress
            if (i + BATCH_SIZE) % (CHECKPOINT_FREQ * BATCH_SIZE) == 0:
                with open(OUTPUT_FILE, 'w') as f:
                    json.dump(enriched_results, f, indent=2)

                with open(PROGRESS_FILE, 'w') as f:
                    json.dump({
                        'last_index': i + BATCH_SIZE,
                        'success_count': success_count,
                        'fail_count': fail_count,
                        'timestamp': datetime.now().isoformat()
                    }, f)

                elapsed = (datetime.now() - start_time).total_seconds() / 3600
                rate = (success_count + fail_count) / elapsed if elapsed > 0 else 0
                remaining = total - (i + BATCH_SIZE)
                eta_hours = remaining / rate if rate > 0 else 0

                print(f"  💾 Checkpoint: {success_count} success, {fail_count} failed")
                print(f"  ⏱️  Rate: {rate:.1f} candidates/hour | ETA: {eta_hours:.1f} hours")

        # Final save
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(enriched_results, f, indent=2)

        elapsed = (datetime.now() - start_time).total_seconds() / 3600

        print(f"\n{'='*80}")
        print(f"✅ PHASE 1 ENRICHMENT COMPLETE!")
        print(f"{'='*80}")
        print(f"Success: {success_count:,}/{total:,} ({success_count/total*100:.1f}%)")
        print(f"Failed: {fail_count:,}")
        print(f"Total time: {elapsed:.2f} hours")
        print(f"Output: {OUTPUT_FILE}")
        print(f"{'='*80}")

if __name__ == "__main__":
    asyncio.run(main())
