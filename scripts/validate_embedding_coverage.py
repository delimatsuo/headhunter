#!/usr/bin/env python3
"""
Validate Embedding Coverage
============================
Check final embedding count in Cloud SQL to confirm remediation success.
"""

import os
import sys
import psycopg2
from datetime import datetime

def main():
    """Query Cloud SQL for embedding statistics"""

    # Database connection details
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "headhunter")
    db_user = os.getenv("DB_USER", "headhunter")
    db_password = os.getenv("DB_PASSWORD", "headhunter")

    print("=" * 80)
    print("🔍 EMBEDDING COVERAGE VALIDATION")
    print("=" * 80)
    print(f"Connecting to: {db_host}:{db_port}/{db_name}")
    print()

    try:
        # Connect to database
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password
        )
        cursor = conn.cursor()

        # Query 1: Total embeddings count
        print("📊 Total Embeddings:")
        cursor.execute("""
            SELECT COUNT(*) as total_embeddings
            FROM search.candidate_embeddings
        """)
        result = cursor.fetchone()
        total_embeddings = result[0] if result else 0
        print(f"   Total: {total_embeddings:,} embeddings")
        print()

        # Query 2: Embeddings by source metadata
        print("📊 Embeddings by Source:")
        cursor.execute("""
            SELECT
                metadata->>'source' as source,
                COUNT(*) as count
            FROM search.candidate_embeddings
            WHERE metadata->>'source' IS NOT NULL
            GROUP BY metadata->>'source'
            ORDER BY count DESC
        """)
        sources = cursor.fetchall()
        if sources:
            for source, count in sources:
                print(f"   {source}: {count:,}")
        else:
            print("   No source metadata found")
        print()

        # Query 3: Recent embeddings (last 24 hours)
        print("📊 Recent Embeddings (last 24 hours):")
        cursor.execute("""
            SELECT COUNT(*) as recent_count
            FROM search.candidate_embeddings
            WHERE created_at >= NOW() - INTERVAL '24 hours'
        """)
        result = cursor.fetchone()
        recent_count = result[0] if result else 0
        print(f"   Count: {recent_count:,}")
        print()

        # Query 4: Embedding dimension check
        print("📊 Embedding Dimensions:")
        cursor.execute("""
            SELECT DISTINCT vector_length(embedding) as dimension
            FROM search.candidate_embeddings
            LIMIT 5
        """)
        dimensions = cursor.fetchall()
        if dimensions:
            for (dim,) in dimensions:
                print(f"   Dimension: {dim}")
        print()

        # Summary
        print("=" * 80)
        print("✅ VALIDATION SUMMARY")
        print("=" * 80)
        print(f"Total Embeddings: {total_embeddings:,}")
        print(f"Expected Coverage: ~28,988 (Phase 2: 17,969 + Phase 3: 11,019)")
        print(f"Actual Coverage: {(total_embeddings/28988*100):.1f}%")

        if total_embeddings >= 28800:
            print("✅ SUCCESS: Near-100% coverage achieved!")
        elif total_embeddings >= 28000:
            print("⚠️  WARNING: Good coverage but slightly below expected")
        else:
            print("❌ ERROR: Coverage significantly below expected")

        print("=" * 80)

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
