#!/usr/bin/env python3
"""
Verify Database Dimension Configuration
========================================

Checks the actual dimension configuration in the database via Cloud SQL Proxy.
"""

import psycopg2

# Database connection via Cloud SQL Proxy
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'headhunter',
    'user': 'postgres',
    'password': 'TempAdmin123!'
}

def check_dimension():
    """Check the embedding column dimension"""
    print("🔍 Verifying database dimension configuration...")
    print(f"{'='*60}\n")

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Check dimension
    cursor.execute("""
        SELECT
            attname as column_name,
            atttypmod as typmod,
            atttypmod - 4 as dimension,
            format_type(atttypid, atttypmod) as full_type
        FROM pg_attribute
        WHERE attrelid = 'search.candidate_embeddings'::regclass
          AND attname = 'embedding';
    """)

    result = cursor.fetchone()

    if result:
        col_name, typmod, dimension, full_type = result
        print(f"Column: {col_name}")
        print(f"Type: {full_type}")
        print(f"Typmod: {typmod}")
        print(f"Calculated Dimension: {dimension}")
        print()

        if dimension == 768:
            print("✅ Dimension is CORRECT (768)")
        else:
            print(f"❌ Dimension is WRONG (expected 768, got {dimension})")
    else:
        print("❌ Embedding column not found!")

    # Check indexes
    print(f"\n{'='*60}")
    print("Index Status:")
    print(f"{'='*60}\n")

    cursor.execute("""
        SELECT
            indexname,
            indexdef
        FROM pg_indexes
        WHERE schemaname = 'search'
          AND tablename = 'candidate_embeddings'
          AND indexname LIKE '%embedding%'
        ORDER BY indexname;
    """)

    indexes = cursor.fetchall()

    for idx_name, idx_def in indexes:
        print(f"Index: {idx_name}")
        print(f"   Definition: {idx_def}")
        print()

    # Check embeddings count
    cursor.execute("""
        SELECT COUNT(*) as total_embeddings
        FROM search.candidate_embeddings;
    """)

    count_result = cursor.fetchone()
    print(f"Total Embeddings: {count_result[0]:,}")

    cursor.close()
    conn.close()

    print(f"\n{'='*60}")
    print("Verification Complete")
    print(f"{'='*60}")

if __name__ == "__main__":
    try:
        check_dimension()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
