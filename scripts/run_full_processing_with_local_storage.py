#!/usr/bin/env python3
"""
Process all 29K candidates with Qwen 2.5 7B using intelligent skill inference
High parallelization: 20 concurrent requests, batch size 50
WITH LOCAL STORAGE BACKUP (saves to JSON + uploads to Firestore)
"""

import json
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.intelligent_skill_processor import IntelligentSkillProcessor
from dotenv import load_dotenv
from google.cloud import firestore

load_dotenv()

def clean_for_json(obj):
    """Remove Firestore Sentinel objects and other non-serializable types"""
    if obj is None:
        return None

    # Check for Firestore Sentinel objects by class name
    if hasattr(obj, '__class__') and 'Sentinel' in obj.__class__.__name__:
        return datetime.now().isoformat()

    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [clean_for_json(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()

    return obj

class ProcessorWithLocalStorage:
    """Wrapper to add local storage + better Firestore handling"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Local JSON storage
        self.local_file = output_dir / "enriched_candidates_full.json"
        self.enriched_data = []

        # Firestore client
        try:
            self.db = firestore.Client()
            self.use_firestore = True
            print("✅ Connected to Firestore")
        except Exception as e:
            print(f"⚠️ Firestore not available: {e}")
            self.use_firestore = False

        # Stats
        self.total_processed = 0
        self.firestore_uploaded = 0
        self.firestore_failed = 0

    async def save_batch_local(self, results: List[Dict[str, Any]]):
        """Save batch to local JSON file"""
        self.enriched_data.extend(results)

        # Clean data for JSON serialization
        clean_data = [clean_for_json(item) for item in self.enriched_data]

        # Write to file incrementally
        with open(self.local_file, 'w', encoding='utf-8') as f:
            json.dump(clean_data, f, indent=2, ensure_ascii=False)

        print(f"💾 Saved {len(self.enriched_data)} total to local file")

    async def upload_batch_to_firestore(self, results: List[Dict[str, Any]]):
        """Upload batch to Firestore with better error handling"""
        if not self.use_firestore or not results:
            return

        # Upload in smaller batches (Firestore has 500 writes/batch limit)
        batch_size = 100
        for i in range(0, len(results), batch_size):
            batch = results[i:i+batch_size]

            try:
                # Create Firestore batch
                fb = self.db.batch()

                for candidate in batch:
                    candidate_id = candidate.get('candidate_id')
                    if not candidate_id:
                        continue

                    doc_ref = self.db.collection('candidates').document(str(candidate_id))
                    fb.set(doc_ref, candidate, merge=True)

                # Commit batch
                fb.commit()
                self.firestore_uploaded += len(batch)
                print(f"☁️  Uploaded {len(batch)} to Firestore (total: {self.firestore_uploaded})")

                # Small delay to avoid rate limits
                await asyncio.sleep(0.5)

            except Exception as e:
                print(f"❌ Firestore upload error: {e}")
                self.firestore_failed += len(batch)
                # Continue processing even if Firestore fails
                continue

async def main():
    """Process all candidates with maximum parallelization + local storage"""

    # Paths
    input_file = Path("/Volumes/Extreme Pro/myprojects/headhunter/data/comprehensive_merged_candidates.json")
    output_dir = Path("/Volumes/Extreme Pro/myprojects/headhunter/data/enriched")
    output_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_file = output_dir / "processing_checkpoint.json"

    print("="*80)
    print("FULL CANDIDATE PROCESSING - Qwen 2.5 7B (WITH LOCAL STORAGE)")
    print("="*80)
    print(f"\nInput: {input_file}")
    print(f"Output: {output_dir}")
    print(f"\nConfiguration:")
    print(f"  Model: Qwen/Qwen2.5-7B-Instruct-Turbo")
    print(f"  Cost: $0.30/1M tokens")
    print(f"  Batch size: 50")
    print(f"  Concurrency: 20")
    print(f"  Local storage: YES (backup)")
    print(f"  Firestore upload: YES")
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

    # Initialize storage wrapper
    storage = ProcessorWithLocalStorage(output_dir)

    # Process in batches with high concurrency
    async with IntelligentSkillProcessor() as processor:
        processor.use_firestore = False  # Disable built-in Firestore (we handle it)

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

            # Separate successful from failed
            successful_results = []
            for r in results:
                if r and not isinstance(r, Exception):
                    successful_results.append(r)
                    processed += 1
                else:
                    failed += 1

            # Save to local file (incremental backup)
            if successful_results:
                await storage.save_batch_local(successful_results)

                # Upload to Firestore (best effort)
                await storage.upload_batch_to_firestore(successful_results)

            # Progress
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = processed / elapsed if elapsed > 0 else 0
            remaining = total - (batch_end)
            eta_seconds = remaining / rate if rate > 0 else 0

            print(f"\nProgress: {processed}/{total} successful ({100*processed/total:.1f}%)")
            print(f"Failed: {failed}")
            print(f"Firestore uploaded: {storage.firestore_uploaded}")
            print(f"Firestore failed: {storage.firestore_failed}")
            print(f"Rate: {rate:.1f} candidates/sec")
            print(f"ETA: {eta_seconds/3600:.1f} hours")

            # Save checkpoint
            with open(checkpoint_file, 'w') as f:
                json.dump({
                    'last_processed_index': batch_end - 1,
                    'total_processed': processed,
                    'total_failed': failed,
                    'firestore_uploaded': storage.firestore_uploaded,
                    'firestore_failed': storage.firestore_failed,
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
        print(f"Firestore uploaded: {storage.firestore_uploaded}")
        print(f"Firestore failed: {storage.firestore_failed}")
        print(f"Total time: {total_time/3600:.2f} hours")
        print(f"Average rate: {processed/total_time:.1f} candidates/sec")
        print(f"\n✅ All data saved to: {storage.local_file}")
        print(f"✅ Firestore upload: {storage.firestore_uploaded}/{processed} successful")

if __name__ == "__main__":
    asyncio.run(main())
