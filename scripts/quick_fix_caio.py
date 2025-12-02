import csv
import json
import firebase_admin
from firebase_admin import credentials, firestore
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred, {'projectId': 'headhunter-ai-0088'})

db = firestore.client()

def extract_linkedin(social_json_str):
    try:
        data = json.loads(social_json_str)
        for item in data:
            if item.get('type') == 'linkedin':
                return item.get('url')
    except Exception:
        pass
    return None

def main():
    filepath = "CSV files/505039_Ella_Executive_Search_CSVs_1/Ella_Executive_Search_candidates_1-1.csv"
    target_id = "190084523"
    
    logger.info(f"Searching for {target_id} in {filepath}...")
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.reader(f)
        for row in reader:
            if row and row[0] == target_id:
                logger.info("🎯 Found Caio Maia!")
                
                # Find social column
                social_str = ""
                for col in row:
                    if isinstance(col, str) and col.strip().startswith("[{") and "linkedin" in col.lower():
                        social_str = col
                        break
                
                if social_str:
                    linkedin_url = extract_linkedin(social_str)
                    logger.info(f"   Extracted URL: {linkedin_url}")
                    
                    if linkedin_url:
                        db.collection('candidates').document(target_id).set({'linkedin_url': linkedin_url}, merge=True)
                        db.collection('enriched_profiles').document(target_id).set({'linkedin_url': linkedin_url}, merge=True)
                        logger.info("✅ Firestore updated!")
                        return
                else:
                    logger.warning("❌ No social string found in row.")
                    return

    logger.warning("❌ Caio Maia not found in file.")

if __name__ == "__main__":
    main()
