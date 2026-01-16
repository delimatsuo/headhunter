#!/usr/bin/env python3
"""
Apply sourcing schema migration to Cloud SQL.
Can run locally via Cloud SQL Proxy or directly to Cloud SQL.

Usage:
    # Via Cloud SQL Proxy (run proxy first):
    python apply_sourcing_migration.py --local

    # Direct to Cloud SQL (requires proper IAM):
    python apply_sourcing_migration.py --project=headhunter-ai-0088 --instance=sql-hh-core
"""

import os
import sys
import argparse
from pathlib import Path

# Try to import psycopg2, install if needed
try:
    import psycopg2
except ImportError:
    print("Installing psycopg2-binary...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary"])
    import psycopg2

SCRIPT_DIR = Path(__file__).parent
MIGRATION_FILE = SCRIPT_DIR / "migrations" / "002_sourcing_schema.sql"


def apply_migration(
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
    dry_run: bool = False,
    force: bool = False
):
    """Apply the sourcing schema migration."""

    if not MIGRATION_FILE.exists():
        print(f"❌ Migration file not found: {MIGRATION_FILE}")
        return False

    print(f"📁 Migration file: {MIGRATION_FILE}")

    # Read migration SQL
    with open(MIGRATION_FILE, 'r') as f:
        migration_sql = f.read()

    if dry_run:
        print("\n[DRY RUN] Would execute:")
        print("-" * 40)
        print(migration_sql)
        print("-" * 40)
        return True

    print(f"\n🔌 Connecting to {host}:{port}/{database} as {user}...")

    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=10
        )
        conn.autocommit = False
        cur = conn.cursor()

        # Check if schema already exists
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.schemata
            WHERE schema_name = 'sourcing'
        """)
        schema_exists = cur.fetchone()[0] > 0

        cur.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'sourcing'
            AND table_name IN ('candidates', 'experience', 'skills', 'candidate_skills', 'embeddings')
        """)
        table_count = cur.fetchone()[0]

        print(f"📊 Schema exists: {'yes' if schema_exists else 'no'}")
        print(f"📊 Tables found: {table_count}/5")

        if table_count >= 5 and not force:
            print("✅ Sourcing schema already deployed!")
            print("   Use --force to re-deploy")
            cur.close()
            conn.close()
            return True

        if force and schema_exists:
            print("⚠️  Force mode: Dropping existing schema...")
            cur.execute("DROP SCHEMA IF EXISTS sourcing CASCADE")
            conn.commit()

        print("\n🚀 Applying migration...")

        # Execute migration (might have multiple statements)
        cur.execute(migration_sql)
        conn.commit()

        # Verify
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'sourcing'
            ORDER BY table_name
        """)
        tables = [row[0] for row in cur.fetchall()]

        print("\n✅ Migration applied successfully!")
        print("📋 Tables created:")
        for table in tables:
            print(f"   - sourcing.{table}")

        # Get row counts
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM sourcing.{table}")
            count = cur.fetchone()[0]
            print(f"      sourcing.{table}: {count} rows")

        cur.close()
        conn.close()
        return True

    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Apply sourcing schema migration")
    parser.add_argument("--local", action="store_true",
                        help="Use local connection (Cloud SQL Proxy required)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Database host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5432,
                        help="Database port (default: 5432)")
    parser.add_argument("--database", default="headhunter",
                        help="Database name (default: headhunter)")
    parser.add_argument("--user", help="Database user")
    parser.add_argument("--password", help="Database password")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show SQL without executing")
    parser.add_argument("--force", action="store_true",
                        help="Force re-deploy (drops existing schema)")

    args = parser.parse_args()

    # Get credentials from environment or args
    host = args.host
    port = args.port
    database = args.database
    user = args.user or os.getenv("PGVECTOR_USER") or os.getenv("DB_USER") or "postgres"
    password = args.password or os.getenv("PGVECTOR_PASSWORD") or os.getenv("DB_PASSWORD") or os.getenv("ADMIN_PASSWORD")

    if not password:
        print("❌ Password required. Set DB_PASSWORD or ADMIN_PASSWORD env var, or use --password")
        sys.exit(1)

    print("=" * 60)
    print("🔧 ELLA SOURCING - SCHEMA MIGRATION")
    print("=" * 60)
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Database: {database}")
    print(f"User: {user}")
    print(f"Dry run: {args.dry_run}")
    print(f"Force: {args.force}")
    print("=" * 60)

    success = apply_migration(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        dry_run=args.dry_run,
        force=args.force
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
