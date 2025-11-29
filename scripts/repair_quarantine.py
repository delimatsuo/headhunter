#!/usr/bin/env python3
"""
Quarantine Repair Script
Iterates through quarantined files, attempts to repair JSON using LLM, and uploads to Firestore.
"""

import os
import glob
import json
import asyncio
import shutil
import logging
from typing import Dict, Any, Optional

from scripts.intelligent_skill_processor import IntelligentSkillProcessor
from firebase_admin import firestore

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

QUARANTINE_DIR = ".quarantine"
REPAIRED_DIR = os.path.join(QUARANTINE_DIR, "repaired")
FAILED_DIR = os.path.join(QUARANTINE_DIR, "failed_repair")

os.makedirs(REPAIRED_DIR, exist_ok=True)
os.makedirs(FAILED_DIR, exist_ok=True)

async def repair_candidate(processor: IntelligentSkillProcessor, meta_file: str) -> bool:
    """Repair a single candidate"""
    base_name = meta_file[:-5]  # Remove .meta
    txt_file = base_name + ".txt"
    
    if not os.path.exists(txt_file):
        logger.warning(f"Missing .txt file for {meta_file}")
        return False

    # Read metadata
    try:
        with open(meta_file, 'r', encoding='utf-8') as f:
            meta_content = f.read()
            # Parse simple key: value format
            meta = {}
            for line in meta_content.splitlines():
                if ':' in line:
                    key, value = line.split(':', 1)
                    meta[key.strip()] = value.strip()
            
            candidate_id = meta.get('candidate_id')
            if not candidate_id or candidate_id == 'None':
                # Try to extract from filename if missing in meta
                # Format: timestamp_uuid.meta
                filename = os.path.basename(base_name)
                if '_' in filename:
                    candidate_id = filename.split('_')[1]
                else:
                    candidate_id = "unknown"
                    
    except Exception as e:
        logger.error(f"Error reading metadata {meta_file}: {e}")
        return False

    # Read raw payload
    try:
        with open(txt_file, 'r', encoding='utf-8') as f:
            raw_payload = f.read()
    except Exception as e:
        logger.error(f"Error reading payload {txt_file}: {e}")
        return False

    logger.info(f"🔧 Attempting repair for {candidate_id}...")
    
    # Attempt repair
    repaired_data = await processor.repair_json_with_llm(raw_payload)
    
    if repaired_data:
        logger.info(f"✅ Repair successful for {candidate_id}")
        
        # Construct full candidate document
        # Note: We might be missing original fields like 'experience' since we only have the output.
        # We'll do our best to reconstruct a valid document.
        
        candidate_doc = {
            "candidate_id": candidate_id,
            "intelligent_analysis": repaired_data,
            "processing_metadata": {
                "timestamp": firestore.SERVER_TIMESTAMP,
                "processor": "quarantine_repair",
                "repaired": True,
                "original_error": meta.get("error_message", "unknown")
            },
            # Add flattened fields for querying
            "explicit_skills": processor._extract_skill_names((repaired_data.get("explicit_skills") or {}).get("technical_skills", [])),
            "inferred_skills_high_confidence": [
                s["skill"] for s in (repaired_data.get("inferred_skills") or {}).get("highly_probable_skills", [])
                if isinstance(s, dict) and "skill" in s
            ],
            "all_probable_skills": processor._extract_all_probable_skills(repaired_data),
            "current_level": (repaired_data.get("career_trajectory_analysis") or {}).get("current_level", "Unknown"),
            "skill_market_value": (repaired_data.get("market_positioning") or {}).get("skill_market_value", "moderate"),
            "overall_rating": (repaired_data.get("recruiter_insights") or {}).get("overall_rating", "C"),
            "recommendation": (repaired_data.get("recruiter_insights") or {}).get("recommendation", "consider")
        }
        
        # Upload to Firestore
        try:
            # 1. Upload to candidates collection
            processor.db.collection("candidates").document(candidate_id).set(candidate_doc, merge=True)
            
            # 2. Upload to enriched_profiles collection
            enriched_doc = {
                "candidate_id": candidate_id,
                "intelligent_analysis": repaired_data,
                "processing_metadata": candidate_doc["processing_metadata"],
                "enrichment_timestamp": firestore.SERVER_TIMESTAMP
            }
            processor.db.collection("enriched_profiles").document(candidate_id).set(enriched_doc, merge=True)
            
            logger.info(f"📤 Uploaded repaired data for {candidate_id}")
            
            # Move files to repaired directory
            shutil.move(meta_file, os.path.join(REPAIRED_DIR, os.path.basename(meta_file)))
            shutil.move(txt_file, os.path.join(REPAIRED_DIR, os.path.basename(txt_file)))
            return True
            
        except Exception as e:
            logger.error(f"Error uploading to Firestore for {candidate_id}: {e}")
            return False
            
    else:
        logger.warning(f"❌ Repair failed for {candidate_id}")
        # Move to failed directory to avoid reprocessing
        shutil.move(meta_file, os.path.join(FAILED_DIR, os.path.basename(meta_file)))
        shutil.move(txt_file, os.path.join(FAILED_DIR, os.path.basename(txt_file)))
        return False

async def main():
    import argparse
    parser = argparse.ArgumentParser(description='Repair quarantined candidates')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of files to process (0 for all)')
    args = parser.parse_args()

    meta_files = glob.glob(os.path.join(QUARANTINE_DIR, "*.meta"))
    logger.info(f"Found {len(meta_files)} quarantined items")
    
    if args.limit > 0:
        meta_files = meta_files[:args.limit]
        logger.info(f"Processing limited batch of {len(meta_files)}")

    success_count = 0
    fail_count = 0

    async with IntelligentSkillProcessor() as processor:
        for meta_file in meta_files:
            if await repair_candidate(processor, meta_file):
                success_count += 1
            else:
                fail_count += 1
                
    logger.info(f"""
🏁 Repair Complete
   ✅ Success: {success_count}
   ❌ Failed: {fail_count}
    """)

if __name__ == "__main__":
    asyncio.run(main())
