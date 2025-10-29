#!/usr/bin/env python3
"""
Re-embed all enriched candidates with structured profile data.

This script:
1. Reads all enriched candidates from Firestore
2. Builds searchable profiles from enriched fields (not raw resume text)
3. Calls hh-embed-svc to update embeddings in pgvector
"""

import asyncio
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

import aiohttp
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
    Updated to work with Python enrichment schema (intelligent_analysis structure)
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
        """Get array of strings from path"""
        value = get_field(path)
        if isinstance(value, list):
            return [str(v) for v in value if isinstance(v, str)]
        return []

    def get_string(path: str) -> Optional[str]:
        """Get string from path"""
        value = get_field(path)
        return str(value) if isinstance(value, str) else None

    # 1. Technical Skills (HIGHEST PRIORITY)
    # From intelligent_analysis.explicit_skills (dict with technical_skills list)
    explicit_skills = get_array('explicit_skills')  # Top-level
    intel_explicit = get_field('intelligent_analysis.explicit_skills')
    if isinstance(intel_explicit, dict):
        tech_skills = intel_explicit.get('technical_skills', [])
        if isinstance(tech_skills, list):
            explicit_skills.extend([str(s) for s in tech_skills if isinstance(s, str)])

    # Also get inferred high-confidence skills
    inferred_high = get_array('inferred_skills_high_confidence')

    # Get primary expertise
    primary_expertise = get_array('primary_expertise')

    # Combine all skills
    all_skills = list(set(explicit_skills + inferred_high + primary_expertise))
    if all_skills:
        parts.append(f"Technical Skills: {', '.join(all_skills[:15])}")

    # 2. Current Level / Seniority
    current_level = get_string('current_level')
    if current_level:
        parts.append(f"Seniority: {current_level}")

    # 3. Career Trajectory Analysis
    career_analysis = get_field('intelligent_analysis.career_trajectory_analysis')
    if isinstance(career_analysis, dict):
        progression = career_analysis.get('progression_speed')
        if progression:
            parts.append(f"Career Progression: {progression}")

    # 4. Market Positioning
    market_pos = get_string('intelligent_analysis.market_positioning')
    if market_pos:
        parts.append(f"Market Position: {market_pos}")

    # 5. Role-based Competencies
    role_comp = get_field('intelligent_analysis.role_based_competencies')
    if isinstance(role_comp, dict):
        roles = list(role_comp.keys())
        if roles:
            parts.append(f"Competencies: {', '.join(roles[:5])}")

    # 6. Recruiter Insights
    recruiter = get_field('intelligent_analysis.recruiter_insights')
    if isinstance(recruiter, dict):
        ideal_roles = recruiter.get('ideal_roles', [])
        if isinstance(ideal_roles, list):
            role_strings = [str(r) for r in ideal_roles if isinstance(r, str)]
            if role_strings:
                parts.append(f"Best Fit Roles: {', '.join(role_strings[:5])}")

        strengths = recruiter.get('key_strengths', [])
        if isinstance(strengths, list):
            strength_strings = [str(s) for s in strengths if isinstance(s, str)]
            if strength_strings:
                parts.append(f"Strengths: {', '.join(strength_strings[:5])}")

    # 7. Overall Rating and Recommendation
    rating = get_string('overall_rating')
    if rating:
        parts.append(f"Rating: {rating}")

    recommendation = get_string('recommendation')
    if recommendation:
        parts.append(f"Recommendation: {recommendation}")

    # 8. Search Keywords
    keywords = get_string('search_keywords')
    if keywords:
        parts.append(f"Keywords: {keywords}")

    # 9. Skill Market Value
    market_value = get_string('skill_market_value')
    if market_value:
        parts.append(f"Market Value: {market_value}")

    # Fallback: if no parts were added, we have a problem
    if not parts:
        # Try to get name at least
        name = get_string('name')
        if name:
            parts.append(f"Candidate: {name}")

        # Last resort: check if there's any data at all
        if not parts:
            return ""  # Return empty string instead of None

    return '\n'.join(parts)


async def reembed_candidate(
    session: aiohttp.ClientSession,
    embed_url: str,
    tenant_id: str,
    candidate_id: str,
    candidate_data: Dict[str, Any],
    api_key: str
) -> bool:
    """Re-embed a single candidate with enriched profile"""
    try:
        profile_text = build_searchable_profile(candidate_data)

        if not profile_text or not profile_text.strip():
            print(f"SKIP {candidate_id}: No searchable profile could be built")
            return False

        payload = {
            "entityId": candidate_id,  # NO tenant prefix - must match candidate_profiles.candidate_id
            "text": profile_text,
            "metadata": {
                "source": "phase2_structured_reembedding",
                "modelVersion": "enriched-v1",
                "promptVersion": "structured-profile-v1"
            }
        }

        headers = {
            "Content-Type": "application/json",
            "X-Tenant-ID": tenant_id,
            "Authorization": f"Bearer {api_key}"
        }

        async with session.post(f"{embed_url}/v1/embeddings/upsert", json=payload, headers=headers) as resp:
            if resp.status >= 200 and resp.status < 300:
                print(f"✓ {candidate_id}: Re-embedded successfully")
                return True
            else:
                error_text = await resp.text()
                print(f"✗ {candidate_id}: Failed with {resp.status}: {error_text}")
                return False

    except Exception as e:
        print(f"✗ {candidate_id}: Exception: {e}")
        return False


async def main():
    """Main migration function"""
    tenant_id = os.getenv("TENANT_ID", "tenant-alpha")
    embed_url = os.getenv("EMBED_SERVICE_URL", "https://hh-embed-svc-production-akcoqbr7sa-uc.a.run.app")
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "headhunter-ai-0088")

    # Get Google Cloud identity token for Cloud Run authentication
    print("🔑 Getting authentication token...")
    api_key_env = get_auth_token()
    print("✅ Authentication token acquired\n")

    # Initialize Firestore
    credentials, _ = get_default_credentials()
    db = firestore.Client(project=project_id, credentials=credentials)

    # Query enriched candidates
    print(f"Fetching enriched candidates from Firestore for tenant {tenant_id}...")
    candidates_ref = db.collection(f"tenants/{tenant_id}/candidates")

    # Get all candidates (in batches if needed)
    all_docs = candidates_ref.stream()
    candidates = []
    for doc in all_docs:
        data = doc.to_dict()
        # Only process if enriched data exists
        if 'intelligent_analysis' in data or 'technical_assessment' in data or 'skill_assessment' in data:
            candidates.append((doc.id, data))

    print(f"Found {len(candidates)} enriched candidates")

    if not candidates:
        print("No enriched candidates found. Nothing to do.")
        return

    # Re-embed in parallel batches
    batch_size = 10
    success_count = 0
    fail_count = 0

    async with aiohttp.ClientSession() as session:
        for i in range(0, len(candidates), batch_size):
            batch = candidates[i:i + batch_size]
            print(f"\nProcessing batch {i // batch_size + 1}/{(len(candidates) + batch_size - 1) // batch_size}...")

            tasks = [
                reembed_candidate(session, embed_url, tenant_id, cid, data, api_key_env)
                for cid, data in batch
            ]
            results = await asyncio.gather(*tasks)

            success_count += sum(results)
            fail_count += len(results) - sum(results)

    print(f"\n{'='*60}")
    print(f"Re-embedding complete!")
    print(f"Success: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"Total: {len(candidates)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
