#!/usr/bin/env python3
"""
Monitor Cloud Run service performance for Phase 2.

Periodically polls /health and /metrics, tracks latency p95, error rates,
and emits alerts if thresholds are exceeded.
"""

import argparse
import json
import time
from collections import deque
from typing import Deque, Dict, Any, Optional

import requests

try:
    from google.oauth2 import id_token
    from google.auth.transport import requests as grequests
    _GOOGLE_AUTH_AVAILABLE = True
except Exception:
    _GOOGLE_AUTH_AVAILABLE = False


def get_id_token(audience: str) -> Optional[str]:
    if not _GOOGLE_AUTH_AVAILABLE:
        return None
    req = grequests.Request()
    return id_token.fetch_id_token(req, audience)


def http_get(url: str, audience: Optional[str] = None, timeout: float = 10.0) -> requests.Response:
    headers = {}
    if audience:
        tok = get_id_token(audience)
        if tok:
            headers["Authorization"] = f"Bearer {tok}"
    return requests.get(url, headers=headers, timeout=timeout)


def p95(latencies):
    if not latencies:
        return None
    data = sorted(latencies)
    k = max(0, int(round(0.95 * (len(data) - 1))))
    return data[k]


def main():
    parser = argparse.ArgumentParser(description="Monitor Cloud Run performance")
    parser.add_argument("--url", required=True, help="Base URL of the service")
    parser.add_argument("--audience", default=None, help="Audience for ID token (service URL)")
    parser.add_argument("--interval", type=float, default=5.0, help="Polling interval seconds")
    parser.add_argument("--duration", type=float, default=120.0, help="Total monitoring duration seconds")
    parser.add_argument("--p95", type=float, default=1.2, help="Target p95 (seconds)")
    parser.add_argument("--error-rate", type=float, default=0.1, help="Error rate alert threshold")
    args = parser.parse_args()

    t_end = time.time() + args.duration
    health_lat: Deque[float] = deque(maxlen=200)
    metrics_lat: Deque[float] = deque(maxlen=200)
    errors = 0
    total = 0

    while time.time() < t_end:
        for path, store in (("/health", health_lat), ("/metrics", metrics_lat)):
            url = f"{args.url}{path}"
            t0 = time.perf_counter()
            try:
                r = http_get(url, args.audience)
                dt = time.perf_counter() - t0
                store.append(dt)
                total += 1
                if not r.ok:
                    errors += 1
                print(json.dumps({"path": path, "code": r.status_code, "latency_s": dt}))
            except Exception as e:
                dt = time.perf_counter() - t0
                store.append(dt)
                total += 1
                errors += 1
                print(json.dumps({"path": path, "error": str(e), "latency_s": dt}))

        time.sleep(args.interval)

    rep = {
        "health_p95_s": p95(list(health_lat)),
        "metrics_p95_s": p95(list(metrics_lat)),
        "error_rate": (errors / total) if total else None,
        "thresholds": {"p95_s": args.p95, "error_rate": args.error_rate},
        "alerts": [],
    }
    if rep["health_p95_s"] and rep["health_p95_s"] > args.p95:
        rep["alerts"].append("health p95 exceeded")
    if rep["metrics_p95_s"] and rep["metrics_p95_s"] > args.p95:
        rep["alerts"].append("metrics p95 exceeded")
    if rep["error_rate"] and rep["error_rate"] > args.error_rate:
        rep["alerts"].append("error rate exceeded")

    print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()

