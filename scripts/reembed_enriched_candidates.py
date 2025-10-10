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
import sys
from typing import Any, Dict, List, Optional

import aiohttp
from google.cloud import firestore
from google.auth import default as get_default_credentials


def build_searchable_profile(candidate: Dict[str, Any]) -> str:
    """
    Builds a searchable profile from enriched candidate data.
    Mirrors the TypeScript implementation in embedding-client.ts
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

    def get_number(path: str) -> Optional[int]:
        """Get number from path"""
        value = get_field(path)
        return int(value) if isinstance(value, (int, float)) else None

    # 1. Technical Skills (HIGHEST PRIORITY)
    primary_skills = get_array('technical_assessment.primary_skills')
    core_competencies = get_array('skill_assessment.technical_skills.core_competencies')
    all_skills = list(set(primary_skills + core_competencies))
    if all_skills:
        parts.append(f"Technical Skills: {', '.join(all_skills[:15])}")

    # 2. Current Role and Title
    current_role = get_string('experience_analysis.current_role')
    current_title = get_string('current_title')
    if current_role:
        parts.append(f"Current Role: {current_role}")
    elif current_title:
        parts.append(f"Current Role: {current_title}")

    # 3. Experience and Seniority
    total_years = get_number('experience_analysis.total_years')
    years_experience = get_number('career_trajectory.years_experience')
    years = total_years if total_years is not None else years_experience
    if years is not None:
        parts.append(f"Experience: {years} years")

    seniority_level = get_string('personal_details.seniority_level')
    current_level = get_string('career_trajectory.current_level')
    seniority = seniority_level or current_level
    if seniority:
        parts.append(f"Seniority: {seniority}")

    # 4. Domain Expertise
    domain_expertise = get_array('skill_assessment.domain_expertise')
    if domain_expertise:
        parts.append(f"Domain: {', '.join(domain_expertise[:5])}")

    # 5. Role Type (IC vs Leadership)
    has_leadership = get_field('leadership_scope.has_leadership')
    team_size = get_number('leadership_scope.team_size')
    if has_leadership is True and team_size:
        parts.append(f"Leadership: Managing {team_size} people")
    elif has_leadership is False:
        parts.append("Role Type: Individual Contributor")

    # 6. Ideal Roles
    ideal_roles = get_array('recruiter_recommendations.ideal_roles')
    best_fit_roles = get_array('recruiter_insights.best_fit_roles')
    roles = list(set(ideal_roles + best_fit_roles))
    if roles:
        parts.append(f"Best Fit: {', '.join(roles[:5])}")

    # 7. Executive Summary
    one_liner = get_string('executive_summary.one_line_pitch')
    if one_liner:
        parts.append(f"Summary: {one_liner}")

    # 8. Searchability Keywords
    keywords = get_array('searchability.keywords')
    search_tags = get_array('search_optimization.keywords')
    all_keywords = list(set(keywords + search_tags))
    if all_keywords:
        parts.append(f"Keywords: {', '.join(all_keywords[:20])}")

    # 9. Company Pedigree
    company_tier = get_string('company_pedigree.company_tier')
    if company_tier:
        parts.append(f"Company Tier: {company_tier}")

    # Fallback: use resume_text if no enriched data
    if not parts:
        resume_text = get_string('resume_text')
        if resume_text:
            print(f"WARNING: No enriched data found for candidate, falling back to resume_text")
            return resume_text

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
            "entityId": f"{tenant_id}:{candidate_id}",
            "text": profile_text,
            "metadata": {
                "source": "reembed_migration",
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
    embed_url = os.getenv("EMBED_SERVICE_URL", "https://hh-embed-svc-production-1034162584026.us-central1.run.app")
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "headhunter-ai-0088")
    api_key_env = os.getenv("HH_API_KEY")

    if not api_key_env:
        print("ERROR: HH_API_KEY environment variable not set")
        sys.exit(1)

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
        if 'technical_assessment' in data or 'skill_assessment' in data:
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
