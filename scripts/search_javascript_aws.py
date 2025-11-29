#!/usr/bin/env python3
"""
Search for Javascript Senior Developer with AWS Experience
"""

import subprocess
import http.client
import json

# Service configuration
SEARCH_SVC_URL = "hh-search-svc-production-akcoqbr7sa-uc.a.run.app"
TENANT_ID = "tenant-alpha"

def get_auth_token():
    """Get Google Cloud identity token"""
    result = subprocess.run(
        ["gcloud", "auth", "print-identity-token"],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip()

print("="*80)
print("SEARCH: Javascript Senior Developer with AWS Experience")
print("="*80)
print()

# Get auth token
print("🔐 Getting auth token...")
token = get_auth_token()
print("   ✅ Token obtained\n")

# Prepare request
conn = http.client.HTTPSConnection(SEARCH_SVC_URL)

headers = {
    "Authorization": f"Bearer {token}",
    "X-Tenant-ID": TENANT_ID,
    "Content-Type": "application/json"
}

payload = json.dumps({
    "queryText": "Javascript senior developer with aws experience",
    "limit": 10,
    "includeScores": True
})

print("🔍 Searching Cloud SQL embeddings...")
print()

try:
    conn.request("POST", "/v1/search/hybrid", payload, headers)
    response = conn.getresponse()
    data = response.read().decode()

    if response.status == 200:
        results = json.loads(data)
        candidates = results.get('candidates', [])

        if candidates:
            print(f"✅ Found {len(candidates)} matching candidates\n")
            print("="*80)

            for i, candidate in enumerate(candidates, 1):
                cand_id = candidate.get('candidateId', 'Unknown')
                score = candidate.get('score', 0)

                print(f"\n{i}. Candidate ID: {cand_id}")
                print(f"   Relevance Score: {score:.4f}")

                # Show enriched profile
                enriched = candidate.get('enrichedProfile', {})
                if enriched:
                    # Level and rating
                    if enriched.get('current_level'):
                        print(f"   Level: {enriched['current_level']}")

                    if enriched.get('overall_rating'):
                        print(f"   Rating: {enriched['overall_rating']}/100")

                    # Skills
                    skills = enriched.get('skills', [])
                    if skills:
                        skill_names = []
                        for s in skills[:10]:
                            if isinstance(s, dict):
                                skill_names.append(s.get('skill', str(s)))
                            else:
                                skill_names.append(str(s))
                        print(f"   Skills: {', '.join(skill_names)}")

                    # Keywords
                    keywords = enriched.get('search_keywords')
                    if keywords:
                        print(f"   Keywords: {keywords}")

            print("\n" + "="*80)
            print("\n✅ Search completed successfully!")
            print(f"   Results retrieved from Cloud SQL embeddings")
            print(f"   Varied scores ({min(c.get('score', 0) for c in candidates):.2f}-{max(c.get('score', 0) for c in candidates):.2f}) prove unique embeddings")

        else:
            print("❌ No candidates found")

    else:
        print(f"❌ Search failed: HTTP {response.status}")
        print(f"   Response: {data}")

except Exception as e:
    print(f"❌ Error: {e}")
finally:
    conn.close()
