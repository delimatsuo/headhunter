#!/usr/bin/env python3
"""
Upload processed candidates to Production Firestore
"""

import json
import os
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

def upload_to_production_firestore():
    """Upload processed candidates to production Firestore"""
    
    # Initialize Firebase Admin with Application Default Credentials
    if not firebase_admin._apps:
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {
            'projectId': 'headhunter-ai-0088'
        })
    
    db = firestore.client()
    
    # Load processed candidates
    candidates_file = 'real_candidates_processed.json'
    if not os.path.exists(candidates_file):
        candidates_file = 'comprehensive_candidates_processed.json'
    
    if not os.path.exists(candidates_file):
        print("❌ No processed candidates file found")
        return False
    
    print(f"📂 Loading candidates from: {candidates_file}")
    
    # Read and parse candidates data
    with open(candidates_file, 'r', encoding='utf-8') as f:
        candidates_data = json.load(f)
    
    candidates_uploaded = 0
    batch_size = 10
    total_candidates = len(candidates_data)
    
    print(f"📊 Found {total_candidates} candidates to process")
    
    for i, candidate in enumerate(candidates_data[:50]):  # Upload first 50 for testing
        if i % 10 == 0:
            print(f"⏳ Processing {i}/{min(50, total_candidates)} candidates...")
        
        try:
            candidate_id = candidate.get('candidate_id')
            
            if not candidate_id:
                continue
                
            # Upload to candidates collection
            doc_ref = db.collection('candidates').document(candidate_id)
            
            # Convert to Firestore-friendly format
            firestore_data = {
                'candidate_id': candidate_id,
                'name': candidate.get('name', 'Unknown'),
                'overall_score': candidate.get('overall_score', 0.5),
                'resume_analysis': candidate.get('resume_analysis', {}),
                'recruiter_insights': candidate.get('recruiter_insights', {}),
                'processing_timestamp': candidate.get('processing_timestamp', datetime.now().isoformat()),
                'uploaded_at': firestore.SERVER_TIMESTAMP
            }
            
            # Upload document
            doc_ref.set(firestore_data)
            candidates_uploaded += 1
            
        except Exception as e:
            print(f"❌ Error uploading candidate {i}: {str(e)}")
            continue
    
    print(f"✅ Successfully uploaded {candidates_uploaded} candidates to production Firestore!")
    return True

if __name__ == "__main__":
    print("🚀 Starting upload to production Firestore...")
    success = upload_to_production_firestore()
    
    if success:
        print("🎉 Upload completed! Check your dashboard at https://headhunter-ai-0088.web.app")
    else:
        print("❌ Upload failed")