#!/usr/bin/env python3
"""
Import New ATS CSV Format
=========================

This script imports candidates from the new ATS CSV format:
  candidate_details_active_jobs_*.csv

Pipeline:
1. Parse CSV with new column format
2. Extract LinkedIn URLs from "Social profiles" text
3. Parse experience and education text
4. Import to Firestore (with deduplication by email)
5. Trigger LLM classification for searchable fields
6. Generate embeddings for vector search

Usage:
    python scripts/import_new_csv_format.py --file /path/to/csv
    python scripts/import_new_csv_format.py --file /path/to/csv --dry-run
    python scripts/import_new_csv_format.py --file /path/to/csv --limit 100
"""

import csv
import json
import os
import re
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import FieldFilter

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


def extract_linkedin_url(social_profiles: str) -> Optional[str]:
    """
    Extract LinkedIn URL from social profiles text.
    
    Input format: "Linkedin: https://... | Github: https://..."
    """
    if not social_profiles:
        return None
    
    # Pattern: Linkedin: URL
    match = re.search(r'Linkedin:\s*(https?://[^\s|]+)', social_profiles, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    return None


def extract_github_url(social_profiles: str) -> Optional[str]:
    """Extract GitHub URL from social profiles text."""
    if not social_profiles:
        return None
    
    match = re.search(r'Github:\s*(https?://[^\s|]+)', social_profiles, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    return None


def parse_experience_text(experience_text: str) -> Dict[str, Any]:
    """
    Parse experience text and extract current role and companies.
    
    Returns:
        {
            'current_title': str,
            'current_company': str,
            'companies': [str],
            'title_keywords': [str],
            'raw_experience': str
        }
    """
    result = {
        'current_title': None,
        'current_company': None,
        'companies': [],
        'title_keywords': [],
        'raw_experience': experience_text
    }
    
    if not experience_text:
        return result
    
    # Split by " | " to get individual roles
    roles = experience_text.split(' | ')
    
    # Extract companies and titles
    for role in roles:
        # Pattern: "TITLE at COMPANY (DATE to DATE)"
        match = re.match(r'^(.+?)\s+at\s+(.+?)\s*\(', role.strip())
        if match:
            title = match.group(1).strip()
            company = match.group(2).strip()
            
            if company and company not in result['companies']:
                result['companies'].append(company)
            
            if title and title not in result['title_keywords']:
                result['title_keywords'].append(title)
    
    # First role is current
    if roles:
        first_role = roles[0].strip()
        match = re.match(r'^(.+?)\s+at\s+(.+?)\s*\(', first_role)
        if match:
            result['current_title'] = match.group(1).strip()
            result['current_company'] = match.group(2).strip()
    
    return result


def parse_education_text(education_text: str) -> List[Dict[str, str]]:
    """
    Parse education text into structured format.
    
    Returns list of education entries.
    """
    if not education_text:
        return []
    
    educations = []
    entries = education_text.split(' | ')
    
    for entry in entries:
        # Pattern: "DEGREE at SCHOOL (DATE to DATE)"
        match = re.match(r'^(.+?)\s+at\s+(.+?)\s*\(([\d/Nn]+)\s*to\s*([\d/Nn]+)\)', entry.strip())
        if match:
            educations.append({
                'degree': match.group(1).strip(),
                'school': match.group(2).strip(),
                'start_date': match.group(3).strip(),
                'end_date': match.group(4).strip()
            })
    
    return educations


def get_existing_emails() -> Dict[str, str]:
    """Get all existing candidate emails mapped to their IDs."""
    logger.info("Loading existing candidates for deduplication...")
    
    emails = {}
    candidates = db.collection('candidates').select(['email', 'canonical_email']).stream()
    
    for doc in candidates:
        data = doc.to_dict()
        email = data.get('canonical_email') or data.get('email')
        if email:
            emails[email.lower().strip()] = doc.id
    
    logger.info(f"Found {len(emails)} existing candidates with emails")
    return emails


def process_csv_row(row: Dict[str, str]) -> Dict[str, Any]:
    """
    Process a single CSV row and return candidate document.
    """
    name = row.get('Name', '').strip()
    email = row.get('Email', '').strip()
    
    if not name:
        return None
    
    # Parse experience
    experience = parse_experience_text(row.get('Experiences', ''))
    
    # Parse education
    education = parse_education_text(row.get('Educations', ''))
    
    # Extract social URLs
    social_profiles = row.get('Social profiles', '')
    linkedin_url = extract_linkedin_url(social_profiles)
    github_url = extract_github_url(social_profiles)
    
    # Build candidate document
    now = datetime.utcnow().isoformat()
    
    candidate = {
        # Identity
        'name': name,
        'email': email if email else None,
        'canonical_email': email.lower().strip() if email else None,
        'phone': row.get('Phone', '').strip() or None,
        
        # Personal info
        'personal': {
            'name': name,
            'email': email if email else None,
            'phone': row.get('Phone', '').strip() or None,
            'location': row.get('Job location', '').strip() or None,
            'linkedin': linkedin_url,
            'github': github_url,
        },
        
        # Professional info
        'professional': {
            'current_title': experience['current_title'],
            'current_company': experience['current_company'],
        },
        
        # Profile data (for enrichment)
        'profile': {
            'name': name,
            'current_role': experience['current_title'],
            'headline': row.get('Headline', '').strip() or None,
            'summary': row.get('Summary', '').strip() or None,
        },
        
        # Raw data for enrichment
        'experience': experience['raw_experience'],
        'education': row.get('Educations', ''),
        
        # Searchable fields (pre-processed)
        'searchable': {
            'title_keywords': experience['title_keywords'][:10],  # Limit to 10
            'companies': experience['companies'][:10],
            'function': 'general',  # Will be updated by LLM classification
            'level': 'mid',  # Will be updated by LLM classification
        },
        
        # Source tracking
        'source': row.get('Source', 'CSV Import'),
        'linkedin_url': linkedin_url,
        
        # Status
        'stage': row.get('Stage', 'Sourced'),
        'tags': [t.strip() for t in row.get('Tags', '').split(',') if t.strip()],
        'disqualified': row.get('Disqualified', 'No').lower() == 'yes',
        
        # Timestamps
        'created_at': row.get('Creation time', now),
        'updated_at': now,
        'imported_at': now,
        
        # Processing flags
        'processing': {
            'status': 'imported',
            'imported_at': now,
            'needs_enrichment': True,
            'needs_classification': True,
            'needs_embedding': True,
        },
        
        # Multi-org support
        'org_id': 'org_ella_main',
        'org_ids': ['org_ella_main'],
    }
    
    return candidate


def import_csv(filepath: str, dry_run: bool = False, limit: Optional[int] = None):
    """
    Import candidates from CSV file.
    """
    logger.info(f"Starting import from: {filepath}")
    logger.info(f"Dry run: {dry_run}, Limit: {limit}")
    
    # Load existing emails for deduplication
    existing_emails = get_existing_emails()
    
    stats = {
        'total': 0,
        'imported': 0,
        'skipped_duplicate': 0,
        'skipped_no_name': 0,
        'skipped_disqualified': 0,
        'errors': 0,
    }
    
    batch = db.batch()
    batch_count = 0
    BATCH_SIZE = 450
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            stats['total'] += 1
            
            if limit and stats['total'] > limit:
                break
            
            # Skip disqualified candidates
            if row.get('Disqualified', 'No').lower() == 'yes':
                stats['skipped_disqualified'] += 1
                continue
            
            # Process row
            candidate = process_csv_row(row)
            
            if not candidate:
                stats['skipped_no_name'] += 1
                continue
            
            # Check for duplicate
            email = candidate.get('canonical_email')
            if email and email in existing_emails:
                stats['skipped_duplicate'] += 1
                if stats['total'] % 500 == 0:
                    logger.info(f"Progress: {stats['total']} rows processed, {stats['imported']} imported, {stats['skipped_duplicate']} duplicates")
                continue
            
            # Generate ID
            candidate_id = f"cand_{int(datetime.utcnow().timestamp()*1000)}_{stats['imported']:05d}"
            
            if dry_run:
                if stats['imported'] < 5:
                    logger.info(f"[DRY RUN] Would import: {candidate['name']} - {candidate['professional']['current_title']}")
            else:
                try:
                    doc_ref = db.collection('candidates').document(candidate_id)
                    batch.set(doc_ref, candidate)
                    batch_count += 1
                    
                    # Track email for in-memory dedup
                    if email:
                        existing_emails[email] = candidate_id
                    
                    # Commit batch if full
                    if batch_count >= BATCH_SIZE:
                        batch.commit()
                        logger.info(f"Committed batch of {batch_count} candidates. Total imported: {stats['imported']}")
                        batch = db.batch()
                        batch_count = 0
                        
                except Exception as e:
                    logger.error(f"Error importing {candidate['name']}: {e}")
                    stats['errors'] += 1
                    continue
            
            stats['imported'] += 1
            
            if stats['total'] % 500 == 0:
                logger.info(f"Progress: {stats['total']} rows processed, {stats['imported']} imported")
    
    # Commit final batch
    if batch_count > 0 and not dry_run:
        batch.commit()
        logger.info(f"Committed final batch of {batch_count} candidates")
    
    return stats


def main():
    parser = argparse.ArgumentParser(description='Import candidates from new ATS CSV format')
    parser.add_argument('--file', required=True, help='Path to CSV file')
    parser.add_argument('--dry-run', action='store_true', help='Simulate import without writing')
    parser.add_argument('--limit', type=int, help='Limit number of rows to process')
    args = parser.parse_args()
    
    if not os.path.exists(args.file):
        logger.error(f"File not found: {args.file}")
        exit(1)
    
    logger.info("=" * 60)
    logger.info("NEW CSV FORMAT IMPORT")
    logger.info("=" * 60)
    
    stats = import_csv(args.file, args.dry_run, args.limit)
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("IMPORT SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total rows:          {stats['total']}")
    logger.info(f"Imported:            {stats['imported']}")
    logger.info(f"Skipped (duplicate): {stats['skipped_duplicate']}")
    logger.info(f"Skipped (no name):   {stats['skipped_no_name']}")
    logger.info(f"Skipped (disqualified): {stats['skipped_disqualified']}")
    logger.info(f"Errors:              {stats['errors']}")
    
    if not args.dry_run and stats['imported'] > 0:
        logger.info("")
        logger.info("NEXT STEPS:")
        logger.info("1. Run LLM classification: python scripts/run-backfill.js")
        logger.info("2. Run enrichment: curl -X POST https://batchEnrichCandidates...")
        logger.info("3. Generate embeddings: python scripts/reembed_enriched_candidates.py")


if __name__ == "__main__":
    main()
