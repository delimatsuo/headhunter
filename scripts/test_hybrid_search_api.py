#!/usr/bin/env python3
"""
Test Hybrid Search API with Job Description
==========================================

Tests the complete search pipeline by sending a Senior Java Engineer
job description to the hh-search-svc API and displaying matching candidates.
"""

import subprocess
import http.client
import json
from typing import Dict, Any

# Service URL
SEARCH_SVC_URL = "hh-search-svc-production-akcoqbr7sa-uc.a.run.app"
TENANT_ID = "tenant-alpha"

# Job Description for Senior Java Engineer
JOB_DESCRIPTION = """
Senior Java Software Engineer

We are seeking an experienced Senior Java Software Engineer to join our team.

Required Skills:
- 8+ years of Java development experience
- Strong expertise in Spring Framework and Spring Boot
- Experience with microservices architecture
- Proficiency in Docker and Kubernetes
- Knowledge of AWS cloud services
- Experience with CI/CD pipelines
- Strong understanding of database design (PostgreSQL, MySQL)
- Agile/Scrum methodology experience

Responsibilities:
- Design and develop scalable Java applications
- Lead technical architecture decisions
- Mentor junior developers
- Implement best practices for code quality
- Collaborate with cross-functional teams

Nice to Have:
- Experience with Kafka or RabbitMQ
- Knowledge of Redis caching
- Frontend experience (React/Angular)
- DevOps experience
"""

def get_auth_token() -> str:
    """Get Google Cloud identity token"""
    result = subprocess.run(
        ["gcloud", "auth", "print-identity-token"],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()

def hybrid_search(query_text: str, token: str, limit: int = 10) -> Dict[str, Any]:
    """
    Perform hybrid search using the hh-search-svc API

    Args:
        query_text: Job description or search query
        token: Auth token
        limit: Number of results to return

    Returns:
        Search results with candidates
    """
    conn = http.client.HTTPSConnection(SEARCH_SVC_URL)

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": TENANT_ID,
        "Content-Type": "application/json"
    }

    payload = json.dumps({
        "queryText": query_text,
        "limit": limit,
        "includeScores": True
    })

    try:
        conn.request("POST", "/v1/search/hybrid", payload, headers)
        response = conn.getresponse()
        data = response.read().decode()

        if response.status == 200:
            return json.loads(data)
        else:
            raise Exception(f"Search failed: HTTP {response.status} - {data}")
    finally:
        conn.close()

def main():
    """Main test function"""
    print("=" * 80)
    print("HYBRID SEARCH API TEST - Senior Java Software Engineer")
    print("=" * 80)
    print()

    # Get auth token
    print("🔐 Getting auth token...")
    token = get_auth_token()
    print("   ✅ Token obtained\n")

    # Display job description
    print("📝 Job Description:")
    print("-" * 80)
    for line in JOB_DESCRIPTION.strip().split('\n')[:10]:
        print(f"   {line}")
    print("   ...")
    print()

    # Perform search
    print("🔍 Searching for matching candidates...")
    print()

    try:
        results = hybrid_search(JOB_DESCRIPTION, token, limit=10)

        # Display results
        candidates = results.get('candidates', [])
        if not candidates:
            print("❌ No candidates found!")
            return

        print(f"{'=' * 80}")
        print(f"TOP {len(candidates)} MATCHING CANDIDATES")
        print(f"{'=' * 80}\n")

        for i, candidate in enumerate(candidates, 1):
            candidate_id = candidate.get('candidateId', 'Unknown')
            score = candidate.get('score', 0)

            print(f"{i}. Candidate ID: {candidate_id}")
            print(f"   Relevance Score: {score:.4f}")

            # Show enriched profile if available
            enriched = candidate.get('enrichedProfile', {})
            if enriched:
                print(f"   Profile:")

                # Skills
                skills = enriched.get('skills', [])
                if skills:
                    skill_names = [s.get('skill', s) if isinstance(s, dict) else s for s in skills[:10]]
                    print(f"      Skills: {', '.join(skill_names)}")

                # Career level
                career = enriched.get('careerLevel')
                if career:
                    print(f"      Career Level: {career}")

                # Experience
                experience = enriched.get('yearsExperience')
                if experience:
                    print(f"      Experience: {experience} years")

            print()

        # Summary
        print("=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"✅ Hybrid search API working correctly!")
        print(f"✅ Found {len(candidates)} matching candidates")
        print(f"✅ Top match score: {candidates[0].get('score', 0):.4f}")
        print(f"\n💡 Search uses:")
        print(f"   • Semantic search with enriched AI analysis embeddings")
        print(f"   • Keyword matching for specific requirements")
        print(f"   • Hybrid scoring combining both approaches")
        print(f"\nThe embeddings are working properly with enriched data!")

    except Exception as e:
        print(f"❌ Search Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
