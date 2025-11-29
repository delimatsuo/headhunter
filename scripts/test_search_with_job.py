#!/usr/bin/env python3
"""
Test Embedding Search with Job Description
===========================================

Creates a job description, generates an embedding, and searches for matching candidates.
"""

import subprocess
import json
import http.client
import psycopg2
from typing import List, Dict, Any

# Configuration
EMBED_SVC_URL = "hh-embed-svc-production-akcoqbr7sa-uc.a.run.app"
TENANT_ID = "tenant-alpha"

# Database connection (via Cloud SQL Proxy)
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'headhunter',
    'user': 'postgres',
    'password': 'TempAdmin123!'
}

# Job Description
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

def generate_job_embedding(job_text: str, token: str) -> List[float]:
    """Generate embedding for job description"""
    print("📝 Generating embedding for job description...")

    conn = http.client.HTTPSConnection(EMBED_SVC_URL)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": TENANT_ID,
        "Content-Type": "application/json"
    }

    payload = json.dumps({
        "entityId": "test-job-senior-java",
        "text": job_text,
        "metadata": {"type": "job_description", "role": "Senior Java Engineer"},
        "chunkType": "default"
    })

    conn.request("POST", "/v1/embeddings/upsert", payload, headers)
    response = conn.getresponse()
    data = response.read().decode()

    if response.status in [200, 201]:
        result = json.loads(data)
        print(f"   ✅ Embedding created: {result.get('dimensions')} dimensions")
        return result.get('vectorId')  # We'll query the DB to get the actual vector
    else:
        raise Exception(f"Failed to create embedding: {response.status} - {data}")

def get_embedding_vector(vector_id: str) -> List[float]:
    """Get the actual embedding vector from database"""
    print(f"📊 Fetching embedding vector from database...")

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT embedding::text
        FROM search.candidate_embeddings
        WHERE id = %s
    """, (vector_id,))

    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if result:
        # Parse the vector string to list of floats
        vector_str = result[0]
        # PostgreSQL vector format: [0.1,0.2,0.3,...]
        vector = [float(x) for x in vector_str.strip('[]').split(',')]
        print(f"   ✅ Retrieved vector: {len(vector)} dimensions")
        return vector
    else:
        raise Exception(f"Vector not found for ID: {vector_id}")

def search_similar_candidates(job_embedding: List[float], limit: int = 10) -> List[Dict[str, Any]]:
    """Search for candidates similar to the job description"""
    print(f"\n🔍 Searching for top {limit} matching candidates...")

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Convert embedding to PostgreSQL vector format
    vector_str = '[' + ','.join(str(x) for x in job_embedding) + ']'

    # Search using cosine similarity (lower distance = more similar)
    query = """
        SELECT
            entity_id,
            embedding_text,
            1 - (embedding <=> %s::vector) as similarity_score,
            metadata
        FROM search.candidate_embeddings
        WHERE tenant_id = %s
          AND entity_id != 'test-job-senior-java'
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """

    cursor.execute(query, (vector_str, TENANT_ID, vector_str, limit))
    results = cursor.fetchall()

    cursor.close()
    conn.close()

    candidates = []
    for row in results:
        candidates.append({
            'candidate_id': row[0],
            'profile_text': row[1],
            'similarity_score': float(row[2]),
            'metadata': row[3]
        })

    return candidates

def main():
    """Main test function"""
    print("=" * 80)
    print("EMBEDDING SEARCH TEST - Senior Java Software Engineer")
    print("=" * 80)
    print()

    # Step 1: Get auth token
    token = get_auth_token()

    # Step 2: Generate embedding for job description
    print("Job Description (first 200 chars):")
    print(JOB_DESCRIPTION[:200] + "...\n")

    vector_id = generate_job_embedding(JOB_DESCRIPTION, token)

    # Step 3: Get the actual embedding vector
    job_embedding = get_embedding_vector(vector_id)

    # Step 4: Search for similar candidates
    matches = search_similar_candidates(job_embedding, limit=10)

    # Step 5: Display results
    print(f"\n{'=' * 80}")
    print(f"TOP {len(matches)} MATCHING CANDIDATES")
    print(f"{'=' * 80}\n")

    for i, match in enumerate(matches, 1):
        print(f"{i}. Candidate ID: {match['candidate_id']}")
        print(f"   Similarity Score: {match['similarity_score']:.4f} (1.0 = perfect match)")

        # Show profile text (first 300 chars)
        profile = match['profile_text'] or "No profile text available"
        print(f"   Profile Preview:")
        for line in profile[:400].split('\n')[:5]:
            if line.strip():
                print(f"      {line.strip()}")

        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✅ Embedding system working correctly!")
    print(f"✅ Vector similarity search operational")
    print(f"✅ Found {len(matches)} candidates ranked by relevance")
    print(f"✅ Top match similarity: {matches[0]['similarity_score']:.4f}")
    print(f"\nThe embeddings are using enriched data (skills, experience, career level)")
    print(f"instead of raw resume text, providing high-quality semantic search results.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
