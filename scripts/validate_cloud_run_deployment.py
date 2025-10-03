#!/usr/bin/env python3
"""
Validate a deployed Cloud Run service for Phase 2.

Checks:
- /health returns healthy/degraded and component statuses
- /metrics returns counters and rates
- /process/batch with provided candidate IDs runs end-to-end
- Measures response times and computes p95 latency
- Optional Firestore validation of enrich results
"""

import argparse
import json
import time
from typing import List, Dict, Any, Optional

import requests

try:
    from google.oauth2 import id_token
    from google.auth.transport import requests as grequests
    _GOOGLE_AUTH_AVAILABLE = True
except Exception:
    _GOOGLE_AUTH_AVAILABLE = False

try:
    from google.cloud import firestore  # Optional for Firestore validation
    _FIRESTORE_AVAILABLE = True
except Exception:
    _FIRESTORE_AVAILABLE = False


def get_id_token(audience: str) -> Optional[str]:
    if not _GOOGLE_AUTH_AVAILABLE:
        return None
    req = grequests.Request()
    return id_token.fetch_id_token(req, audience)


def http_get(url: str, auth_audience: Optional[str] = None, timeout: float = 15.0) -> requests.Response:
    headers = {}
    if auth_audience:
        token = get_id_token(auth_audience)
        if token:
            headers["Authorization"] = f"Bearer {token}"
    return requests.get(url, headers=headers, timeout=timeout)


def http_post(url: str, payload: Dict[str, Any], auth_audience: Optional[str] = None, timeout: float = 60.0) -> requests.Response:
    headers = {"Content-Type": "application/json"}
    if auth_audience:
        token = get_id_token(auth_audience)
        if token:
            headers["Authorization"] = f"Bearer {token}"
    return requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)


def p95(latencies: List[float]) -> Optional[float]:
    if not latencies:
        return None
    data = sorted(latencies)
    k = max(0, int(round(0.95 * (len(data) - 1))))
    return data[k]


def validate_health(base_url: str, audience: Optional[str]) -> Dict[str, Any]:
    url = f"{base_url}/health"
    t0 = time.perf_counter()
    resp = http_get(url, audience)
    dt = time.perf_counter() - t0
    status = "pass" if resp.ok else "fail"
    body = {}
    try:
        body = resp.json()
    except Exception:
        pass
    return {"endpoint": "/health", "status": status, "code": resp.status_code, "latency_s": dt, "body": body}


def validate_metrics(base_url: str, audience: Optional[str]) -> Dict[str, Any]:
    url = f"{base_url}/metrics"
    t0 = time.perf_counter()
    resp = http_get(url, audience)
    dt = time.perf_counter() - t0
    status = "pass" if resp.ok else "fail"
    body = {}
    try:
        body = resp.json()
    except Exception:
        pass
    return {"endpoint": "/metrics", "status": status, "code": resp.status_code, "latency_s": dt, "body": body}


def run_batch(base_url: str, audience: Optional[str], candidate_ids: List[str]) -> Dict[str, Any]:
    url = f"{base_url}/process/batch"
    payload = {"candidate_ids": candidate_ids}
    t0 = time.perf_counter()
    resp = http_post(url, payload, audience, timeout=300)
    dt = time.perf_counter() - t0
    status = "pass" if resp.ok else "fail"
    body = {}
    try:
        body = resp.json()
    except Exception as e:
        body = {"error": str(e), "text": resp.text[:500]}
    return {"endpoint": "/process/batch", "status": status, "code": resp.status_code, "latency_s": dt, "body": body}


def verify_firestore_updates(candidate_ids: List[str], project_id: Optional[str], collection: str = "candidates") -> Dict[str, Any]:
    if not _FIRESTORE_AVAILABLE:
        return {"enabled": False, "reason": "google-cloud-firestore not available"}
    client = firestore.Client(project=project_id) if project_id else firestore.Client()
    results = {}
    ok = True
    for cid in candidate_ids:
        doc = client.collection(collection).document(cid).get()
        exists = doc.exists
        data = doc.to_dict() if exists else None
        enriched = bool(data and data.get("status") == "enriched")
        results[cid] = {"exists": exists, "status": data.get("status") if data else None, "enriched": enriched}
        ok = ok and enriched
    return {"enabled": True, "ok": ok, "details": results}


def main():
    parser = argparse.ArgumentParser(description="Validate Cloud Run Phase 2 deployment")
    parser.add_argument("--url", required=True, help="Base URL of the Cloud Run service")
    parser.add_argument("--audience", default=None, help="Audience for ID token (usually the service URL)")
    parser.add_argument("--candidates", nargs="*", help="Candidate IDs to process in batch")
    parser.add_argument("--project-id", default=None, help="GCP project for Firestore validation")
    parser.add_argument("--collection", default="candidates", help="Firestore collection name")
    parser.add_argument("--latency-p95", type=float, default=1.2, help="Target p95 response time in seconds")
    args = parser.parse_args()

    health_runs = []
    metrics_runs = []

    # Warm-up and measure a few samples
    for _ in range(3):
        health_runs.append(validate_health(args.url, args.audience))
        metrics_runs.append(validate_metrics(args.url, args.audience))

    health_lat = [r["latency_s"] for r in health_runs]
    metrics_lat = [r["latency_s"] for r in metrics_runs]

    report: Dict[str, Any] = {
        "summary": {
            "target_p95_s": args.latency_p95,
            "health_p95_s": p95(health_lat),
            "metrics_p95_s": p95(metrics_lat),
        },
        "health_checks": health_runs,
        "metrics_checks": metrics_runs,
    }

    if args.candidates:
        batch_result = run_batch(args.url, args.audience, args.candidates)
        report["batch_result"] = batch_result
        if batch_result.get("status") == "pass":
            body = batch_result.get("body", {})
            report["batch_summary"] = {
                "total": body.get("total_candidates"),
                "successful": body.get("successful"),
                "failed": body.get("failed"),
            }
            # Optional Firestore validation
            fs_verify = verify_firestore_updates(args.candidates, args.project_id, args.collection)
            report["firestore_validation"] = fs_verify

    # Overall status
    overall = "pass"
    for r in health_runs + metrics_runs:
        if r["status"] != "pass":
            overall = "fail"
            break
    report["overall_status"] = overall

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()

