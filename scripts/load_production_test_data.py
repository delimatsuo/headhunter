#!/usr/bin/env python3
"""
Load test candidates into production Firestore via API Gateway
"""

import csv
import json
import os
import sys
import requests
from pathlib import Path
from typing import Dict, Any, List

# Configuration
API_GATEWAY_URL = "https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev"
PROJECT_ID = "headhunter-ai-0088"
TENANT_ID = "test-tenant"

def get_api_key() -> str:
    """Get API key from environment or Secret Manager"""
    api_key = os.environ.get("API_GATEWAY_KEY")
    if not api_key:
        print("⚠️  API_GATEWAY_KEY not set, fetching from Secret Manager...")
        import subprocess
        result = subprocess.run(
            ["gcloud", "secrets", "versions", "access", "latest",
             "--secret=api-gateway-key", f"--project={PROJECT_ID}"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"❌ Failed to get API key: {result.stderr}")
            sys.exit(1)
        api_key = result.stdout.strip()
    return api_key

def read_resume(resume_path: Path) -> str:
    """Read resume content from file"""
    if not resume_path.exists():
        return f"Resume file not found: {resume_path}"

    if resume_path.suffix == '.txt':
        return resume_path.read_text()
    elif resume_path.suffix == '.pdf':
        # For PDF, return a placeholder - actual PDF parsing would need PyPDF2
        return f"[PDF Resume: {resume_path.name}] - Content extraction not implemented"
    elif resume_path.suffix == '.docx':
        # For DOCX, return a placeholder - actual parsing would need python-docx
        return f"[DOCX Resume: {resume_path.name}] - Content extraction not implemented"
    elif resume_path.suffix == '.png':
        # For images, return a placeholder
        return f"[Image Resume: {resume_path.name}] - OCR not implemented"
    else:
        return f"Unsupported resume format: {resume_path.suffix}"

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
                "candidateId": row['candidate_id'],
                "name": row['name'],
                "roleLevel": row['role_level'],
                "resumeText": resume_content,
                "recruiterComments": row['recruiter_comments'],
                "tenantId": TENANT_ID
            }
            candidates.append(candidate)

    return candidates

def upload_candidate(api_key: str, candidate: Dict[str, Any]) -> tuple[bool, str]:
    """Upload a candidate via API Gateway to embed service"""
    url = f"{API_GATEWAY_URL}/v1/candidates"

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
        "X-Tenant-ID": TENANT_ID
    }

    try:
        response = requests.post(url, json=candidate, headers=headers, timeout=30)

        if response.status_code in [200, 201]:
            return True, "Success"
        else:
            return False, f"HTTP {response.status_code}: {response.text}"

    except requests.exceptions.RequestException as e:
        return False, f"Request failed: {str(e)}"

def main():
    """Main upload function"""
    print("🚀 Loading test data into production Firestore")
    print("=" * 60)

    # Get API key
    api_key = get_api_key()
    print(f"✅ API key retrieved (length: {len(api_key)})")

    # Load candidates from CSV
    csv_path = Path(__file__).parent.parent / "datasets" / "csv" / "sample_candidates.csv"
    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_path}")
        sys.exit(1)

    candidates = load_candidates_from_csv(csv_path)
    print(f"📊 Loaded {len(candidates)} candidates from CSV")
    print()

    # Upload candidates
    successful = 0
    failed = 0

    for i, candidate in enumerate(candidates, 1):
        print(f"⏳ [{i}/{len(candidates)}] Uploading {candidate['name']}...", end=" ")
        success, message = upload_candidate(api_key, candidate)

        if success:
            successful += 1
            print("✅")
        else:
            failed += 1
            print(f"❌ {message}")

    print()
    print("=" * 60)
    print("📊 Upload Results:")
    print(f"   ✅ Successful: {successful}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📈 Total: {len(candidates)}")

    if successful > 0:
        print()
        print("🎉 Test data loaded successfully!")
        print()
        print("📝 Next steps:")
        print("1. Verify candidates in Firestore")
        print("2. Check embeddings in pgvector")
        print("3. Run search smoke tests")
    else:
        print()
        print("❌ No candidates were uploaded successfully")
        print("Check API Gateway logs for errors")
        sys.exit(1)

if __name__ == "__main__":
    main()
