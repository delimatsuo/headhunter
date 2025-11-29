#!/usr/bin/env python3
"""
Apply Database Dimension Fix
============================

Applies the complete embedding dimension fix to the production database.
"""

import psycopg2
import sys

# Database connection via Cloud SQL Proxy
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'headhunter',
    'user': 'postgres',
    'password': 'uYIOOh2FS1pVHtDpV+aBLDDOdsPhqsk7WKwhmsU/wqw='
}

def verify_current_dimension(conn):
    """Check the current embedding column dimension"""
    print("🔍 Checking current dimension...")
    print("="*60)

    cursor = conn.cursor()
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
    cursor.close()

    if result:
        col_name, typmod, dimension, full_type = result
        print(f"Column: {col_name}")
        print(f"Type: {full_type}")
        print(f"Typmod: {typmod}")
        print(f"Calculated Dimension: {dimension}")
        print()

        if dimension == 768:
            print("✅ Dimension is already CORRECT (768)")
            return True
        else:
            print(f"❌ Dimension is WRONG (expected 768, got {dimension})")
            return False
    else:
        print("❌ Embedding column not found!")
        return False

def check_embeddings_count(conn):
    """Check current embeddings count"""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM search.candidate_embeddings;")
    count = cursor.fetchone()[0]
    cursor.close()
    return count

def apply_fix(conn):
    """Apply the dimension fix"""
    print("\n" + "="*60)
    print("🔧 Applying Database Fix...")
    print("="*60)
    print("\n⚠️  This will drop and recreate the embedding column")
    print("⚠️  All existing embeddings will be lost and need to be regenerated")
    print()

    cursor = conn.cursor()

    # Start transaction
    print("Starting transaction...")
    cursor.execute("BEGIN;")

    # 1. Drop and recreate embedding column
    print("  1. Dropping and recreating embedding column with vector(768)...")
    cursor.execute("ALTER TABLE search.candidate_embeddings DROP COLUMN IF EXISTS embedding CASCADE;")
    cursor.execute("ALTER TABLE search.candidate_embeddings ADD COLUMN embedding vector(768);")

    # 2. Recreate unique constraint
    print("  2. Recreating unique constraint...")
    cursor.execute("""
        ALTER TABLE search.candidate_embeddings
          ADD CONSTRAINT candidate_embeddings_tenant_entity_chunk_unique
          UNIQUE (tenant_id, entity_id, chunk_type);
    """)

    # 3. Recreate HNSW index
    print("  3. Creating HNSW index...")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS candidate_embeddings_embedding_hnsw_idx
          ON search.candidate_embeddings
          USING hnsw (embedding vector_cosine_ops)
          WITH (m = 16, ef_construction = 64);
    """)

    # 4. Recreate IVFFlat index
    print("  4. Creating IVFFlat index...")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS candidate_embeddings_embedding_ivfflat_idx
          ON search.candidate_embeddings
          USING ivfflat (embedding vector_cosine_ops)
          WITH (lists = 100);
    """)

    # Commit transaction
    print("  5. Committing transaction...")
    cursor.execute("COMMIT;")

    print("\n✅ Database fix applied successfully!")

    cursor.close()

def main():
    try:
        print("🔌 Connecting to database...")
        conn = psycopg2.connect(**DB_CONFIG)
        print("✅ Connected!\n")

        # Check current dimension
        is_correct = verify_current_dimension(conn)

        if is_correct:
            print("\n✅ No fix needed - dimension is already correct!")
            conn.close()
            return 0

        # Check embeddings count before fix
        count_before = check_embeddings_count(conn)
        print(f"\n📊 Current embeddings count: {count_before:,}")

        # Apply fix
        apply_fix(conn)

        # Verify fix
        print("\n" + "="*60)
        print("🔍 Verifying fix...")
        print("="*60 + "\n")
        is_correct_after = verify_current_dimension(conn)

        # Check embeddings count after fix
        count_after = check_embeddings_count(conn)
        print(f"\n📊 Embeddings count after fix: {count_after:,}")

        if is_correct_after and count_after == 0:
            print("\n" + "="*60)
            print("✅ FIX COMPLETE!")
            print("="*60)
            print("\nNext steps:")
            print("  1. Re-embed all 17,969 enriched candidates")
            print("     python3 scripts/reembed_all_enriched.py")
            print("  2. Restart services")
            print("  3. Verify search functionality")
            return 0
        else:
            print("\n❌ Fix verification failed!")
            return 1

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            print("\n🔌 Disconnected from database")

if __name__ == "__main__":
    sys.exit(main())
