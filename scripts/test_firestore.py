
import firebase_admin
from firebase_admin import credentials, firestore
import os

if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app()
        print("Initialized Firebase with default credentials")
    except:
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {'projectId': 'headhunter-ai-0088'})
        print("Initialized Firebase with application default credentials")

db = firestore.client()
candidate_id = "190484564"
doc_ref = db.collection("candidates").document(candidate_id)
doc = doc_ref.get()

if doc.exists:
    print(f"Found candidate: {doc.to_dict().get('name', 'Unknown')}")
    print(f"Data keys: {list(doc.to_dict().keys())}")
else:
    print("Candidate not found")
