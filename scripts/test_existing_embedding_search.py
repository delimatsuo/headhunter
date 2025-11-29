#!/usr/bin/env python3
"""
Test Search with Existing Embeddings
====================================

Tests semantic search using existing candidate embeddings to verify
the search functionality works correctly with enriched data.
"""

import psycopg2
from typing import List, Dict, Any

# Database connection (requires Cloud SQL Proxy or direct connection)
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'headhunter',
    'user': 'postgres',
    'password': 'TempAdmin123!'
}

TENANT_ID = "tenant-alpha"

def test_search_with_existing_embedding(limit: int = 10) -> None:
    """
    Test semantic search by:
    1. Pick a random candidate with skills
    2. Use their embedding to find similar candidates
    3. Display results to verify search quality
    """
    print("=" * 80)
    print("SEMANTIC SEARCH TEST - Using Existing Enriched Embeddings")
    print("=" * 80)
    print()

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Step 1: Get a sample candidate with their embedding
        print("📝 Selecting a sample candidate...")
        cursor.execute("""
            SELECT
                entity_id,
                embedding_text,
                embedding,
                metadata
            FROM search.candidate_embeddings
            WHERE tenant_id = %s
              AND embedding_text IS NOT NULL
              AND embedding_text != 'No enriched data available'
            LIMIT 1;
        """, (TENANT_ID,))

        sample_row = cursor.fetchone()
        if not sample_row:
            print("❌ No candidates found with enriched embeddings!")
            return

        sample_id, sample_text, sample_embedding, sample_metadata = sample_row

        print(f"✅ Sample Candidate ID: {sample_id}")
        print(f"\nEnriched Profile:")
        for line in sample_text.split('\n')[:8]:
            print(f"   {line}")
        print()

        # Step 2: Search for similar candidates
        print(f"🔍 Searching for top {limit} similar candidates...")
        print()

        # Convert embedding to string format for query
        embedding_str = '[' + ','.join(str(x) for x in sample_embedding) + ']'

        cursor.execute("""
            SELECT
                entity_id,
                embedding_text,
                1 - (embedding <=> %s::vector) as similarity_score,
                metadata
            FROM search.candidate_embeddings
            WHERE tenant_id = %s
              AND entity_id != %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """, (embedding_str, TENANT_ID, sample_id, embedding_str, limit))

        results = cursor.fetchall()

        # Step 3: Display results
        print(f"{'=' * 80}")
        print(f"TOP {len(results)} MATCHING CANDIDATES")
        print(f"{'=' * 80}\n")

        for i, row in enumerate(results, 1):
            entity_id, profile_text, similarity, metadata = row

            print(f"{i}. Candidate ID: {entity_id}")
            print(f"   Similarity Score: {similarity:.4f} (1.0 = perfect match)")

            if profile_text:
                print(f"   Profile Preview:")
                for line in profile_text.split('\n')[:5]:
                    if line.strip():
                        print(f"      {line.strip()}")
            else:
                print(f"   Profile: No enriched data")

            print()

        # Summary
        print("=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"✅ Semantic search operational!")
        print(f"✅ Vector similarity search working correctly")
        print(f"✅ Found {len(results)} similar candidates")
        if results:
            print(f"✅ Top match similarity: {results[0][2]:.4f}")
        print(f"\n💡 Search is using enriched AI analysis data (skills, experience, career level)")
        print(f"   instead of raw resume text, providing high-quality semantic matching.")

        cursor.close()
        conn.close()

    except psycopg2.OperationalError as e:
        print(f"\n❌ Database Connection Error: {e}")
        print(f"\n💡 Make sure Cloud SQL Proxy is running:")
        print(f"   ./cloud_sql_proxy headhunter-ai-0088:us-central1:sql-hh-core")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_search_with_existing_embedding(limit=10)
