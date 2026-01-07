#!/usr/bin/env python3
"""
Sync Country Data from Firestore to PostgreSQL

The search service queries PostgreSQL, but country data was backfilled to Firestore.
This script syncs the country field from Firestore to PostgreSQL.

Usage:
    python3 sync_country_to_postgres.py [--dry-run]
"""

import argparse
import logging
import os
from collections import Counter

import firebase_admin
from firebase_admin import credentials, firestore
import psycopg2
from psycopg2.extras import execute_batch

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_firebase():
    """Initialize Firebase Admin SDK."""
    if not firebase_admin._apps:
        try:
            firebase_admin.initialize_app()
            logger.info("Initialized Firebase with default credentials")
        except Exception:
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred, {'projectId': 'headhunter-ai-0088'})
            logger.info("Initialized Firebase with application default credentials")


def get_postgres_connection():
    """Get PostgreSQL connection - tries Cloud SQL first, then local."""
    # Try Cloud SQL connection string from environment
    conn_str = os.environ.get('POSTGRES_URL')
    
    if not conn_str:
        # Try to build from individual env vars
        host = os.environ.get('POSTGRES_HOST', 'localhost')
        port = os.environ.get('POSTGRES_PORT', '5432')
        db = os.environ.get('POSTGRES_DB', 'headhunter')
        user = os.environ.get('POSTGRES_USER', 'headhunter')
        password = os.environ.get('POSTGRES_PASSWORD', 'headhunter')
        conn_str = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    
    logger.info(f"Connecting to PostgreSQL...")
    conn = psycopg2.connect(conn_str)
    return conn


def sync_country_data(dry_run: bool = False):
    """Sync country data from Firestore to PostgreSQL."""
    
    # Get Firestore data
    db = firestore.client()
    candidates_ref = db.collection('candidates')
    
    logger.info("Fetching candidates with country from Firestore...")
    
    updates = []
    country_stats = Counter()
    
    for doc in candidates_ref.stream():
        data = doc.to_dict()
        country = data.get('country')
        if country:
            updates.append((country, doc.id))
            country_stats[country] += 1
    
    logger.info(f"Found {len(updates)} candidates with country data")
    logger.info("Country distribution:")
    for country, count in country_stats.most_common():
        logger.info(f"  {country}: {count}")
    
    if dry_run:
        logger.info("[DRY RUN] Would update PostgreSQL with above data")
        return len(updates)
    
    # Connect to PostgreSQL and update
    conn = get_postgres_connection()
    cur = conn.cursor()
    
    # Check current state
    cur.execute("SELECT COUNT(*) FROM search.candidate_profiles WHERE country IS NOT NULL")
    before_count = cur.fetchone()[0]
    logger.info(f"PostgreSQL candidates with country before: {before_count}")
    
    # Batch update
    logger.info(f"Updating {len(updates)} candidates in PostgreSQL...")
    
    update_sql = """
        UPDATE search.candidate_profiles 
        SET country = %s 
        WHERE candidate_id = %s
    """
    
    execute_batch(cur, update_sql, updates, page_size=1000)
    conn.commit()
    
    # Check after
    cur.execute("SELECT COUNT(*) FROM search.candidate_profiles WHERE country IS NOT NULL")
    after_count = cur.fetchone()[0]
    logger.info(f"PostgreSQL candidates with country after: {after_count}")
    
    # Verify distribution
    cur.execute("""
        SELECT country, COUNT(*) as cnt 
        FROM search.candidate_profiles 
        WHERE country IS NOT NULL
        GROUP BY country 
        ORDER BY cnt DESC
    """)
    logger.info("\nPostgreSQL country distribution after sync:")
    for row in cur.fetchall():
        logger.info(f"  {row[0]}: {row[1]}")
    
    cur.close()
    conn.close()
    
    return len(updates)


def main():
    parser = argparse.ArgumentParser(description='Sync country data from Firestore to PostgreSQL')
    parser.add_argument('--dry-run', action='store_true', help='Preview without updating')
    args = parser.parse_args()
    
    logger.info("=== Sync Country Data to PostgreSQL ===")
    if args.dry_run:
        logger.info("Running in DRY RUN mode")
    
    init_firebase()
    count = sync_country_data(dry_run=args.dry_run)
    
    logger.info(f"\n=== Sync Complete: {count} candidates ===")


if __name__ == '__main__':
    main()
