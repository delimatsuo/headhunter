#!/usr/bin/env python3
"""
Upload processed candidates to Firestore
"""

import json
import sys
import urllib.request
import urllib.parse
import urllib.error
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent

class FirestoreUploader:
    def __init__(self, emulator_host="localhost", emulator_port="8081"):
        self.base_url = f"http://{emulator_host}:{emulator_port}/v1/projects/headhunter-ai-0088/databases/(default)/documents"
        self.project_id = "headhunter-ai-0088"
        
    def upload_candidate(self, candidate_data):
        """Upload a single candidate to Firestore"""
        candidate_id = candidate_data['candidate_id']
        
        # Convert Python data to Firestore format
        firestore_doc = self.convert_to_firestore_format(candidate_data)
        
        url = f"{self.base_url}/candidates/{candidate_id}"
        
        try:
            data = json.dumps(firestore_doc).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
            req.get_method = lambda: 'PATCH'
            
            with urllib.request.urlopen(req) as response:
                if response.getcode() == 200:
                    return True, None
                else:
                    return False, f"HTTP {response.getcode()}: {response.read().decode()}"
        except urllib.error.HTTPError as e:
            return False, f"HTTP {e.code}: {e.read().decode()}"
        except Exception as e:
            return False, str(e)
    
    def convert_to_firestore_format(self, data):
        """Convert Python data to Firestore document format"""
        def convert_value(value):
            if isinstance(value, str):
                return {"stringValue": value}
            elif isinstance(value, bool):
                return {"booleanValue": value}
            elif isinstance(value, int):
                return {"integerValue": str(value)}
            elif isinstance(value, float):
                return {"doubleValue": value}
            elif isinstance(value, list):
                return {"arrayValue": {"values": [convert_value(item) for item in value]}}
            elif isinstance(value, dict):
                return {"mapValue": {"fields": {k: convert_value(v) for k, v in value.items()}}}
            else:
                return {"stringValue": str(value)}
        
        return {
            "fields": {k: convert_value(v) for k, v in data.items()}
        }
    
    def upload_all_candidates(self, candidates_file):
        """Upload all candidates from JSON file"""
        print(f"🚀 Uploading candidates to Firestore from {candidates_file}")
        print("-" * 60)
        
        try:
            with open(candidates_file, 'r') as f:
                candidates = json.load(f)
        except Exception as e:
            print(f"❌ Error loading candidates file: {e}")
            return False
        
        successful_uploads = 0
        failed_uploads = 0
        
        for i, candidate in enumerate(candidates):
            try:
                success, error = self.upload_candidate(candidate)
                
                if success:
                    successful_uploads += 1
                    print(f"✅ Uploaded {i+1}/{len(candidates)}: {candidate['name']} ({candidate['candidate_id']})")
                else:
                    failed_uploads += 1
                    print(f"❌ Failed {i+1}/{len(candidates)}: {candidate['name']} - {error}")
                
                # Small delay to avoid overwhelming the emulator
                time.sleep(0.1)
                
            except Exception as e:
                failed_uploads += 1
                print(f"❌ Error processing candidate {i+1}: {e}")
        
        print("\n📊 Upload Results:")
        print(f"   Successful uploads: {successful_uploads}")
        print(f"   Failed uploads: {failed_uploads}")
        print(f"   Total candidates: {len(candidates)}")
        
        return successful_uploads > 0

def main():
    """Main upload function"""
    candidates_file = SCRIPTS_DIR / "real_candidates_processed.json"
    
    if not candidates_file.exists():
        print(f"❌ Candidates file not found: {candidates_file}")
        print("Please run process_real_data.py first")
        sys.exit(1)
    
    uploader = FirestoreUploader()
    success = uploader.upload_all_candidates(str(candidates_file))
    
    if success:
        print("\n✅ Upload complete! Candidates are now in Firestore")
        print("\n🔄 Next steps:")
        print("1. Generate embeddings for semantic search")
        print("2. Test search functionality")
        print("3. Test frontend integration")
    else:
        print("\n❌ Upload failed")
        print("Make sure Firestore emulator is running:")
        print("firebase emulators:start --only firestore")

if __name__ == "__main__":
    main()