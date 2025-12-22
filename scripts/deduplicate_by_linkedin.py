#!/usr/bin/env python3
"""
Deduplicate Candidates by LinkedIn URL
=======================================

This script finds duplicate candidates based on LinkedIn URL and deletes
the older entries, keeping only the most recent one.

Usage:
    python scripts/deduplicate_by_linkedin.py --dry-run    # Preview changes
    python scripts/deduplicate_by_linkedin.py              # Actually delete
"""

import argparse
import logging
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any

import firebase_admin
from firebase_admin import credentials, firestore

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Firebase
if not firebase_admin._apps:
    try:
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {'projectId': 'headhunter-ai-0088'})
    except Exception as e:
        logger.error(f"Failed to init Firebase: {e}")
        exit(1)

db = firestore.client()


def normalize_linkedin_url(url: str) -> str:
    """
    Normalize LinkedIn URL for comparison.
    
    Examples:
        https://www.linkedin.com/in/joao-silva -> linkedin.com/in/joao-silva
        http://linkedin.com/in/joao-silva/ -> linkedin.com/in/joao-silva
        https://www.linkedin.com/in/Joao-Silva -> linkedin.com/in/joao-silva
    """
    if not url:
        return None
    
    url = url.lower().strip()
    
    # Remove protocol
    url = url.replace('https://', '').replace('http://', '')
    
    # Remove www.
    url = url.replace('www.', '')
    
    # Remove trailing slash
    url = url.rstrip('/')
    
    # Remove query parameters
    if '?' in url:
        url = url.split('?')[0]
    
    return url


def get_candidate_timestamp(data: Dict[str, Any]) -> datetime:
    """
    Get the creation/update timestamp for a candidate.
    Handles various timestamp formats.
    """
    # Try different timestamp fields
    for field in ['created_at', 'updated_at', 'imported_at']:
        ts = data.get(field)
        if ts:
            # Firestore Timestamp
            if hasattr(ts, 'seconds'):
                return datetime.fromtimestamp(ts.seconds)
            # String timestamp
            if isinstance(ts, str):
                try:
                    return datetime.fromisoformat(ts.replace('Z', '+00:00'))
                except:
                    try:
                        return datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
                    except:
                        pass
    
    # Default to epoch if no timestamp found
    return datetime(1970, 1, 1)


def find_duplicates():
    """
    Find all candidates grouped by their normalized LinkedIn URL.
    Returns a dict of linkedin_url -> list of (doc_id, data, timestamp)
    """
    logger.info("Scanning candidates for LinkedIn URLs...")
    
    linkedin_groups = defaultdict(list)
    total_candidates = 0
    candidates_with_linkedin = 0
    
    # Stream all candidates
    for doc in db.collection('candidates').stream():
        total_candidates += 1
        data = doc.to_dict()
        
        # Try to find LinkedIn URL in various places
        linkedin_url = None
        
        # Direct field
        if data.get('linkedin_url'):
            linkedin_url = data.get('linkedin_url')
        # Personal section
        elif data.get('personal', {}).get('linkedin'):
            linkedin_url = data.get('personal', {}).get('linkedin')
        
        if linkedin_url:
            normalized = normalize_linkedin_url(linkedin_url)
            if normalized and 'linkedin.com/in/' in normalized:
                timestamp = get_candidate_timestamp(data)
                linkedin_groups[normalized].append({
                    'doc_id': doc.id,
                    'name': data.get('name', 'Unknown'),
                    'timestamp': timestamp,
                    'data': data
                })
                candidates_with_linkedin += 1
        
        if total_candidates % 5000 == 0:
            logger.info(f"Scanned {total_candidates} candidates...")
    
    logger.info(f"Total candidates: {total_candidates}")
    logger.info(f"Candidates with LinkedIn URL: {candidates_with_linkedin}")
    
    return linkedin_groups


def deduplicate(dry_run: bool = True):
    """
    Find and delete duplicate candidates based on LinkedIn URL.
    Keeps the newest entry for each LinkedIn URL.
    """
    linkedin_groups = find_duplicates()
    
    # Find groups with duplicates
    duplicates = {k: v for k, v in linkedin_groups.items() if len(v) > 1}
    
    logger.info(f"Found {len(duplicates)} LinkedIn URLs with duplicates")
    
    total_to_delete = 0
    total_kept = 0
    docs_to_delete = []
    
    for linkedin_url, candidates in duplicates.items():
        # Sort by timestamp descending (newest first)
        sorted_candidates = sorted(candidates, key=lambda x: x['timestamp'], reverse=True)
        
        # Keep the newest, delete the rest
        keeper = sorted_candidates[0]
        to_delete = sorted_candidates[1:]
        
        total_kept += 1
        total_to_delete += len(to_delete)
        
        if len(to_delete) > 0:
            logger.info(f"LinkedIn: {linkedin_url}")
            logger.info(f"  KEEP: {keeper['doc_id']} - {keeper['name']} ({keeper['timestamp']})")
            for d in to_delete:
                logger.info(f"  DELETE: {d['doc_id']} - {d['name']} ({d['timestamp']})")
                docs_to_delete.append(d['doc_id'])
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Duplicate LinkedIn URLs found: {len(duplicates)}")
    logger.info(f"Documents to keep: {total_kept}")
    logger.info(f"Documents to delete: {total_to_delete}")
    
    if dry_run:
        logger.info("")
        logger.info("DRY RUN - No changes made.")
        logger.info("Run without --dry-run to actually delete duplicates.")
    else:
        logger.info("")
        logger.info("Deleting duplicates...")
        
        # Delete in batches (smaller to avoid transaction limits)
        batch = db.batch()
        batch_count = 0
        deleted = 0
        
        for doc_id in docs_to_delete:
            batch.delete(db.collection('candidates').document(doc_id))
            batch_count += 1
            
            if batch_count >= 100:  # Smaller batches to avoid size limit
                batch.commit()
                deleted += batch_count
                logger.info(f"Deleted {deleted} / {len(docs_to_delete)} documents...")
                batch = db.batch()
                batch_count = 0
        
        # Final batch
        if batch_count > 0:
            batch.commit()
            deleted += batch_count
        
        logger.info(f"✅ Deleted {deleted} duplicate candidates")
    
    return {
        'duplicates_found': len(duplicates),
        'documents_deleted': total_to_delete if not dry_run else 0,
        'documents_kept': total_kept
    }


def main():
    parser = argparse.ArgumentParser(description='Deduplicate candidates by LinkedIn URL')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without deleting')
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("DEDUPLICATE CANDIDATES BY LINKEDIN URL")
    logger.info("=" * 60)
    
    result = deduplicate(args.dry_run)
    
    logger.info("")
    logger.info("Result:", result)


if __name__ == "__main__":
    main()
