#!/usr/bin/env python3
"""Check service health endpoints"""

import subprocess
import http.client
import json

def get_auth_token():
    result = subprocess.run(
        ["gcloud", "auth", "print-identity-token"],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()

def check_health(service_url, token):
    """Check service health"""
    conn = http.client.HTTPSConnection(service_url)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": "tenant-alpha"
    }

    print(f"\nChecking {service_url}/health/detailed")
    print("=" * 80)

    try:
        conn.request("GET", "/health/detailed", headers=headers)
        response = conn.getresponse()
        data = response.read().decode()

        print(f"Status: {response.status}")
        if response.status == 200:
            result = json.loads(data)
            print(json.dumps(result, indent=2))
        else:
            print(f"Response: {data}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    token = get_auth_token()

    check_health("hh-embed-svc-production-akcoqbr7sa-uc.a.run.app", token)
    check_health("hh-search-svc-production-akcoqbr7sa-uc.a.run.app", token)
