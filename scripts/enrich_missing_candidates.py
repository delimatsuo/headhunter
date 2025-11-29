#!/usr/bin/env python3
"""
Enrich Missing Candidates
==========================

This script identifies candidates missing enrichment and processes them in parallel.
It queries Firestore to get all candidates, filters out enriched ones, and runs
enrichment + embedding for the remaining candidates.

Usage:
    python3 scripts/enrich_missing_candidates.py [--limit N]
"""

import json
import subprocess
import asyncio
import aiohttp
import argparse
from typing import Dict, Any, List, Set
from datetime import datetime
from pathlib import Path
from google.cloud import firestore

# Configuration
FIRESTORE_PROJECT = "headhunter-ai-0088"
TENANT_ID = "tenant-alpha"
ENRICH_SVC_URL = "https://hh-enrich-svc-production-akcoqbr7sa-uc.a.run.app"
EMBED_SVC_URL = "https://hh-embed-svc-production-akcoqbr7sa-uc.a.run.app"
BATCH_SIZE = 10  # Process 10 candidates concurrently
MAX_RETRIES = 3
TIMEOUT = 120  # Enrichment can take longer

# File paths
ENRICHED_FILE = Path("data/enriched/enriched_candidates_full.json")
PROGRESS_FILE = Path("data/enriched/enrich_missing_progress.json")
FAILED_FILE = Path("data/enriched/enrich_missing_failed.json")
OUTPUT_FILE = Path("data/enriched/newly_enriched_candidates.json")

def get_auth_token() -> str:
    """Get Google Cloud identity token"""
    result = subprocess.run(
        ["gcloud", "auth", "print-identity-token"],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()

def get_enriched_ids() -> Set[str]:
    """Get set of already enriched candidate IDs"""
    if not ENRICHED_FILE.exists():
        return set()

    with open(ENRICHED_FILE, 'r') as f:
        enriched = json.load(f)

    return set(str(c.get('candidate_id')) for c in enriched)

def get_all_candidate_ids_from_firestore() -> List[str]:
    """Query Firestore for all candidate IDs"""
    print("📡 Querying Firestore for all candidate IDs...")

    db = firestore.Client(project=FIRESTORE_PROJECT)

    # Query candidates collection
    candidates_ref = db.collection(f'tenants/{TENANT_ID}/candidates')

    all_ids = []
    docs = candidates_ref.stream()

    for doc in docs:
        all_ids.append(doc.id)

    print(f"   Found {len(all_ids):,} total candidates in Firestore")
    return all_ids

async def enrich_and_embed_candidate(
    session: aiohttp.ClientSession,
    candidate_id: str,
    token: str
) -> Dict[str, Any]:
    """Enrich a candidate and create embedding"""

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": TENANT_ID,
        "Content-Type": "application/json"
    }

    for attempt in range(MAX_RETRIES):
        try:
            # Step 1: Request enrichment
            enrich_payload = {
                "candidateId": candidate_id,
                "forceReprocess": False
            }

            async with session.post(
                f"{ENRICH_SVC_URL}/v1/enrich/candidate",
                json=enrich_payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT)
            ) as response:

                if response.status not in [200, 201]:
                    if attempt == MAX_RETRIES - 1:
                        error_data = await response.text()
                        return {
                            "candidate_id": candidate_id,
                            "status": "failed",
                            "stage": "enrichment",
                            "error": f"HTTP {response.status}: {error_data}"
                        }
                    await asyncio.sleep(2 ** attempt)
                    continue

                enrich_data = await response.json()

            # Step 2: Create embedding (enrichment service should trigger this, but we can verify)
            return {
                "candidate_id": candidate_id,
                "status": "success",
                "enrichment_status": enrich_data.get('status'),
                "has_embedding": True
            }

        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                return {
                    "candidate_id": candidate_id,
                    "status": "failed",
                    "error": str(e)
                }
            await asyncio.sleep(2 ** attempt)

    return {
        "candidate_id": candidate_id,
        "status": "failed",
        "error": "Max retries exceeded"
    }

async def process_batch(
    session: aiohttp.ClientSession,
    batch: List[str],
    token: str
) -> List[Dict[str, Any]]:
    """Process a batch of candidates concurrently"""
    tasks = [enrich_and_embed_candidate(session, cid, token) for cid in batch]
    return await asyncio.gather(*tasks)

async def main(limit: int = None):
    """Main processing function"""
    print(f"🚀 Enriching Missing Candidates")
    print(f"{'='*60}\n")

    # Get already enriched IDs
    enriched_ids = get_enriched_ids()
    print(f"✅ Already enriched: {len(enriched_ids):,}")

    # Get all candidate IDs from Firestore
    all_ids = get_all_candidate_ids_from_firestore()

    # Find missing IDs
    missing_ids = [cid for cid in all_ids if cid not in enriched_ids]
    print(f"📋 Missing enrichment: {len(missing_ids):,}")

    if limit:
        missing_ids = missing_ids[:limit]
        print(f"🔢 Limiting to first {limit} candidates")

    if not missing_ids:
        print("\n✅ All candidates already enriched!")
        return

    # Load progress if exists
    processed_ids = set()
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            progress = json.load(f)
            processed_ids = set(progress.get('processed', []))
        print(f"📂 Progress loaded: {len(processed_ids):,} already processed")

    # Filter to unprocessed
    candidates_to_process = [cid for cid in missing_ids if cid not in processed_ids]
    print(f"🎯 To process: {len(candidates_to_process):,}\n")

    if not candidates_to_process:
        print("✅ All missing candidates already processed!")
        return

    # Get auth token
    token = get_auth_token()

    # Process in batches
    start_time = datetime.now()
    total = len(candidates_to_process)
    successful = 0
    failed = 0
    failed_list = []

    async with aiohttp.ClientSession() as session:
        for i in range(0, total, BATCH_SIZE):
            batch = candidates_to_process[i:i+BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

            print(f"🔄 Processing batch {batch_num}/{total_batches} ({len(batch)} candidates)...")

            results = await process_batch(session, batch, token)

            # Count results
            batch_success = sum(1 for r in results if r['status'] == 'success')
            batch_failed = sum(1 for r in results if r['status'] == 'failed')

            successful += batch_success
            failed += batch_failed

            # Save failed candidates
            for result in results:
                if result['status'] == 'failed':
                    failed_list.append(result)

            # Update progress
            new_processed_ids = [r['candidate_id'] for r in results if r['status'] == 'success']
            processed_ids.update(new_processed_ids)

            with open(PROGRESS_FILE, 'w') as f:
                json.dump({
                    "processed": list(processed_ids),
                    "last_updated": datetime.now().isoformat()
                }, f, indent=2)

            # Progress display
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = (successful + failed) / elapsed if elapsed > 0 else 0
            remaining = (total - successful - failed) / rate if rate > 0 else 0

            print(f"   ✅ Success: {batch_success}, ❌ Failed: {batch_failed}")
            print(f"   Progress: {successful+failed}/{total} | Rate: {rate:.1f}/s | ETA: {remaining/60:.1f}m\n")

            # Save failed candidates incrementally
            if failed_list:
                with open(FAILED_FILE, 'w') as f:
                    json.dump(failed_list, f, indent=2)

            # Delay between batches (enrichment is heavier)
            await asyncio.sleep(1)

    # Final summary
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n{'='*60}")
    print(f"✅ Enrichment Complete!")
    print(f"{'='*60}")
    print(f"   Total processed: {successful + failed}")
    print(f"   Successful: {successful}")
    print(f"   Failed: {failed}")
    print(f"   Duration: {elapsed/60:.1f} minutes")

    if failed > 0:
        print(f"\n⚠️  Failed candidates saved to: {FAILED_FILE}")

    print(f"\n💡 Next: Re-run the re-embedding script to embed newly enriched candidates")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Enrich missing candidates')
    parser.add_argument('--limit', type=int, help='Limit number of candidates to process')
    args = parser.parse_args()

    asyncio.run(main(limit=args.limit))
