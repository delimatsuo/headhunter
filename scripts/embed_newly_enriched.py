#!/usr/bin/env python3
"""
Embed Newly Enriched Candidates (Phase 1 Results)
==================================================
Generate embeddings for the 10,992 candidates enriched on 2025-10-27.

Filters candidates by processing_metadata.timestamp to only embed those
enriched today, avoiding re-processing the 17,969 already embedded in Phase 2.
"""

import asyncio
import aiohttp
import json
import os
import sys
import subprocess
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from google.cloud import firestore
from google.auth import default as get_default_credentials

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
        print(f"ERROR: Failed to get auth token: {e.stderr}")
        sys.exit(1)


def build_searchable_profile(candidate: Dict[str, Any]) -> str:
    """
    Builds a searchable profile from enriched candidate data.
    Works with Python enrichment schema (intelligent_analysis structure)
    """
    parts: List[str] = []

    def get_field(path: str) -> Optional[Any]:
        """Navigate nested dict path like 'a.b.c'"""
        keys = path.split('.')
        current = candidate
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current

    def get_array(path: str) -> List[str]:
        """Get array field and ensure it's a list of strings"""
        value = get_field(path)
        if isinstance(value, list):
            return [str(item) for item in value if isinstance(item, str)]
        return []

    # 1. Technical Skills (HIGHEST PRIORITY)
    explicit_skills = get_array('explicit_skills')
    intel_explicit = get_field('intelligent_analysis.explicit_skills')
    if isinstance(intel_explicit, dict):
        tech_skills = intel_explicit.get('technical_skills', [])
        if isinstance(tech_skills, list):
            explicit_skills.extend([str(s) for s in tech_skills if isinstance(s, str)])

    inferred_high = get_array('inferred_skills_high_confidence')
    primary_expertise = get_array('primary_expertise')

    # Combine all skills
    all_skills = list(set(explicit_skills + inferred_high + primary_expertise))
    if all_skills:
        parts.append(f"Technical Skills: {', '.join(all_skills[:15])}")

    # 2. Seniority Level
    current_level = get_field('current_level') or get_field('intelligent_analysis.career_trajectory_analysis.current_level')
    if current_level:
        parts.append(f"Seniority: {current_level}")

    # 3. Overall Rating
    rating = get_field('overall_rating') or get_field('intelligent_analysis.recruiter_insights.overall_rating')
    if rating:
        parts.append(f"Rating: {rating}")

    # 4. Core Competencies
    intel_comp = get_field('intelligent_analysis.role_based_competencies')
    if isinstance(intel_comp, dict):
        competencies = []
        for role, skills in intel_comp.items():
            if isinstance(skills, list):
                competencies.extend([str(s) for s in skills[:3] if isinstance(s, str)])
        if competencies:
            parts.append(f"Core Competencies: {', '.join(competencies[:10])}")

    # 5. Search Keywords
    keywords = get_field('search_keywords')
    if keywords:
        parts.append(f"Keywords: {keywords}")

    # 6. Market Positioning
    market_pos = get_field('intelligent_analysis.market_positioning')
    if isinstance(market_pos, str):
        parts.append(f"Market Position: {market_pos}")

    # 7. Domain Expertise
    composite = get_field('intelligent_analysis.composite_skill_profile')
    if isinstance(composite, dict):
        domain = composite.get('domain_specialization')
        if domain:
            parts.append(f"Domain: {domain}")

    # 8. Recruiter Insights
    rec_insights = get_field('intelligent_analysis.recruiter_insights')
    if isinstance(rec_insights, dict):
        recommendation = rec_insights.get('recommendation')
        if recommendation:
            parts.append(f"Recommendation: {recommendation}")

    # 9. Career Trajectory
    career_traj = get_field('intelligent_analysis.career_trajectory_analysis')
    if isinstance(career_traj, dict):
        trajectory_type = career_traj.get('trajectory_type')
        if trajectory_type:
            parts.append(f"Career Path: {trajectory_type}")

    return '\n'.join(parts) if parts else ""


async def embed_batch(session: aiohttp.ClientSession, batch: List[Tuple[str, Dict[str, Any]]], 
                     embed_url: str, tenant_id: str, api_key: str) -> List[Tuple[str, bool, Optional[str]]]:
    """Generate embeddings for a batch of candidates"""
    results = []
    
    for candidate_id, candidate_data in batch:
        try:
            # Build searchable profile
            searchable_profile = build_searchable_profile(candidate_data)
            
            if not searchable_profile:
                results.append((candidate_id, False, "No searchable profile could be built"))
                continue
            
            # Prepare metadata (convert Firestore DatetimeWithNanoseconds to ISO string)
            enriched_at = candidate_data.get('processing_metadata', {}).get('timestamp')
            enriched_at_str = None
            if enriched_at:
                try:
                    # Handle Firestore DatetimeWithNanoseconds objects
                    if hasattr(enriched_at, 'timestamp'):
                        enriched_at_str = datetime.fromtimestamp(enriched_at.timestamp(), tz=timezone.utc).isoformat()
                    elif isinstance(enriched_at, str):
                        enriched_at_str = enriched_at
                    elif hasattr(enriched_at, 'isoformat'):
                        enriched_at_str = enriched_at.isoformat()
                    else:
                        enriched_at_str = str(enriched_at)
                except Exception as e:
                    # Fallback: just use current time if conversion fails
                    enriched_at_str = datetime.now(timezone.utc).isoformat()

            # Ensure enriched_at_str is actually a string or None (not a Firestore object)
            if enriched_at_str is not None and not isinstance(enriched_at_str, str):
                enriched_at_str = datetime.now(timezone.utc).isoformat()

            # Call embedding service - use plain candidate_id to match profiles table
            payload = {
                "entityId": candidate_id,  # NO tenant prefix - must match candidate_profiles.candidate_id
                "text": searchable_profile,
                "metadata": {
                    "source": "phase1_new_enrichment",
                    "modelVersion": "enriched-v1",
                    "promptVersion": "structured-profile-v1",
                    "enriched_at": enriched_at_str
                }
            }

            headers = {
                "Content-Type": "application/json",
                "X-Tenant-ID": tenant_id,
                "Authorization": f"Bearer {api_key}"
            }
            
            async with session.post(f"{embed_url}/v1/embeddings/upsert", json=payload, headers=headers) as response:
                if response.status == 200:
                    results.append((candidate_id, True, None))
                else:
                    error_text = await response.text()
                    results.append((candidate_id, False, f"HTTP {response.status}: {error_text[:100]}"))
                    
        except Exception as e:
            results.append((candidate_id, False, str(e)[:100]))
    
    return results


async def main():
    """Main embedding function"""
    tenant_id = os.getenv("TENANT_ID", "tenant-alpha")
    embed_url = os.getenv("EMBED_SERVICE_URL", "https://hh-embed-svc-production-akcoqbr7sa-uc.a.run.app")
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "headhunter-ai-0088")
    
    # Filter date (only candidates enriched on or after this date)
    filter_date_str = "2025-10-27"
    filter_date = datetime.fromisoformat(filter_date_str).replace(tzinfo=timezone.utc)

    # Get Google Cloud identity token for Cloud Run authentication
    print("🔑 Getting authentication token...")
    api_key_env = get_auth_token()
    print("✅ Authentication token acquired\n")

    # Initialize Firestore
    credentials, _ = get_default_credentials()
    db = firestore.Client(project=project_id, credentials=credentials)

    # Query enriched candidates
    print(f"📊 Fetching newly enriched candidates from Firestore (enriched >= {filter_date_str})...")
    candidates_ref = db.collection(f"tenants/{tenant_id}/candidates")

    # Get all candidates and filter by timestamp
    all_docs = candidates_ref.stream()
    candidates = []
    skipped_old = 0

    for doc in all_docs:
        data = doc.to_dict()

        # Check if enriched
        if not ('intelligent_analysis' in data or 'technical_assessment' in data):
            continue

        # Filter by processing timestamp
        timestamp_obj = data.get('processing_metadata', {}).get('timestamp')
        if timestamp_obj:
            timestamp_dt = None
            # Convert to datetime if it's a string, otherwise use as-is
            if isinstance(timestamp_obj, str):
                try:
                    timestamp_dt = datetime.fromisoformat(timestamp_obj.replace('Z', '+00:00'))
                    # Ensure timezone-aware
                    if timestamp_dt.tzinfo is None:
                        timestamp_dt = timestamp_dt.replace(tzinfo=timezone.utc)
                except:
                    timestamp_dt = None
            else:
                # It's already a datetime object from Firestore
                timestamp_dt = timestamp_obj
                # Make timezone-aware if it's naive
                if timestamp_dt and timestamp_dt.tzinfo is None:
                    timestamp_dt = timestamp_dt.replace(tzinfo=timezone.utc)

            if timestamp_dt and timestamp_dt >= filter_date:
                candidates.append((doc.id, data))
            else:
                skipped_old += 1
        else:
            skipped_old += 1
    
    print(f"✅ Found {len(candidates)} newly enriched candidates")
    print(f"⏭️  Skipped {skipped_old} candidates (already embedded in Phase 2)\n")
    
    if not candidates:
        print("❌ No new candidates to embed")
        return
    
    # Process in batches
    batch_size = 10
    total = len(candidates)
    success_count = 0
    failed_count = 0
    failed_ids = []
    
    start_time = datetime.now()
    
    print(f"🚀 Starting embedding generation for {total} candidates")
    print(f"   Batch size: {batch_size}")
    print(f"   Target: {embed_url}\n")
    
    async with aiohttp.ClientSession() as session:
        for i in range(0, total, batch_size):
            batch = candidates[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total + batch_size - 1) // batch_size
            
            results = await embed_batch(session, batch, embed_url, tenant_id, api_key_env)
            
            # Process results
            for candidate_id, success, error in results:
                if success:
                    success_count += 1
                    print(f"  ✓ {candidate_id}")
                else:
                    failed_count += 1
                    failed_ids.append((candidate_id, error))
                    print(f"  ✗ {candidate_id}: {error}")
            
            # Progress update
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = (success_count + failed_count) / elapsed if elapsed > 0 else 0
            remaining = total - (success_count + failed_count)
            eta_seconds = remaining / rate if rate > 0 else 0
            
            print(f"\n📊 Batch {batch_num}/{total_batches} Complete")
            print(f"   Progress: {success_count + failed_count}/{total} ({(success_count + failed_count)/total*100:.1f}%)")
            print(f"   Success: {success_count} | Failed: {failed_count}")
            print(f"   Rate: {rate:.1f} candidates/sec")
            print(f"   ETA: {eta_seconds/60:.1f} minutes\n")
    
    # Final summary
    elapsed = (datetime.now() - start_time).total_seconds()
    
    print("="*80)
    print("✅ EMBEDDING GENERATION COMPLETE!")
    print("="*80)
    print(f"Total candidates: {total}")
    print(f"Successfully embedded: {success_count} ({success_count/total*100:.1f}%)")
    print(f"Failed: {failed_count}")
    print(f"Duration: {elapsed/60:.1f} minutes")
    print(f"Average rate: {(success_count + failed_count)/elapsed:.1f} candidates/sec")
    
    if failed_ids:
        print(f"\n❌ Failed candidate IDs ({len(failed_ids)}):")
        for cid, error in failed_ids[:20]:  # Show first 20
            print(f"   {cid}: {error}")
        if len(failed_ids) > 20:
            print(f"   ... and {len(failed_ids) - 20} more")
    
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
