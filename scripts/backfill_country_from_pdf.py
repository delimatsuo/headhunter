#!/usr/bin/env python3
"""
Backfill Country Data from LinkedIn PDFs

Extracts location/country from LinkedIn PDF exports and updates:
1. Firestore candidates collection
2. PostgreSQL search.candidate_profiles table

This script processes all ~3,000 candidate PDFs to populate country data
for accurate geographic filtering in search.

Usage:
    python3 backfill_country_from_pdf.py [--dry-run] [--limit N] [--firestore-only] [--postgres-only]
"""

import argparse
import logging
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Optional, Tuple

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from pdf_location_extractor import (
    build_candidate_pdf_mapping,
    extract_location_from_linkedin_pdf,
)
from country_extractor import extract_country_from_address

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
RESUMES_DIR = REPO_ROOT / "CSV files" / "505039_Ella_Executive_Search_files_1" / "resumes"


def init_firebase():
    """Initialize Firebase Admin SDK."""
    import firebase_admin
    from firebase_admin import credentials

    if not firebase_admin._apps:
        try:
            firebase_admin.initialize_app()
            logger.info("Initialized Firebase with default credentials")
        except Exception:
            try:
                cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(cred, {
                    'projectId': 'headhunter-ai-0088',
                })
                logger.info("Initialized Firebase with application default credentials")
            except Exception as e:
                logger.error(f"Could not initialize Firebase: {e}")
                raise


def init_postgres():
    """Initialize PostgreSQL connection."""
    import psycopg2
    from psycopg2.extras import execute_batch

    # Try environment variable first
    postgres_url = os.environ.get('POSTGRES_URL')
    if postgres_url:
        conn = psycopg2.connect(postgres_url)
    else:
        # Fall back to local default
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='headhunter',
            user='headhunter',
            password='headhunter'
        )

    logger.info("Connected to PostgreSQL")
    return conn


def extract_country_from_all_pdfs(
    pdf_mapping: Dict[str, str],
    limit: Optional[int] = None
) -> Dict[str, Dict]:
    """
    Extract country data from all PDFs.

    Returns dict of candidate_id -> {country, city, raw_location, source}
    """
    results = {}
    total = len(pdf_mapping)

    if limit:
        items = list(pdf_mapping.items())[:limit]
    else:
        items = list(pdf_mapping.items())

    logger.info(f"Extracting locations from {len(items)} PDFs...")

    for i, (candidate_id, pdf_path) in enumerate(items):
        try:
            location_data = extract_location_from_linkedin_pdf(pdf_path)
            if location_data.get('country'):
                results[candidate_id] = location_data

            # Progress logging
            if (i + 1) % 500 == 0:
                logger.info(f"Processed {i + 1}/{len(items)} PDFs, found {len(results)} with country data")

        except Exception as e:
            logger.debug(f"Error extracting from PDF {pdf_path}: {e}")
            continue

    logger.info(f"Extracted country data for {len(results)}/{len(items)} candidates")
    return results


def backfill_firestore(
    location_data: Dict[str, Dict],
    dry_run: bool = False
) -> Tuple[int, int, int]:
    """
    Update Firestore candidates with country data.

    Returns: (updated, skipped, errors)
    """
    from firebase_admin import firestore

    db = firestore.client()
    candidates_ref = db.collection('candidates')

    updated = 0
    skipped = 0
    errors = 0
    country_stats = Counter()

    # Process in batches
    batch = db.batch()
    batch_count = 0
    BATCH_SIZE = 500

    for candidate_id, data in location_data.items():
        try:
            doc_ref = candidates_ref.document(candidate_id)
            doc = doc_ref.get()

            if not doc.exists:
                skipped += 1
                continue

            existing = doc.to_dict()
            existing_country = existing.get('country')

            # Skip if already has country
            if existing_country:
                skipped += 1
                country_stats[existing_country] += 1
                continue

            country = data.get('country')
            city = data.get('city')
            raw_location = data.get('raw_location')

            if country:
                if dry_run:
                    logger.debug(f"[DRY RUN] Would update {candidate_id}: country={country}, city={city}")
                else:
                    update_data = {
                        'country': country,
                        'city': city,
                        'location_raw': raw_location,
                    }
                    batch.update(doc_ref, update_data)
                    batch_count += 1

                    if batch_count >= BATCH_SIZE:
                        batch.commit()
                        logger.info(f"Firestore: Committed batch of {batch_count} updates")
                        batch = db.batch()
                        batch_count = 0

                updated += 1
                country_stats[country] += 1
            else:
                skipped += 1

        except Exception as e:
            logger.error(f"Firestore error for {candidate_id}: {e}")
            errors += 1

    # Commit remaining batch
    if batch_count > 0 and not dry_run:
        batch.commit()
        logger.info(f"Firestore: Committed final batch of {batch_count} updates")

    logger.info(f"\nFirestore Summary: updated={updated}, skipped={skipped}, errors={errors}")
    logger.info("Country distribution:")
    for country, count in country_stats.most_common(10):
        logger.info(f"  {country}: {count}")

    return updated, skipped, errors


def backfill_postgres(
    location_data: Dict[str, Dict],
    dry_run: bool = False
) -> Tuple[int, int, int]:
    """
    Update PostgreSQL candidate_profiles with country data.

    Returns: (updated, skipped, errors)
    """
    from psycopg2.extras import execute_batch

    conn = init_postgres()
    cur = conn.cursor()

    updated = 0
    skipped = 0
    errors = 0
    country_stats = Counter()

    # Prepare batch updates
    updates = []

    for candidate_id, data in location_data.items():
        country = data.get('country')
        city = data.get('city')

        if country:
            updates.append((country, city, candidate_id))
            country_stats[country] += 1

    if dry_run:
        logger.info(f"[DRY RUN] Would update {len(updates)} PostgreSQL records")
        cur.close()
        conn.close()
        return len(updates), 0, 0

    # Execute batch update
    try:
        logger.info(f"Updating {len(updates)} PostgreSQL records...")

        # Update across all tenants
        update_sql = """
            UPDATE search.candidate_profiles
            SET country = %s, location = COALESCE(location, %s)
            WHERE candidate_id = %s AND country IS NULL
        """

        execute_batch(cur, update_sql, updates, page_size=1000)
        conn.commit()

        updated = cur.rowcount if cur.rowcount >= 0 else len(updates)
        logger.info(f"PostgreSQL: Updated {updated} records")

    except Exception as e:
        logger.error(f"PostgreSQL batch update error: {e}")
        conn.rollback()
        errors = len(updates)

    cur.close()
    conn.close()

    logger.info(f"\nPostgreSQL Summary: updated={updated}, skipped={skipped}, errors={errors}")
    logger.info("Country distribution:")
    for country, count in country_stats.most_common(10):
        logger.info(f"  {country}: {count}")

    return updated, skipped, errors


def main():
    parser = argparse.ArgumentParser(description='Backfill country data from LinkedIn PDFs')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--limit', type=int, help='Limit number of PDFs to process')
    parser.add_argument('--firestore-only', action='store_true', help='Only update Firestore')
    parser.add_argument('--postgres-only', action='store_true', help='Only update PostgreSQL')
    args = parser.parse_args()

    logger.info("=== Country Backfill from LinkedIn PDFs ===")
    if args.dry_run:
        logger.info("Running in DRY RUN mode")

    # Build PDF mapping
    logger.info(f"\nScanning for PDFs in: {RESUMES_DIR}")
    pdf_mapping = build_candidate_pdf_mapping(str(RESUMES_DIR))
    logger.info(f"Found {len(pdf_mapping)} candidates with PDF files")

    # Extract country from all PDFs
    location_data = extract_country_from_all_pdfs(pdf_mapping, limit=args.limit)

    if not location_data:
        logger.warning("No location data extracted. Exiting.")
        return

    # Country statistics preview
    country_counts = Counter(d['country'] for d in location_data.values() if d.get('country'))
    logger.info(f"\nExtracted country data for {len(location_data)} candidates:")
    for country, count in country_counts.most_common():
        logger.info(f"  {country}: {count}")

    # Update Firestore
    if not args.postgres_only:
        logger.info("\n--- Updating Firestore ---")
        init_firebase()
        fs_updated, fs_skipped, fs_errors = backfill_firestore(location_data, args.dry_run)

    # Update PostgreSQL
    if not args.firestore_only:
        logger.info("\n--- Updating PostgreSQL ---")
        try:
            pg_updated, pg_skipped, pg_errors = backfill_postgres(location_data, args.dry_run)
        except Exception as e:
            logger.warning(f"PostgreSQL update skipped: {e}")
            logger.info("(PostgreSQL may not be running locally)")

    logger.info("\n=== Backfill Complete ===")


if __name__ == '__main__':
    main()
