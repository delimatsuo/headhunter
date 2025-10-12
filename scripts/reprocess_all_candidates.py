#!/usr/bin/env python3
"""
Re-process all candidates through the enrichment pipeline.

This will trigger enrichment + embedding for all existing candidates,
which will use the new enriched profile embedding logic.
"""

import asyncio
import os
import sys
from typing import List, Dict, Any

import aiohttp
import asyncpg


async def fetch_candidate_ids(db_config: Dict[str, str]) -> List[str]:
    """Fetch all candidate IDs from PostgreSQL"""
    print("Connecting to PostgreSQL...")
    conn = await asyncpg.connect(
        host=db_config['host'],
        database=db_config['database'],
        user=db_config['user'],
        password=db_config['password']
    )

    tenant_id = db_config['tenant_id']
    print(f"Fetching candidates from {tenant_id}.candidates...")

    query = f"""
        SELECT id
        FROM {tenant_id}.candidates
        ORDER BY id
    """

    rows = await conn.fetch(query)
    await conn.close()

    candidate_ids = [str(row['id']) for row in rows]
    print(f"Found {len(candidate_ids)} candidates")

    return candidate_ids


async def submit_enrichment_job(
    session: aiohttp.ClientSession,
    enrich_url: str,
    tenant_id: str,
    candidate_id: str,
    api_key: str,
    async_mode: bool = True
) -> Dict[str, Any]:
    """Submit a single enrichment job"""
    payload = {
        "candidateId": candidate_id,
        "async": async_mode
    }

    headers = {
        "Content-Type": "application/json",
        "X-Tenant-ID": tenant_id,
        "x-api-key": api_key
    }

    try:
        async with session.post(
            f"{enrich_url}/v1/enrich/profile",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=5 if async_mode else 60)
        ) as resp:
            if resp.status in [200, 202]:
                result = await resp.json()
                job = result.get('job', {})
                job_id = job.get('jobId', 'unknown')
                status = job.get('status', 'unknown')
                return {
                    'success': True,
                    'candidate_id': candidate_id,
                    'job_id': job_id,
                    'status': status
                }
            else:
                error_text = await resp.text()
                return {
                    'success': False,
                    'candidate_id': candidate_id,
                    'error': f"HTTP {resp.status}: {error_text[:200]}"
                }
    except Exception as e:
        return {
            'success': False,
            'candidate_id': candidate_id,
            'error': str(e)
        }


async def main():
    """Main reprocessing function"""
    # Configuration from environment
    tenant_id = os.getenv("TENANT_ID", "tenant_alpha")
    enrich_url = os.getenv("ENRICH_SERVICE_URL", "https://hh-enrich-svc-production-1034162584026.us-central1.run.app")
    api_key = os.getenv("HH_API_KEY")

    db_config = {
        'host': os.getenv("DB_HOST", "/cloudsql/headhunter-ai-0088:us-central1:sql-hh-core"),
        'database': os.getenv("DB_NAME", "headhunter"),
        'user': os.getenv("DB_USER", "postgres"),
        'password': os.getenv("DB_PASSWORD"),
        'tenant_id': tenant_id
    }

    if not api_key:
        print("ERROR: HH_API_KEY environment variable not set")
        sys.exit(1)

    if not db_config['password']:
        print("ERROR: DB_PASSWORD environment variable not set")
        sys.exit(1)

    # Fetch all candidate IDs
    candidate_ids = await fetch_candidate_ids(db_config)

    if not candidate_ids:
        print("No candidates found. Nothing to do.")
        return

    # Submit enrichment jobs in batches
    batch_size = 10
    async_mode = True  # Use async jobs for speed

    success_count = 0
    fail_count = 0

    print(f"\n{'='*60}")
    print(f"Starting re-enrichment of {len(candidate_ids)} candidates...")
    print(f"Service: {enrich_url}")
    print(f"Tenant: {tenant_id}")
    print(f"Async mode: {async_mode}")
    print(f"{'='*60}\n")

    async with aiohttp.ClientSession() as session:
        for i in range(0, len(candidate_ids), batch_size):
            batch = candidate_ids[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(candidate_ids) + batch_size - 1) // batch_size

            print(f"Batch {batch_num}/{total_batches}: Submitting {len(batch)} jobs...")

            tasks = [
                submit_enrichment_job(session, enrich_url, tenant_id, cid, api_key, async_mode)
                for cid in batch
            ]

            results = await asyncio.gather(*tasks)

            # Count successes/failures
            batch_success = sum(1 for r in results if r['success'])
            batch_fail = len(results) - batch_success

            success_count += batch_success
            fail_count += batch_fail

            # Show results for this batch
            for result in results:
                if result['success']:
                    cid = result['candidate_id']
                    job_id = result['job_id']
                    status = result['status']
                    print(f"  ✓ {cid}: Job {job_id} ({status})")
                else:
                    cid = result['candidate_id']
                    error = result['error']
                    print(f"  ✗ {cid}: {error}")

            # Small delay between batches to avoid overwhelming the service
            if i + batch_size < len(candidate_ids):
                await asyncio.sleep(0.5)

    print(f"\n{'='*60}")
    print(f"Re-enrichment job submission complete!")
    print(f"Success: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"Total: {len(candidate_ids)}")
    print(f"{'='*60}")

    if async_mode:
        print("\nNOTE: Jobs are processing asynchronously.")
        print("Monitor logs to track progress:")
        print(f"  gcloud logging read 'resource.labels.service_name=hh-enrich-svc-production' --project=headhunter-ai-0088 --limit=50")


if __name__ == "__main__":
    asyncio.run(main())
