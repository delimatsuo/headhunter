#!/usr/bin/env python3
"""Verify test data in Firestore"""

import firebase_admin
from firebase_admin import credentials, firestore

PROJECT_ID = "headhunter-ai-0088"

def main():
    # Initialize
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={'projectId': PROJECT_ID})

    db = firestore.client()

    # Query candidates
    docs = db.collection('candidates').limit(10).stream()

    print("📊 Candidates in Firestore:")
    print("=" * 60)

    count = 0
    for doc in docs:
        data = doc.to_dict()
        count += 1
        print(f"\n{count}. ID: {doc.id}")
        print(f"   Name: {data.get('name')}")
        print(f"   Role: {data.get('role_level')}")
        print(f"   Tenant: {data.get('tenant_id')}")
        print(f"   Status: {data.get('status')}")

    print(f"\n✅ Total candidates found: {count}")

if __name__ == "__main__":
    main()
