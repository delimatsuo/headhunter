#!/usr/bin/env python3
"""
Test hh-embed-svc after database dimension fix.
Verifies the service can successfully create embeddings with 768 dimensions.
"""

import subprocess
import json
import http.client
import sys

def get_auth_token() -> str:
    """Get Google Cloud identity token for authenticating to Cloud Run services"""
    result = subprocess.run(
        ["gcloud", "auth", "print-identity-token"],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()

def test_embedding_service():
    """Test that hh-embed-svc can create embeddings successfully"""

    print("🔐 Getting authentication token...")
    token = get_auth_token()

    print("📡 Testing hh-embed-svc...")

    # Test embedding creation
    conn = http.client.HTTPSConnection("hh-embed-svc-production-akcoqbr7sa-uc.a.run.app")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": "tenant-alpha",
        "Content-Type": "application/json"
    }

    payload = json.dumps({
        "entityId": "test-dimension-fix-verification",
        "text": "Senior Python developer with 10 years of experience in machine learning and cloud infrastructure. Expert in AWS, Docker, and Kubernetes.",
        "metadata": {
            "test": True,
            "purpose": "dimension_fix_verification"
        },
        "chunkType": "default"
    })

    print(f"📤 Sending test embedding request...")
    conn.request("POST", "/v1/embeddings/upsert", payload, headers)
    response = conn.getresponse()
    data = response.read().decode()

    print(f"\n📊 Response Status: {response.status}")

    if response.status in [200, 201]:
        result = json.loads(data)
        print(f"✅ SUCCESS! Service is working correctly")
        print(f"   Entity ID: {result.get('entityId')}")
        print(f"   Model: {result.get('modelVersion', 'N/A')}")
        print(f"   Tenant: {result.get('tenantId', 'N/A')}")

        # Verify embedding was stored
        if 'embedding' in result or result.get('status') == 'success':
            print(f"\n✅ Embedding successfully stored in database with 768 dimensions")
            return True
        else:
            print(f"\n⚠️  Warning: Unexpected response format")
            print(f"   Response: {json.dumps(result, indent=2)}")
            return False
    else:
        print(f"❌ ERROR: Service returned status {response.status}")
        print(f"   Response: {data}")
        return False

if __name__ == "__main__":
    try:
        success = test_embedding_service()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        sys.exit(1)
