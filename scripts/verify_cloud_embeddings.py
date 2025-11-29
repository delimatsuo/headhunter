#!/usr/bin/env python3
"""
Verify Cloud Embeddings Status
===============================
Check actual embedding storage in Cloud SQL to confirm all candidates
have embeddings correctly stored in the production cloud service.
"""

import os
import sys
from google.cloud.sql.connector import Connector
import sqlalchemy
from sqlalchemy import text

def main():
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "headhunter-ai-0088")
    instance_connection_name = f"{project_id}:us-central1:sql-hh-core"
    db_user = "headhunter"
    db_pass = os.getenv("DB_PASSWORD", "headhunter")
    db_name = "headhunter"
    tenant_id = "tenant-alpha"

    print("🔍 Verifying embeddings in Cloud SQL...")
    print(f"   Instance: {instance_connection_name}")
    print(f"   Database: {db_name}")
    print(f"   Tenant: {tenant_id}\n")

    # Initialize Cloud SQL connector
    connector = Connector()

    def getconn():
        conn = connector.connect(
            instance_connection_name,
            "pg8000",
            user=db_user,
            password=db_pass,
            db=db_name,
        )
        return conn

    # Create SQLAlchemy engine
    engine = sqlalchemy.create_engine(
        "postgresql+pg8000://",
        creator=getconn,
    )

    try:
        with engine.connect() as conn:
            # Check if table exists
            print("📊 Checking database structure...")
            table_check = text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'search'
                    AND table_name = 'candidate_embeddings'
                );
            """)
            table_exists = conn.execute(table_check).scalar()

            if not table_exists:
                print("❌ ERROR: search.candidate_embeddings table does not exist!")
                print("   Cloud SQL embeddings table not set up yet.")
                sys.exit(1)

            print("✅ Table exists: search.candidate_embeddings\n")

            # Count total embeddings
            print("📊 Counting embeddings...")
            count_query = text("""
                SELECT COUNT(*) as total
                FROM search.candidate_embeddings
                WHERE tenant_id = :tenant_id;
            """)
            total_count = conn.execute(count_query, {"tenant_id": tenant_id}).scalar()

            # Count unique embeddings
            unique_query = text("""
                SELECT COUNT(DISTINCT embedding) as unique_embeddings
                FROM search.candidate_embeddings
                WHERE tenant_id = :tenant_id;
            """)
            unique_count = conn.execute(unique_query, {"tenant_id": tenant_id}).scalar()

            # Count unique entity IDs
            entity_query = text("""
                SELECT COUNT(DISTINCT entity_id) as unique_entities
                FROM search.candidate_embeddings
                WHERE tenant_id = :tenant_id;
            """)
            entity_count = conn.execute(entity_query, {"tenant_id": tenant_id}).scalar()

            # Check embedding dimension
            dim_query = text("""
                SELECT vector_dims(embedding) as dimension
                FROM search.candidate_embeddings
                WHERE tenant_id = :tenant_id
                LIMIT 1;
            """)
            dimension_result = conn.execute(dim_query, {"tenant_id": tenant_id}).fetchone()
            dimension = dimension_result[0] if dimension_result else None

            # Get metadata breakdown
            metadata_query = text("""
                SELECT
                    metadata->>'source' as source,
                    COUNT(*) as count
                FROM search.candidate_embeddings
                WHERE tenant_id = :tenant_id
                GROUP BY metadata->>'source'
                ORDER BY count DESC;
            """)
            metadata_results = conn.execute(metadata_query, {"tenant_id": tenant_id}).fetchall()

            # Get sample embedding vector
            sample_query = text("""
                SELECT
                    entity_id,
                    substring(embedding::text, 1, 100) as vector_preview
                FROM search.candidate_embeddings
                WHERE tenant_id = :tenant_id
                LIMIT 3;
            """)
            sample_results = conn.execute(sample_query, {"tenant_id": tenant_id}).fetchall()

            # Print results
            print("="*80)
            print("✅ CLOUD SQL EMBEDDINGS STATUS")
            print("="*80)
            print(f"Total embeddings stored:        {total_count:,}")
            print(f"Unique embedding vectors:       {unique_count:,}")
            print(f"Unique candidate IDs:           {entity_count:,}")
            print(f"Embedding dimension:            {dimension}")
            print("="*80)

            # Analysis
            print("\n📊 DATA QUALITY ANALYSIS:")
            if total_count == unique_count:
                print("   ✅ All embeddings are unique (no duplicates)")
            else:
                duplicates = total_count - unique_count
                print(f"   ⚠️  Found {duplicates} duplicate embeddings")

            if total_count == entity_count:
                print("   ✅ One embedding per candidate (1:1 mapping)")
            elif entity_count < total_count:
                print(f"   ⚠️  Some candidates have multiple embeddings")
            else:
                print(f"   ❌ More entities than embeddings (should not happen)")

            if dimension == 768:
                print("   ✅ Correct embedding dimension (768)")
            else:
                print(f"   ⚠️  Unexpected dimension: {dimension} (expected 768)")

            # Metadata breakdown
            if metadata_results:
                print("\n📋 EMBEDDINGS BY SOURCE:")
                for row in metadata_results:
                    source = row[0] or "null"
                    count = row[1]
                    print(f"   - {source}: {count:,} embeddings")

            # Sample vectors
            if sample_results:
                print("\n🔍 SAMPLE EMBEDDING VECTORS:")
                for row in sample_results:
                    entity_id = row[0]
                    preview = row[1]
                    print(f"   - {entity_id}: {preview}...")

            # Expected vs Actual
            EXPECTED_CANDIDATES = 28988  # From Firestore verification
            print("\n💡 COVERAGE ANALYSIS:")
            print(f"   Expected candidates (from Firestore): {EXPECTED_CANDIDATES:,}")
            print(f"   Actual embeddings (in Cloud SQL):     {entity_count:,}")

            if entity_count == EXPECTED_CANDIDATES:
                print("   ✅ 100% COVERAGE - All candidates have embeddings!")
            elif entity_count > EXPECTED_CANDIDATES:
                extra = entity_count - EXPECTED_CANDIDATES
                print(f"   ⚠️  {extra} extra embeddings (may include deleted candidates)")
            else:
                missing = EXPECTED_CANDIDATES - entity_count
                print(f"   ❌ MISSING {missing:,} embeddings ({missing/EXPECTED_CANDIDATES*100:.1f}%)")
                print(f"   → Need to embed {missing:,} more candidates")

            print("="*80)

    except Exception as e:
        print(f"❌ ERROR connecting to Cloud SQL: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure Cloud SQL instance is running")
        print("2. Check DB_PASSWORD environment variable")
        print("3. Verify Cloud SQL API is enabled")
        print("4. Check firewall rules allow connection")
        sys.exit(1)
    finally:
        connector.close()

if __name__ == "__main__":
    main()
