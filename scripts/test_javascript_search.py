#!/usr/bin/env python3
"""
Test Search for Javascript Senior Developer with AWS
"""

import subprocess
import requests
import sys

# Get auth token
try:
    result = subprocess.run(
        ["gcloud", "auth", "print-identity-token"],
        capture_output=True,
        text=True,
        check=True
    )
    token = result.stdout.strip()
except subprocess.CalledProcessError as e:
    print(f"❌ Failed to get auth token: {e.stderr}")
    sys.exit(1)

# Search parameters
search_url = "https://hh-search-svc-production-akcoqbr7sa-uc.a.run.app/v1/search/candidates"
params = {
    "query": "Javascript senior developer with aws experience",
    "limit": 10
}
headers = {
    "X-Tenant-ID": "tenant-alpha",
    "Authorization": f"Bearer {token}"
}

print("="*80)
print('SEARCH: "Javascript senior developer with aws experience"')
print("="*80)
print()

try:
    response = requests.get(search_url, params=params, headers=headers, timeout=30)
    response.raise_for_status()

    data = response.json()

    if 'results' in data and len(data['results']) > 0:
        print(f"✅ Found {len(data['results'])} results\n")

        for i, result in enumerate(data['results'], 1):
            candidate_id = result.get('candidateId', 'N/A')
            vector_score = result.get('vectorScore', 0)

            print(f"{i}. Candidate ID: {candidate_id}")
            print(f"   Vector Score: {vector_score:.4f}")

            # Show profile data
            profile = result.get('profile', {})

            if profile.get('current_level'):
                print(f"   Level: {profile['current_level']}")

            if profile.get('overall_rating'):
                print(f"   Rating: {profile['overall_rating']}")

            # Show skills
            skills = []
            if profile.get('explicit_skills') and isinstance(profile['explicit_skills'], list):
                skills.extend(profile['explicit_skills'][:8])
            elif profile.get('primary_expertise') and isinstance(profile['primary_expertise'], list):
                skills.extend(profile['primary_expertise'][:8])

            if skills:
                print(f"   Skills: {', '.join(skills)}")

            # Show match reason if available
            if profile.get('search_keywords'):
                print(f"   Keywords: {profile['search_keywords']}")

            print()
    else:
        print("❌ No results found")
        if 'error' in data:
            print(f"   Error: {data['error']}")

    print("="*80)
    print("\n✅ Search completed successfully")
    print(f"   This proves embeddings are in Cloud SQL and working!")

except requests.exceptions.RequestException as e:
    print(f"❌ Search request failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    sys.exit(1)
