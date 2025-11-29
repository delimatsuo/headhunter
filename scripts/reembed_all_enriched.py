#!/usr/bin/env python3
"""
Re-embed All Enriched Candidates
==================================

This script re-embeds all 17,969 enriched candidates using their intelligent_analysis data.
It processes candidates in parallel batches for performance.

Usage:
    python3 scripts/reembed_all_enriched.py

Progress is saved incrementally, so the script can be interrupted and resumed.
"""

import json
import subprocess
import http.client
import asyncio
import aiohttp
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path

# Configuration
EMBED_SVC_URL = "https://hh-embed-svc-production-akcoqbr7sa-uc.a.run.app"
TENANT_ID = "tenant-alpha"
BATCH_SIZE = 20  # Process 20 candidates concurrently
MAX_RETRIES = 3
TIMEOUT = 30  # seconds per request

# File paths
INPUT_FILE = Path("data/enriched/enriched_candidates_full.json")
PROGRESS_FILE = Path("data/enriched/reembed_progress.json")
FAILED_FILE = Path("data/enriched/reembed_failed.json")

def get_auth_token() -> str:
    """Get Google Cloud identity token"""
    result = subprocess.run(
        ["gcloud", "auth", "print-identity-token"],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()

def build_searchable_profile(candidate: Dict[str, Any]) -> str:
    """Extract searchable text from enriched data"""
    parts: List[str] = []
    ia = candidate.get('intelligent_analysis', {})

    if not ia:
        return "No enriched data available"

    # Technical Skills
    explicit_skills_obj = ia.get('explicit_skills', {})
    explicit_skills_list = explicit_skills_obj.get('technical_skills', [])
    explicit_skill_names = [s.get('skill') for s in explicit_skills_list if s.get('skill')]

    inferred_skills_obj = ia.get('inferred_skills', {})
    inferred_skills_list = inferred_skills_obj.get('highly_probable_skills', [])
    inferred_skill_names = [s.get('skill') for s in inferred_skills_list if s.get('skill')]

    all_skills = list(set(explicit_skill_names + inferred_skill_names))
    if all_skills:
        parts.append(f"Technical Skills: {', '.join(all_skills[:30])}")

    # Career Trajectory
    ct = ia.get('career_trajectory_analysis', {})
    if ct.get('current_level'):
        parts.append(f"Career Level: {ct['current_level']}")
    if ct.get('years_experience'):
        parts.append(f"Experience: {ct['years_experience']} years")
    if ct.get('promotion_velocity'):
        parts.append(f"Promotion Pattern: {ct['promotion_velocity']}")

    # Market Positioning
    mp = ia.get('market_positioning', {})
    if mp.get('target_market_segment'):
        parts.append(f"Market Segment: {mp['target_market_segment']}")
    if mp.get('salary_range_estimate'):
        parts.append(f"Salary Range: {mp['salary_range_estimate']}")

    # Recruiter Insights
    ri = ia.get('recruiter_insights', {})
    if ri.get('one_line_pitch'):
        parts.append(f"Profile: {ri['one_line_pitch']}")
    if ri.get('placement_likelihood'):
        parts.append(f"Placement Potential: {ri['placement_likelihood']}")

    return '\n'.join(parts) if parts else "No enriched data available"

async def reembed_candidate(
    session: aiohttp.ClientSession,
    candidate: Dict[str, Any],
    token: str
) -> Dict[str, Any]:
    """Re-embed a single candidate"""
    candidate_id = str(candidate.get('candidate_id'))
    searchable_text = build_searchable_profile(candidate)

    payload = {
        "entityId": candidate_id,
        "text": searchable_text,
        "metadata": {
            "source": "enriched_analysis",
            "reembedding": True,
            "timestamp": datetime.now().isoformat()
        },
        "chunkType": "default"
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": TENANT_ID,
        "Content-Type": "application/json"
    }

    for attempt in range(MAX_RETRIES):
        try:
            async with session.post(
                f"{EMBED_SVC_URL}/v1/embeddings/upsert",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT)
            ) as response:
                data = await response.json()

                if response.status in [200, 201]:
                    return {
                        "candidate_id": candidate_id,
                        "status": "success",
                        "dimensions": data.get('dimensions'),
                        "vectorId": data.get('vectorId')
                    }
                else:
                    if attempt == MAX_RETRIES - 1:
                        return {
                            "candidate_id": candidate_id,
                            "status": "failed",
                            "error": f"HTTP {response.status}: {data}"
                        }
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                return {
                    "candidate_id": candidate_id,
                    "status": "failed",
                    "error": str(e)
                }
            await asyncio.sleep(2 ** attempt)

async def process_batch(
    session: aiohttp.ClientSession,
    batch: List[Dict[str, Any]],
    token: str
) -> List[Dict[str, Any]]:
    """Process a batch of candidates concurrently"""
    tasks = [reembed_candidate(session, candidate, token) for candidate in batch]
    return await asyncio.gather(*tasks)

async def main():
    """Main processing function"""
    print(f"🚀 Re-embedding Enriched Candidates")
    print(f"{'='*60}\n")

    # Load candidates
    print(f"📂 Loading candidates from {INPUT_FILE}...")
    with open(INPUT_FILE, 'r') as f:
        all_candidates = json.load(f)

    print(f"   Total candidates: {len(all_candidates)}")

    # Load progress if exists
    processed_ids = set()
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            progress = json.load(f)
            processed_ids = set(progress.get('processed', []))
        print(f"   Already processed: {len(processed_ids)}")

    # Filter to candidates that need processing
    candidates_to_process = [
        c for c in all_candidates
        if str(c.get('candidate_id')) not in processed_ids
    ]

    print(f"   Remaining to process: {len(candidates_to_process)}\n")

    if not candidates_to_process:
        print("✅ All candidates already processed!")
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

            # Small delay between batches
            await asyncio.sleep(0.5)

    # Final summary
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n{'='*60}")
    print(f"✅ Re-embedding Complete!")
    print(f"{'='*60}")
    print(f"   Total processed: {successful + failed}")
    print(f"   Successful: {successful}")
    print(f"   Failed: {failed}")
    print(f"   Duration: {elapsed/60:.1f} minutes")
    print(f"   Average rate: {(successful + failed) / elapsed:.1f} candidates/second")

    if failed > 0:
        print(f"\n⚠️  Failed candidates saved to: {FAILED_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
