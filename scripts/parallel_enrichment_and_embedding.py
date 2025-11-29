#!/usr/bin/env python3
"""
Parallel Enrichment and Embedding Fix
======================================

This script performs two critical tasks in parallel:
1. Re-embed 17,969 enriched candidates using enriched data (not raw data)
2. Enrich and embed 11,173 candidates missing enrichment

Usage:
    python3 scripts/parallel_enrichment_and_embedding.py --task reembed
    python3 scripts/parallel_enrichment_and_embedding.py --task enrich
    python3 scripts/parallel_enrichment_and_embedding.py --task both
"""

import asyncio
import aiohttp
import json
import argparse
import sys
import os
import subprocess
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

# Configuration
EMBED_SVC_URL = "https://hh-embed-svc-production-akcoqbr7sa-uc.a.run.app"
ENRICH_SVC_URL = "https://hh-enrich-svc-production-akcoqbr7sa-uc.a.run.app"
TENANT_ID = "tenant-alpha"
BATCH_SIZE = 15  # Process 15 candidates at a time
MAX_RETRIES = 3
TIMEOUT = 60  # seconds

# File paths
ENRICHED_FILE = Path("data/enriched/enriched_candidates_full.json")
MISSING_FILE = Path("/tmp/missing_enrichment_candidates.json")
OUTPUT_DIR = Path("data/enriched")


def get_auth_token() -> str:
    """Get Google Cloud identity token for authenticating to Cloud Run services"""
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-identity-token"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to get auth token: {e.stderr}")
        sys.exit(1)


def get_auth_headers(token: str) -> Dict[str, str]:
    """Build authentication headers for API requests"""
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": TENANT_ID,
        "Content-Type": "application/json"
    }


class ProgressTracker:
    """Track and display progress of parallel processing"""

    def __init__(self, total: int, task_name: str):
        self.total = total
        self.task_name = task_name
        self.completed = 0
        self.failed = 0
        self.start_time = datetime.now()

    def update(self, success: bool = True):
        if success:
            self.completed += 1
        else:
            self.failed += 1

        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = self.completed / elapsed if elapsed > 0 else 0
        remaining = (self.total - self.completed - self.failed) / rate if rate > 0 else 0

        print(f"\r{self.task_name}: {self.completed}/{self.total} "
              f"({self.failed} failed) | "
              f"Rate: {rate:.1f}/s | "
              f"ETA: {remaining/60:.1f}m", end="", flush=True)

    def finish(self):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        print(f"\n\n✅ {self.task_name} Complete!")
        print(f"   Total: {self.total}")
        print(f"   Successful: {self.completed}")
        print(f"   Failed: {self.failed}")
        print(f"   Duration: {elapsed/60:.1f} minutes")


def build_searchable_profile(candidate: Dict[str, Any]) -> str:
    """
    Build searchable profile from enriched candidate data.
    Mirrors the implementation in reembed_enriched_candidates.py
    """
    parts: List[str] = []

    # Helper to safely get nested values
    def get_string(path: str) -> str:
        keys = path.split('.')
        value = candidate.get('intelligent_analysis', {})
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, '')
            else:
                return ''
        return str(value) if value else ''

    def get_array(path: str) -> List[str]:
        keys = path.split('.')
        value = candidate.get('intelligent_analysis', {})
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, [])
            else:
                return []
        return value if isinstance(value, list) else []

    # 1. Technical Skills (HIGHEST PRIORITY)
    explicit_skills = get_array('explicit_skills')
    inferred_skills = get_array('inferred_skills')
    all_skills = list(set(explicit_skills + inferred_skills))
    if all_skills:
        parts.append(f"Technical Skills: {', '.join(all_skills[:20])}")

    # 2. Current Role and Level
    current_level = get_string('career_trajectory_analysis.current_level')
    if current_level:
        parts.append(f"Level: {current_level}")

    years_exp = get_string('career_trajectory_analysis.years_experience')
    if years_exp:
        parts.append(f"Experience: {years_exp} years")

    # 3. Market Positioning
    market_segment = get_string('market_positioning.target_market_segment')
    if market_segment:
        parts.append(f"Market Segment: {market_segment}")

    # 4. Company Context
    company_context = get_array('company_context_skills')
    if company_context:
        parts.append(f"Company Skills: {', '.join(company_context[:10])}")

    # 5. Role Competencies
    role_comps = get_array('role_based_competencies')
    if role_comps:
        parts.append(f"Role Competencies: {', '.join(role_comps[:10])}")

    # 6. Recruiter Insights
    insights = get_string('recruiter_insights.key_strengths')
    if insights:
        parts.append(f"Strengths: {insights}")

    ideal_roles = get_array('recruiter_insights.ideal_roles')
    if ideal_roles:
        parts.append(f"Ideal Roles: {', '.join(ideal_roles[:5])}")

    return '\n'.join(parts)


async def reembed_candidate(
    session: aiohttp.ClientSession,
    candidate: Dict[str, Any],
    progress: ProgressTracker,
    auth_headers: Dict[str, str]
) -> Optional[str]:
    """Re-embed a single enriched candidate with corrected data"""

    candidate_id = candidate.get('candidate_id')
    if not candidate_id:
        progress.update(success=False)
        return None

    try:
        # Build enriched searchable profile
        searchable_text = build_searchable_profile(candidate)

        if not searchable_text:
            print(f"\n⚠️  No searchable text for candidate {candidate_id}")
            progress.update(success=False)
            return None

        # Call hh-embed-svc to update embedding
        payload = {
            "entityId": str(candidate_id),
            "text": searchable_text,
            "metadata": {
                "candidate_id": str(candidate_id),
                "name": candidate.get('name', ''),
                "reembedded_at": datetime.now().isoformat(),
                "source": "enriched_data"
            }
        }

        async with session.post(
            f"{EMBED_SVC_URL}/v1/embeddings/upsert",
            json=payload,
            headers=auth_headers,
            timeout=aiohttp.ClientTimeout(total=TIMEOUT)
        ) as resp:
            if resp.status == 200:
                progress.update(success=True)
                return candidate_id
            else:
                error_text = await resp.text()
                print(f"\n⚠️  Embed failed for {candidate_id}: {resp.status} - {error_text[:100]}")
                progress.update(success=False)
                return None

    except asyncio.TimeoutError:
        print(f"\n⚠️  Timeout re-embedding candidate {candidate_id}")
        progress.update(success=False)
        return None
    except Exception as e:
        print(f"\n⚠️  Error re-embedding candidate {candidate_id}: {str(e)[:100]}")
        progress.update(success=False)
        return None


async def enrich_and_embed_candidate(
    session: aiohttp.ClientSession,
    candidate: Dict[str, Any],
    progress: ProgressTracker,
    auth_headers: Dict[str, str]
) -> Optional[str]:
    """Enrich and embed a single candidate"""

    candidate_id = candidate.get('id')
    if not candidate_id:
        progress.update(success=False)
        return None

    try:
        # Queue enrichment job
        enrich_payload = {
            "candidateDocumentId": str(candidate_id),
            "correlationId": f"parallel-enrich-{candidate_id}"
        }

        async with session.post(
            f"{ENRICH_SVC_URL}/api/enrich/queue",
            json=enrich_payload,
            headers=auth_headers,
            timeout=aiohttp.ClientTimeout(total=TIMEOUT)
        ) as resp:
            if resp.status in [200, 202]:
                progress.update(success=True)
                return candidate_id
            else:
                error_text = await resp.text()
                print(f"\n⚠️  Enrich failed for {candidate_id}: {resp.status} - {error_text[:100]}")
                progress.update(success=False)
                return None

    except asyncio.TimeoutError:
        print(f"\n⚠️  Timeout enriching candidate {candidate_id}")
        progress.update(success=False)
        return None
    except Exception as e:
        print(f"\n⚠️  Error enriching candidate {candidate_id}: {str(e)[:100]}")
        progress.update(success=False)
        return None


async def process_batch(
    session: aiohttp.ClientSession,
    batch: List[Dict[str, Any]],
    progress: ProgressTracker,
    task_type: str,
    auth_headers: Dict[str, str]
) -> List[str]:
    """Process a batch of candidates in parallel"""

    if task_type == "reembed":
        tasks = [reembed_candidate(session, c, progress, auth_headers) for c in batch]
    else:  # enrich
        tasks = [enrich_and_embed_candidate(session, c, progress, auth_headers) for c in batch]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, str)]


async def run_reembedding(enriched_candidates: List[Dict[str, Any]], auth_token: str):
    """Re-embed all enriched candidates with corrected data"""

    print(f"\n{'='*70}")
    print(f"RE-EMBEDDING {len(enriched_candidates)} ENRICHED CANDIDATES")
    print(f"{'='*70}\n")

    auth_headers = get_auth_headers(auth_token)
    progress = ProgressTracker(len(enriched_candidates), "Re-embedding")
    successful_ids = []

    async with aiohttp.ClientSession() as session:
        # Process in batches
        for i in range(0, len(enriched_candidates), BATCH_SIZE):
            batch = enriched_candidates[i:i + BATCH_SIZE]
            batch_results = await process_batch(session, batch, progress, "reembed", auth_headers)
            successful_ids.extend(batch_results)

            # Small delay between batches to avoid overwhelming the service
            await asyncio.sleep(0.5)

    progress.finish()

    # Save results
    output_file = OUTPUT_DIR / f"reembedding_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "total": len(enriched_candidates),
            "successful": len(successful_ids),
            "failed": len(enriched_candidates) - len(successful_ids),
            "successful_ids": successful_ids
        }, f, indent=2)

    print(f"\n📄 Results saved to: {output_file}")


async def run_enrichment(missing_candidates: List[Dict[str, Any]], auth_token: str):
    """Enrich all missing candidates"""

    print(f"\n{'='*70}")
    print(f"ENRICHING {len(missing_candidates)} MISSING CANDIDATES")
    print(f"{'='*70}\n")

    auth_headers = get_auth_headers(auth_token)
    progress = ProgressTracker(len(missing_candidates), "Enriching")
    successful_ids = []

    async with aiohttp.ClientSession() as session:
        # Process in batches
        for i in range(0, len(missing_candidates), BATCH_SIZE):
            batch = missing_candidates[i:i + BATCH_SIZE]
            batch_results = await process_batch(session, batch, progress, "enrich", auth_headers)
            successful_ids.extend(batch_results)

            # Small delay between batches
            await asyncio.sleep(0.5)

    progress.finish()

    # Save results
    output_file = OUTPUT_DIR / f"enrichment_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "total": len(missing_candidates),
            "successful": len(successful_ids),
            "failed": len(missing_candidates) - len(successful_ids),
            "successful_ids": successful_ids
        }, f, indent=2)

    print(f"\n📄 Results saved to: {output_file}")


async def run_both(auth_token: str):
    """Run both reembedding and enrichment in parallel"""

    print(f"\n{'='*70}")
    print(f"PARALLEL PROCESSING: RE-EMBEDDING + ENRICHMENT")
    print(f"{'='*70}\n")

    # Load data
    with open(ENRICHED_FILE, 'r') as f:
        enriched = json.load(f)

    with open(MISSING_FILE, 'r') as f:
        missing = json.load(f)

    print(f"📊 Loaded {len(enriched)} enriched candidates")
    print(f"📊 Loaded {len(missing)} missing candidates\n")

    # Run both tasks concurrently
    await asyncio.gather(
        run_reembedding(enriched, auth_token),
        run_enrichment(missing, auth_token)
    )


def main():
    global BATCH_SIZE

    parser = argparse.ArgumentParser(description="Parallel enrichment and embedding fix")
    parser.add_argument(
        "--task",
        choices=["reembed", "enrich", "both"],
        default="both",
        help="Task to run: reembed (fix embeddings), enrich (missing candidates), or both"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"Batch size for parallel processing (default: {BATCH_SIZE})"
    )

    args = parser.parse_args()
    BATCH_SIZE = args.batch_size

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Get authentication token
    print("🔑 Getting authentication token...")
    auth_token = get_auth_token()
    print("✅ Authentication token acquired\n")

    # Run selected task
    if args.task == "reembed":
        print(f"Loading enriched candidates from {ENRICHED_FILE}...")
        with open(ENRICHED_FILE, 'r') as f:
            enriched = json.load(f)
        asyncio.run(run_reembedding(enriched, auth_token))

    elif args.task == "enrich":
        print(f"Loading missing candidates from {MISSING_FILE}...")
        with open(MISSING_FILE, 'r') as f:
            missing = json.load(f)
        asyncio.run(run_enrichment(missing, auth_token))

    else:  # both
        asyncio.run(run_both(auth_token))


if __name__ == "__main__":
    main()
