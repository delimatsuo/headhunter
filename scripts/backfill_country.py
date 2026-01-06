#!/usr/bin/env python3
"""
Backfill Country Data

Populates the 'country' field for existing candidates in Firestore
by extracting it from CSV data or inferring from address fields.

Usage:
    python3 backfill_country.py [--dry-run] [--limit N]
"""

import argparse
import csv
import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional, Tuple
from collections import Counter

import firebase_admin
from firebase_admin import credentials, firestore

from country_extractor import extract_country_from_address

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]

# CSV files with candidate data
CSV_PATHS = [
    REPO_ROOT / "CSV files" / "505039_Ella_Executive_Search_CSVs_1" / "Ella_Executive_Search_candidates_1-1.csv",
    REPO_ROOT / "CSV files" / "505039_Ella_Executive_Search_CSVs_1" / "Ella_Executive_Search_candidates_2-1.csv",
    REPO_ROOT / "CSV files" / "505039_Ella_Executive_Search_CSVs_1" / "Ella_Executive_Search_candidates_3-1.csv",
]

# Merged data path (fallback)
MERGED_DATA_PATH = REPO_ROOT / "data" / "comprehensive_merged_candidates.json"


def init_firebase():
    """Initialize Firebase Admin SDK."""
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


def load_csv_address_data() -> Dict[str, str]:
    """Load address data from CSV files, keyed by candidate ID."""
    address_map = {}

    for csv_path in CSV_PATHS:
        if not csv_path.exists():
            logger.warning(f"CSV file not found: {csv_path}")
            continue

        logger.info(f"Loading addresses from {csv_path.name}...")
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                candidate_id = row.get('id', '').strip()
                address = row.get('address', '').strip()
                if candidate_id and address:
                    address_map[candidate_id] = address

    logger.info(f"Loaded {len(address_map)} addresses from CSV files")
    return address_map


def load_merged_address_data() -> Dict[str, str]:
    """Load address data from merged JSON file."""
    address_map = {}

    if not MERGED_DATA_PATH.exists():
        logger.warning(f"Merged data file not found: {MERGED_DATA_PATH}")
        return address_map

    logger.info(f"Loading addresses from {MERGED_DATA_PATH.name}...")
    with open(MERGED_DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for candidate in data:
        candidate_id = str(candidate.get('id', '')).strip()
        address = candidate.get('address', '').strip()
        if candidate_id and address:
            address_map[candidate_id] = address

    logger.info(f"Loaded {len(address_map)} addresses from merged data")
    return address_map


def backfill_firestore(
    address_map: Dict[str, str],
    dry_run: bool = False,
    limit: Optional[int] = None
) -> Tuple[int, int, int]:
    """
    Backfill country field in Firestore.

    Returns:
        Tuple of (updated, skipped, errors)
    """
    db = firestore.client()
    candidates_ref = db.collection('candidates')

    updated = 0
    skipped = 0
    errors = 0
    country_stats = Counter()

    # Get all candidates from Firestore
    logger.info("Fetching candidates from Firestore...")

    query = candidates_ref
    if limit:
        query = query.limit(limit)

    docs = list(query.stream())
    total = len(docs)
    logger.info(f"Found {total} candidates to process")

    batch = db.batch()
    batch_count = 0
    BATCH_SIZE = 500

    for i, doc in enumerate(docs):
        try:
            doc_id = doc.id
            data = doc.to_dict()

            # Skip if already has country
            existing_country = data.get('country')
            if existing_country:
                skipped += 1
                country_stats[existing_country] += 1
                continue

            # Try to get address from CSV data first
            address = address_map.get(doc_id, '')

            # Fall back to original_data.address in Firestore
            if not address:
                orig_data = data.get('original_data', {})
                if isinstance(orig_data, dict):
                    address = orig_data.get('address', '')

            # Extract country
            country, city = extract_country_from_address(address)

            if country:
                if dry_run:
                    logger.debug(f"[DRY RUN] Would update {doc_id}: country={country}, city={city}")
                else:
                    update_data = {
                        'country': country,
                        'city': city,
                        'address': address,
                    }
                    batch.update(candidates_ref.document(doc_id), update_data)
                    batch_count += 1

                    # Commit batch if full
                    if batch_count >= BATCH_SIZE:
                        batch.commit()
                        logger.info(f"Committed batch of {batch_count} updates")
                        batch = db.batch()
                        batch_count = 0

                updated += 1
                country_stats[country] += 1
            else:
                skipped += 1
                country_stats['Unknown'] += 1

            # Progress logging
            if (i + 1) % 1000 == 0:
                logger.info(f"Processed {i + 1}/{total} candidates...")

        except Exception as e:
            logger.error(f"Error processing {doc_id}: {e}")
            errors += 1

    # Commit remaining batch
    if batch_count > 0 and not dry_run:
        batch.commit()
        logger.info(f"Committed final batch of {batch_count} updates")

    # Log statistics
    logger.info("\n=== Backfill Summary ===")
    logger.info(f"Total processed: {total}")
    logger.info(f"Updated: {updated}")
    logger.info(f"Skipped (already has country or no address): {skipped}")
    logger.info(f"Errors: {errors}")
    logger.info("\nCountry distribution:")
    for country, count in country_stats.most_common():
        logger.info(f"  {country}: {count}")

    return updated, skipped, errors


def main():
    parser = argparse.ArgumentParser(description='Backfill country data for candidates')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying them')
    parser.add_argument('--limit', type=int, help='Limit number of candidates to process')
    args = parser.parse_args()

    logger.info("=== Country Backfill Script ===")
    if args.dry_run:
        logger.info("Running in DRY RUN mode - no changes will be made")

    # Initialize Firebase
    init_firebase()

    # Load address data from CSV files
    address_map = load_csv_address_data()

    # Also load from merged data as fallback
    merged_addresses = load_merged_address_data()
    for k, v in merged_addresses.items():
        if k not in address_map:
            address_map[k] = v

    logger.info(f"Total addresses available: {len(address_map)}")

    # Backfill Firestore
    updated, skipped, errors = backfill_firestore(
        address_map,
        dry_run=args.dry_run,
        limit=args.limit
    )

    logger.info("\n=== Backfill Complete ===")
    if args.dry_run:
        logger.info(f"Would have updated {updated} candidates")
    else:
        logger.info(f"Updated {updated} candidates")


if __name__ == '__main__':
    main()
