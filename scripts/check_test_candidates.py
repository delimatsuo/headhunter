#!/usr/bin/env python3
import firebase_admin
from firebase_admin import firestore

if not firebase_admin._apps:
    firebase_admin.initialize_app(options={'projectId': 'headhunter-ai-0088'})

db = firestore.client()

# Check for our test candidates
test_ids = ['sarah_chen', 'marcus_rodriguez', 'james_thompson', 'lisa_park', 'emily_watson', 'john_smith']

print("🔍 Checking for test candidates:")
for cid in test_ids:
    doc = db.collection('candidates').document(cid).get()
    if doc.exists:
        data = doc.to_dict()
        print(f"✅ {cid}: {data.get('name')} - {data.get('role_level')}")
    else:
        print(f"❌ {cid}: Not found")
