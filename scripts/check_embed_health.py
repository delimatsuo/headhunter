#!/usr/bin/env python3
"""Check embed service health"""

import subprocess
import http.client
import json

def get_auth_token():
    result = subprocess.run(
        ["gcloud", "auth", "print-identity-token"],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()

token = get_auth_token()
conn = http.client.HTTPSConnection("hh-embed-svc-production-akcoqbr7sa-uc.a.run.app")

headers = {
    "Authorization": f"Bearer {token}",
    "X-Tenant-ID": "tenant-alpha"
}

print("Checking /health endpoint")
print("=" * 80)

conn.request("GET", "/health", headers=headers)
response = conn.getresponse()
data = response.read().decode()

print(f"Status: {response.status}")
print(f"Response: {data}")
conn.close()

# Check /readyz endpoint
print("\n\nChecking /readyz endpoint")
print("=" * 80)

conn = http.client.HTTPSConnection("hh-embed-svc-production-akcoqbr7sa-uc.a.run.app")
conn.request("GET", "/readyz", headers=headers)
response = conn.getresponse()
data = response.read().decode()

print(f"Status: {response.status}")
print(f"Response: {data}")
conn.close()
