#!/usr/bin/env python3
"""
Verify Actual Embeddings in Cloud SQL
======================================
Direct database query to count what's ACTUALLY stored.
"""

import os
import sys

try:
    import pg8000
    from google.cloud.sql.connector import Connector
except ImportError:
    print("❌ Missing dependencies. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "cloud-sql-python-connector[pg8000]"])
    import pg8000
    from google.cloud.sql.connector import Connector

# Configuration
PROJECT_ID = "headhunter-ai-0088"
REGION = "us-central1"
INSTANCE_NAME = "sql-hh-core"
DB_USER = "headhunter"
DB_NAME = "headhunter"
TENANT_ID = "tenant-alpha"

# Get password from env or use default
DB_PASSWORD = os.getenv("DB_PASSWORD", "headhunter")

print("="*80)
print("CLOUD SQL EMBEDDINGS VERIFICATION")
print("="*80)
print(f"Instance: {PROJECT_ID}:{REGION}:{INSTANCE_NAME}")
print(f"Database: {DB_NAME}")
print(f"Tenant: {TENANT_ID}\n")

# Initialize connector
connector = Connector()

def getconn():
    conn = connector.connect(
        f"{PROJECT_ID}:{REGION}:{INSTANCE_NAME}",
        "pg8000",
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
    )
    return conn

try:
    print("🔌 Connecting to Cloud SQL...")
    conn = getconn()
    cursor = conn.cursor()
    print("✅ Connected\n")

    # Query 1: Count embeddings
    print("📊 Query 1: Counting embeddings...")
    cursor.execute("""
        SELECT
            COUNT(*) as total_embeddings,
            COUNT(DISTINCT embedding) as unique_embeddings,
            COUNT(DISTINCT entity_id) as unique_candidates
        FROM search.candidate_embeddings
        WHERE tenant_id = %s;
    """, (TENANT_ID,))

    row = cursor.fetchone()
    total_emb, unique_emb, unique_cand = row

    print(f"   Total embeddings:      {total_emb:,}")
    print(f"   Unique embeddings:     {unique_emb:,}")
    print(f"   Unique candidates:     {unique_cand:,}\n")

    # Query 2: Check for dimension
    print("📊 Query 2: Checking embedding dimensions...")
    cursor.execute("""
        SELECT vector_dims(embedding) as dimension
        FROM search.candidate_embeddings
        WHERE tenant_id = %s
        LIMIT 1;
    """, (TENANT_ID,))

    dim_row = cursor.fetchone()
    if dim_row:
        dimension = dim_row[0]
        print(f"   Embedding dimension:   {dimension}\n")
    else:
        print("   ⚠️  No embeddings found to check dimension\n")

    # Query 3: Source breakdown
    print("📊 Query 3: Embeddings by source...")
    cursor.execute("""
        SELECT
            metadata->>'source' as source,
            COUNT(*) as count
        FROM search.candidate_embeddings
        WHERE tenant_id = %s
        GROUP BY metadata->>'source'
        ORDER BY count DESC;
    """, (TENANT_ID,))

    sources = cursor.fetchall()
    if sources:
        for source, count in sources:
            source_name = source if source else "(null)"
            print(f"   - {source_name}: {count:,}")
    print()

    # Query 4: Sample entity IDs
    print("📊 Query 4: Sample entity IDs...")
    cursor.execute("""
        SELECT entity_id
        FROM search.candidate_embeddings
        WHERE tenant_id = %s
        ORDER BY created_at DESC
        LIMIT 10;
    """, (TENANT_ID,))

    samples = cursor.fetchall()
    if samples:
        print("   Recent entity IDs:")
        for (entity_id,) in samples:
            print(f"      - {entity_id}")
    print()

    # Analysis
    print("="*80)
    print("ANALYSIS")
    print("="*80)

    EXPECTED_COUNT = 28988

    if total_emb == 0:
        print("❌ CRITICAL: No embeddings found in Cloud SQL!")
        print("   The embedding scripts reported success but nothing was stored.")
        print("   Check hh-embed-svc logs for storage errors.")
    elif total_emb < 100:
        print(f"❌ CRITICAL: Only {total_emb} embeddings found!")
        print(f"   Expected: ~{EXPECTED_COUNT:,}")
        print(f"   Missing: ~{EXPECTED_COUNT - total_emb:,}")
        print("   This explains why search returns weak matches.")
    elif total_emb < EXPECTED_COUNT * 0.5:
        print(f"⚠️  WARNING: Only {total_emb:,} embeddings found")
        print(f"   Expected: ~{EXPECTED_COUNT:,}")
        print(f"   Missing: ~{EXPECTED_COUNT - total_emb:,} ({(EXPECTED_COUNT - total_emb)/EXPECTED_COUNT*100:.1f}%)")
    elif total_emb < EXPECTED_COUNT * 0.9:
        print(f"⚠️  Partial coverage: {total_emb:,} embeddings")
        print(f"   Expected: ~{EXPECTED_COUNT:,}")
        print(f"   Missing: ~{EXPECTED_COUNT - total_emb:,} ({(EXPECTED_COUNT - total_emb)/EXPECTED_COUNT*100:.1f}%)")
    else:
        print(f"✅ GOOD: {total_emb:,} embeddings found")
        print(f"   Coverage: {total_emb/EXPECTED_COUNT*100:.1f}%")

        if unique_emb < total_emb * 0.95:
            print(f"⚠️  WARNING: Some duplicate embeddings detected")
            print(f"   Duplicates: ~{total_emb - unique_emb:,}")
        else:
            print(f"✅ All embeddings are unique")

    print("="*80)

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    connector.close()
