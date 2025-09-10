#!/usr/bin/env python3
"""
Verify data uploaded to Production Firestore
"""

import firebase_admin
from firebase_admin import credentials, firestore

def verify_firestore_data():
    """Verify uploaded candidates in production Firestore"""
    
    # Initialize Firebase Admin with Application Default Credentials
    if not firebase_admin._apps:
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {
            'projectId': 'headhunter-ai-0088'
        })
    
    db = firestore.client()
    
    # Get candidate count
    candidates_ref = db.collection('candidates')
    docs = list(candidates_ref.limit(10).stream())
    
    print(f"📊 Found {len(docs)} candidates (first 10):")
    
    for i, doc in enumerate(docs):
        data = doc.to_dict()
        print(f"{i+1}. {data.get('name', 'Unknown')} (ID: {doc.id})")
        print(f"   Score: {data.get('overall_score', 'N/A')}")
        print(f"   Uploaded: {data.get('uploaded_at', 'N/A')}")
        print()
    
    # Get total count (approximate)
    try:
        total_docs = candidates_ref.get()
        total_count = len(list(total_docs))
        print(f"🔢 Total candidates in Firestore: {total_count}")
    except Exception as e:
        print(f"❌ Error getting total count: {e}")
    
    return True

if __name__ == "__main__":
    print("🔍 Verifying Firestore data...")
    verify_firestore_data()