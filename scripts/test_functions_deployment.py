#!/usr/bin/env python3
"""
Validate deployed Firebase Functions by invoking the healthCheck callable.

This script locates the function URL via gcloud and performs an HTTP POST
using the callable protocol body shape {"data": {...}}. It verifies that
the response indicates a healthy status and reports details.

Usage:
  python scripts/test_functions_deployment.py --project-id <PROJECT_ID> --region us-central1
"""

import argparse
import json
import subprocess
import sys
import urllib.request
import urllib.error


def run(cmd: list[str]) -> tuple[int, str, str]:
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate()
    return p.returncode, out.strip(), err.strip()


def get_function_url(name: str, region: str) -> str | None:
    code, out, err = run(["gcloud", "functions", "list", "--region", region, "--format", "json"])
    if code != 0:
        print(f"❌ Failed to list functions: {err}")
        return None
    try:
        items = json.loads(out or "[]")
        for fn in items:
            if fn.get("name", "").endswith(f"/locations/{region}/functions/{name}"):
                # Gen2 lists httpsTrigger.url
                url = (fn.get("httpsTrigger") or {}).get("url")
                if url:
                    return url
        # Fallback: if names don't include region suffix, try by displayName
        for fn in items:
            if fn.get("displayName") == name:
                url = (fn.get("httpsTrigger") or {}).get("url")
                if url:
                    return url
    except Exception as e:  # noqa: BLE001
        print(f"❌ Could not parse functions list: {e}")
    return None


def call_callable(url: str) -> tuple[bool, dict | None, str | None]:
    body = {"data": {}}
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            try:
                payload = json.loads(raw)
            except Exception:
                return False, None, f"Non-JSON response: {raw[:200]}"
            return True, payload, None
    except urllib.error.HTTPError as e:
        return False, None, f"HTTPError: {e.code} {e.reason}"
    except urllib.error.URLError as e:
        return False, None, f"URLError: {e.reason}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--region", default="us-central1")
    args = ap.parse_args()

    # Ensure correct project is active
    rc, _, err = run(["gcloud", "config", "set", "project", args.project_id])
    if rc != 0:
        print(f"❌ gcloud project set failed: {err}")
        return 2

    url = get_function_url("healthCheck", args.region)
    if not url:
        print("❌ Could not find healthCheck function URL. Ensure it is deployed.")
        return 3

    ok, payload, err = call_callable(url)
    if not ok:
        print(f"❌ healthCheck call failed: {err}")
        return 4

    # Firebase callable wraps response as { result: ... } for some runtimes.
    result = payload.get("result", payload)
    status = (result or {}).get("status")

    if status == "healthy":
        print("✅ healthCheck reports healthy")
        print(json.dumps(result, indent=2))
        return 0
    else:
        print("❌ healthCheck did not return healthy status")
        print(json.dumps(payload, indent=2))
        return 5


if __name__ == "__main__":
    sys.exit(main())

