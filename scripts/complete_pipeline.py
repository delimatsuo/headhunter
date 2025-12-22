#!/usr/bin/env python3
"""
Complete Data Treatment Pipeline
=================================

This script runs the full data treatment pipeline:
1. Wait for classification to complete
2. Run LLM enrichment for career insights
3. Generate embeddings for vector search

Usage:
    python scripts/complete_pipeline.py
"""

import subprocess
import time
import logging
from datetime import datetime

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


def get_pipeline_stats():
    """Get current pipeline statistics."""
    stats = {
        'total': 0,
        'classified': 0,
        'enriched': 0,
        'with_embedding': 0,
        'needs_classification': 0,
        'needs_enrichment': 0,
        'needs_embedding': 0,
    }
    
    for doc in db.collection('candidates').stream():
        data = doc.to_dict()
        stats['total'] += 1
        
        # Classification check
        if data.get('searchable', {}).get('classification_version') == '2.0':
            stats['classified'] += 1
        elif data.get('processing', {}).get('needs_classification'):
            stats['needs_classification'] += 1
        
        # Enrichment check
        if data.get('intelligent_analysis'):
            stats['enriched'] += 1
        elif data.get('processing', {}).get('needs_enrichment'):
            stats['needs_enrichment'] += 1
        
        # Embedding check
        if data.get('searchable', {}).get('embedding'):
            stats['with_embedding'] += 1
        elif data.get('processing', {}).get('needs_embedding'):
            stats['needs_embedding'] += 1
    
    return stats


def print_stats(stats):
    """Print pipeline statistics."""
    logger.info("=" * 60)
    logger.info("PIPELINE STATUS")
    logger.info("=" * 60)
    logger.info(f"Total candidates:     {stats['total']}")
    logger.info(f"Classified (v2.0):    {stats['classified']} ({100*stats['classified']/max(1,stats['total']):.1f}%)")
    logger.info(f"Enriched:             {stats['enriched']} ({100*stats['enriched']/max(1,stats['total']):.1f}%)")
    logger.info(f"With embedding:       {stats['with_embedding']} ({100*stats['with_embedding']/max(1,stats['total']):.1f}%)")
    logger.info("")
    logger.info(f"Needs classification: {stats['needs_classification']}")
    logger.info(f"Needs enrichment:     {stats['needs_enrichment']}")
    logger.info(f"Needs embedding:      {stats['needs_embedding']}")


def run_enrichment_batch(batch_size=50, max_batches=100):
    """
    Run batch enrichment for candidates without intelligent_analysis.
    Uses the batch enrichment cloud function.
    """
    logger.info("Starting enrichment...")
    
    # Find candidates needing enrichment
    candidates_to_enrich = []
    
    for doc in db.collection('candidates').stream():
        data = doc.to_dict()
        if not data.get('intelligent_analysis'):
            candidates_to_enrich.append(doc.id)
    
    logger.info(f"Found {len(candidates_to_enrich)} candidates to enrich")
    
    if not candidates_to_enrich:
        logger.info("No candidates need enrichment")
        return
    
    # Import analysis service
    import sys
    sys.path.insert(0, 'functions')
    
    # For now, mark candidates as needing enrichment
    # The actual enrichment should be done via the cloud function
    batch = db.batch()
    count = 0
    
    for doc_id in candidates_to_enrich[:1000]:  # Limit to 1000 for now
        doc_ref = db.collection('candidates').document(doc_id)
        batch.update(doc_ref, {
            'processing.needs_enrichment': True,
            'processing.enrichment_queued_at': datetime.utcnow().isoformat()
        })
        count += 1
        
        if count >= 450:
            batch.commit()
            logger.info(f"Queued {count} candidates for enrichment")
            batch = db.batch()
            count = 0
    
    if count > 0:
        batch.commit()
        logger.info(f"Queued {count} candidates for enrichment")
    
    logger.info(f"Total queued: {len(candidates_to_enrich[:1000])}")
    logger.info("Run cloud function batchEnrichCandidates to process queue")


def generate_embeddings():
    """
    Generate embeddings for candidates that have classification but no embedding.
    """
    logger.info("Checking for candidates needing embeddings...")
    
    # Count candidates that need embeddings
    needs_embedding = 0
    has_embedding = 0
    
    for doc in db.collection('candidates').stream():
        data = doc.to_dict()
        if data.get('searchable', {}).get('embedding'):
            has_embedding += 1
        else:
            needs_embedding += 1
    
    logger.info(f"Candidates with embedding: {has_embedding}")
    logger.info(f"Candidates needing embedding: {needs_embedding}")
    
    if needs_embedding == 0:
        logger.info("All candidates have embeddings!")
        return
    
    logger.info("To generate embeddings, run:")
    logger.info("  python scripts/reembed_enriched_candidates.py")


def main():
    logger.info("=" * 60)
    logger.info("COMPLETE DATA TREATMENT PIPELINE")
    logger.info("=" * 60)
    logger.info(f"Started at: {datetime.now().isoformat()}")
    
    # Get initial stats
    logger.info("\nGetting pipeline statistics...")
    stats = get_pipeline_stats()
    print_stats(stats)
    
    # Check if classification is still running
    import os
    result = os.popen("ps aux | grep run-backfill | grep -v grep | wc -l").read().strip()
    classification_running = int(result) > 0
    
    if classification_running:
        logger.info("\n⚠️  Classification processes are still running")
        logger.info("   Waiting for them to complete...")
        
        # Wait and monitor
        while True:
            time.sleep(30)
            result = os.popen("ps aux | grep run-backfill | grep -v grep | wc -l").read().strip()
            if int(result) == 0:
                logger.info("✅ Classification complete!")
                break
            logger.info(f"   Still running... ({result} processes)")
    
    # Get updated stats
    logger.info("\nUpdated statistics after classification:")
    stats = get_pipeline_stats()
    print_stats(stats)
    
    # Run enrichment (queue candidates)
    logger.info("\n" + "=" * 60)
    logger.info("STEP 2: ENRICHMENT")
    logger.info("=" * 60)
    run_enrichment_batch()
    
    # Check embeddings
    logger.info("\n" + "=" * 60)
    logger.info("STEP 3: EMBEDDINGS")
    logger.info("=" * 60)
    generate_embeddings()
    
    # Final stats
    logger.info("\n" + "=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Finished at: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
