#!/usr/bin/env python3
"""Test re-embedding with enriched data"""

import json
import subprocess
import http.client
from typing import Dict, Any, List

EMBED_SVC_URL = "hh-embed-svc-production-akcoqbr7sa-uc.a.run.app"
TENANT_ID = "tenant-alpha"

def get_auth_token() -> str:
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

    # Technical Skills - explicit
    explicit_skills_obj = ia.get('explicit_skills', {})
    explicit_skills_list = explicit_skills_obj.get('technical_skills', [])
    explicit_skill_names = [s.get('skill') for s in explicit_skills_list if s.get('skill')]

    # Technical Skills - inferred
    inferred_skills_obj = ia.get('inferred_skills', {})
    inferred_skills_list = inferred_skills_obj.get('highly_probable_skills', [])
    inferred_skill_names = [s.get('skill') for s in inferred_skills_list if s.get('skill')]

    # Combine all skills
    all_skills = list(set(explicit_skill_names + inferred_skill_names))
    if all_skills:
        parts.append(f"Technical Skills: {', '.join(all_skills[:30])}")

    # Career Trajectory
    ct = ia.get('career_trajectory_analysis', {})
    current_level = ct.get('current_level')
    if current_level:
        parts.append(f"Career Level: {current_level}")

    years_exp = ct.get('years_experience')
    if years_exp:
        parts.append(f"Experience: {years_exp} years")

    promotion_velocity = ct.get('promotion_velocity')
    if promotion_velocity:
        parts.append(f"Promotion Pattern: {promotion_velocity}")

    # Market Positioning
    mp = ia.get('market_positioning', {})
    target_segment = mp.get('target_market_segment')
    if target_segment:
        parts.append(f"Market Segment: {target_segment}")

    salary_range = mp.get('salary_range_estimate')
    if salary_range:
        parts.append(f"Salary Range: {salary_range}")

    # Recruiter Insights
    ri = ia.get('recruiter_insights', {})
    pitch = ri.get('one_line_pitch')
    if pitch:
        parts.append(f"Profile: {pitch}")

    placement_likelihood = ri.get('placement_likelihood')
    if placement_likelihood:
        parts.append(f"Placement Potential: {placement_likelihood}")

    return '\n'.join(parts) if parts else "No enriched data available"

def test_reembed(candidates: List[Dict[str, Any]]):
    """Test re-embedding for a batch of candidates"""
    print(f"Testing re-embedding for {len(candidates)} candidates...\n")

    token = get_auth_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": TENANT_ID,
        "Content-Type": "application/json"
    }

    success_count = 0
    fail_count = 0

    for i, candidate in enumerate(candidates, 1):
        candidate_id = candidate.get('candidate_id')

        # Build searchable profile from enriched data
        searchable_text = build_searchable_profile(candidate)

        print(f"{i}/{len(candidates)}: Candidate {candidate_id}")
        print(f"   Searchable text (first 100 chars): {searchable_text[:100]}...")

        # Prepare embedding request
        payload = json.dumps({
            "entityId": str(candidate_id),
            "text": searchable_text,
            "metadata": {
                "source": "enriched_analysis",
                "reembedding": True
            },
            "chunkType": "default"
        })

        # Send request
        try:
            conn = http.client.HTTPSConnection(EMBED_SVC_URL)
            conn.request("POST", "/v1/embeddings/upsert", payload, headers)
            response = conn.getresponse()
            data = response.read().decode()

            if response.status in [200, 201]:
                result = json.loads(data)
                print(f"   ✅ Success! Dimensions: {result.get('dimensions', 'N/A')}")
                success_count += 1
            else:
                print(f"   ❌ Failed! Status: {response.status}, Response: {data[:100]}")
                fail_count += 1

        except Exception as e:
            print(f"   ❌ Error: {e}")
            fail_count += 1

        print()

    print(f"\n{'='*60}")
    print(f"Results: {success_count} success, {fail_count} failed")
    print(f"{'='*60}")

if __name__ == "__main__":
    # Load test candidates
    with open('/tmp/test_reembed_10.json', 'r') as f:
        test_candidates = json.load(f)

    test_reembed(test_candidates)
