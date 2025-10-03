#!/usr/bin/env python3
"""
Load test candidates directly into production Firestore and pgvector
Uses Firebase Admin SDK for direct access
"""

import csv
import sys
from pathlib import Path
from typing import Dict, Any, List
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.sql.connector import Connector
import pg8000
import json

# Configuration
PROJECT_ID = "headhunter-ai-0088"
TENANT_ID = "test-tenant"
CLOUD_SQL_INSTANCE = "headhunter-ai-0088:us-central1:sql-hh-core"
DB_NAME = "headhunter"
DB_USER = "headhunter-app"

def init_firestore():
    """Initialize Firebase Admin SDK"""
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={
            'projectId': PROJECT_ID
        })
    return firestore.client()

def read_resume(resume_path: Path) -> str:
    """Read resume content from file"""
    if not resume_path.exists():
        return f"Resume file not found: {resume_path}"

    if resume_path.suffix == '.txt':
        return resume_path.read_text()
    else:
        # For non-text files, return placeholder
        return f"[{resume_path.suffix.upper()[1:]} Resume: {resume_path.name}]"

def load_candidates_from_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """Load candidates from CSV file"""
    candidates = []
    repo_root = csv_path.parent.parent

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            resume_path = repo_root / row['resume_file']
            resume_content = read_resume(resume_path)

            candidate = {
                "candidate_id": row['candidate_id'],
                "name": row['name'],
                "role_level": row['role_level'],
                "resume_text": resume_content,
                "recruiter_comments": row['recruiter_comments'],
                "tenant_id": TENANT_ID,
                "status": "active",
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP
            }
            candidates.append(candidate)

    return candidates

def upload_to_firestore(db, candidates: List[Dict[str, Any]]) -> int:
    """Upload candidates to Firestore"""
    successful = 0

    for candidate in candidates:
        try:
            doc_ref = db.collection('candidates').document(candidate['candidate_id'])
            doc_ref.set(candidate)
            successful += 1
            print(f"✅ Firestore: {candidate['name']}")
        except Exception as e:
            print(f"❌ Firestore failed for {candidate['name']}: {e}")

    return successful

def get_db_password() -> str:
    """Get database password from Secret Manager"""
    import subprocess
    result = subprocess.run(
        ["gcloud", "secrets", "versions", "access", "latest",
         "--secret=db-primary-password", f"--project={PROJECT_ID}"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"❌ Failed to get DB password: {result.stderr}")
        sys.exit(1)
    return result.stdout.strip()

def upload_to_pgvector(candidates: List[Dict[str, Any]]) -> int:
    """Upload candidate metadata to pgvector (embeddings will be generated separately)"""
    db_password = get_db_password()
    connector = Connector()

    def getconn():
        return connector.connect(
            CLOUD_SQL_INSTANCE,
            "pg8000",
            user=DB_USER,
            password=db_password,
            db=DB_NAME
        )

    successful = 0

    try:
        conn = getconn()
        cursor = conn.cursor()

        # Create table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                candidate_id VARCHAR(255) PRIMARY KEY,
                tenant_id VARCHAR(255) NOT NULL,
                name VARCHAR(500),
                role_level VARCHAR(100),
                status VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert candidates
        for candidate in candidates:
            try:
                cursor.execute("""
                    INSERT INTO candidates (candidate_id, tenant_id, name, role_level, status)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (candidate_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        role_level = EXCLUDED.role_level,
                        status = EXCLUDED.status,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    candidate['candidate_id'],
                    candidate['tenant_id'],
                    candidate['name'],
                    candidate['role_level'],
                    'active'
                ))
                successful += 1
                print(f"✅ pgvector: {candidate['name']}")
            except Exception as e:
                print(f"❌ pgvector failed for {candidate['name']}: {e}")

        conn.commit()
        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ pgvector connection error: {e}")
    finally:
        connector.close()

    return successful

def main():
    """Main upload function"""
    print("🚀 Loading test data into production")
    print("=" * 60)

    # Initialize Firestore
    print("📦 Initializing Firestore...")
    db = init_firestore()
    print("✅ Firestore connected")

    # Load candidates from CSV
    csv_path = Path(__file__).parent.parent / "datasets" / "csv" / "sample_candidates.csv"
    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_path}")
        sys.exit(1)

    candidates = load_candidates_from_csv(csv_path)
    print(f"📊 Loaded {len(candidates)} candidates from CSV")
    print()

    # Upload to Firestore
    print("⏳ Uploading to Firestore...")
    firestore_count = upload_to_firestore(db, candidates)
    print()

    # Upload to pgvector
    print("⏳ Uploading to pgvector...")
    pgvector_count = upload_to_pgvector(candidates)
    print()

    # Summary
    print("=" * 60)
    print("📊 Upload Results:")
    print(f"   Firestore: {firestore_count}/{len(candidates)} successful")
    print(f"   pgvector:  {pgvector_count}/{len(candidates)} successful")

    if firestore_count > 0 and pgvector_count > 0:
        print()
        print("🎉 Test data loaded successfully!")
        print()
        print("📝 Next steps:")
        print("1. Generate embeddings (call hh-embed-svc)")
        print("2. Run search smoke tests")
        print("3. Verify rerank cache")
    else:
        print()
        print("❌ Some uploads failed - check logs above")
        sys.exit(1)

if __name__ == "__main__":
    main()
