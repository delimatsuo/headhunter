import csv
import json
import os
import glob
import firebase_admin
from firebase_admin import credentials, firestore
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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

def extract_linkedin(social_json_str):
    try:
        # Handle CSV double-quote escaping if needed, though csv module usually handles it
        # The raw string might look like "[{""type""...}]" if read manually, 
        # but csv reader should give us '[{"type"...}]'
        
        data = json.loads(social_json_str)
        for item in data:
            if item.get('type') == 'linkedin':
                return item.get('url')
    except Exception:
        pass
    return None

def process_csv_file(filepath):
    logger.info(f"Processing {filepath}...")
    updated_count = 0
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f)
            # Skip header if present (heuristic: check if first row has "id" or similar)
            # We'll just iterate and check if row[0] looks like an ID
            
            for row in reader:
                if not row or len(row) < 13:
                    continue
                    
                candidate_id = row[0]
                if not candidate_id.isdigit():
                    continue
                
                if candidate_id == '190084523':
                    logger.info(f"🎯 Found Caio Maia (190084523) in row. Length: {len(row)}")
                    # logger.info(f"Row content: {row}")

                # Extract Email (Search all columns)
                email = ""
                # First check likely column 3
                if len(row) > 3 and "@" in row[3] and not row[3].startswith("[{"):
                    email = row[3].strip()
                
                # If not found, search all columns
                if not email:
                    for col in row:
                        if isinstance(col, str) and "@" in col and not col.startswith("[{") and len(col) < 100:
                            # Basic validation
                            if " " not in col.strip():
                                email = col.strip()
                                break
                
                # Look for the social media column. It's usually around index 12.
                # We'll search for a column that looks like JSON and has "linkedin"
                social_str = ""
                for col in row:
                    if isinstance(col, str) and col.strip().startswith("[{") and "linkedin" in col.lower():
                        social_str = col
                        break
                
                if candidate_id == '190084523':
                    logger.info(f"   Social string found: {bool(social_str)}")
                    if social_str:
                        logger.info(f"   Social string content: {social_str[:100]}...")

                linkedin_url = None
                if social_str:
                    linkedin_url = extract_linkedin(social_str)
                    
                    if candidate_id == '190084523':
                        logger.info(f"   Extracted LinkedIn URL: {linkedin_url}")

                if linkedin_url or email:
                    # Update Firestore
                    try:
                        update_data = {}
                        if linkedin_url:
                            update_data['linkedin_url'] = linkedin_url
                        if email:
                            update_data['email'] = email
                            
                        doc_ref = db.collection('candidates').document(candidate_id)
                        doc_ref.set(update_data, merge=True)
                        
                        # Also update enriched_profiles if it exists
                        enrich_ref = db.collection('enriched_profiles').document(candidate_id)
                        enrich_ref.set(update_data, merge=True)
                        
                        updated_count += 1
                        if updated_count % 100 == 0:
                            logger.info(f"   Updated {updated_count} candidates...")
                    except Exception as e:
                        logger.error(f"   Error updating {candidate_id}: {e}")

    except Exception as e:
        logger.error(f"Error reading {filepath}: {e}")
        
    logger.info(f"✅ Finished {filepath}: Updated {updated_count} candidates.")
    return updated_count

import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', help='Specific CSV file to process')
    args = parser.parse_args()

    if args.file:
        logger.info(f"Processing specific file: {args.file}")
        process_csv_file(args.file)
        return

    base_dir = "CSV files"
    csv_files = glob.glob(os.path.join(base_dir, "**/*.csv"), recursive=True)
    
    logger.info(f"Found {len(csv_files)} CSV files.")
    
    total_updated = 0
    for csv_file in csv_files:
        # Only process candidate files (heuristic)
        if "candidates" in csv_file.lower():
            total_updated += process_csv_file(csv_file)
            
    logger.info(f"🎉 Total candidates updated with LinkedIn URLs: {total_updated}")

if __name__ == "__main__":
    main()
