#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Verifies that inter-service communication across the local stack works as
# expected by executing the end-to-end flow and probing critical service hops.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf '[service-comm][error] Missing required command: %s\n' "$1" >&2
    exit 1
  fi
}

require_cmd python3

python3 - <<'PY'
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from scripts.run_integration import SERVICE_URLS, execute_flow, get_token, HttpClient, TENANT_ID

REPORT = {
    "search_to_embed": None,
    "search_to_rerank": None,
    "enrich_to_embed": None,
    "tenant_isolation": None,
    "unauthorized_access": None,
    "pipeline_summary": None,
    "issues": [],
}

try:
    summary = execute_flow()
except Exception as exc:  # noqa: BLE001
    REPORT["issues"].append(f"End-to-end flow failed: {exc}")
    print(json.dumps(REPORT, indent=2, sort_keys=True))
    sys.exit(1)

steps = summary.get("steps", {})

for key in ("enrich_submit", "enrich_wait", "embeddings_generate", "embeddings_upsert", "search_hybrid", "search_rerank", "evidence_retrieve"):
    result = steps.get(key, {})
    if result.get("status") != "passed":
        REPORT["issues"].append(f"Step {key} did not pass")

search_step = steps.get("search_hybrid", {})
rerank_step = steps.get("search_rerank", {})
embed_step = steps.get("embeddings_generate", {})

if search_step.get("status") == "passed" and embed_step.get("status") == "passed":
    REPORT["search_to_embed"] = {
        "searchLatencyMs": round(search_step.get("latency_ms", 0.0), 2),
        "embedProvider": embed_step.get("data", {}).get("provider"),
    }
else:
    REPORT["issues"].append("Search/embed linkage missing successful results")

if rerank_step.get("status") == "passed" and search_step.get("status") == "passed":
    REPORT["search_to_rerank"] = {
        "rerankLatencyMs": round(rerank_step.get("latency_ms", 0.0), 2),
        "topCandidateId": rerank_step.get("data", {}).get("top_candidate_id"),
    }
else:
    REPORT["issues"].append("Rerank step did not pass")

enrich_step = steps.get("enrich_submit", {})
if enrich_step.get("status") == "passed" and embed_step.get("status") == "passed":
    REPORT["enrich_to_embed"] = {
        "jobId": enrich_step.get("data", {}).get("job", {}).get("jobId") if isinstance(enrich_step.get("data"), dict) else None,
        "embedDimensions": embed_step.get("data", {}).get("dimensions"),
    }
else:
    REPORT["issues"].append("Enrichment workflow did not reach embedding generation")

REPORT["pipeline_summary"] = {
    "totalSteps": summary.get("stats", {}).get("totalSteps"),
    "elapsedMs": summary.get("performance", {}).get("totalRuntimeMs"),
    "p95Ms": summary.get("performance", {}).get("stepLatencyP95Ms"),
    "cacheHitRate": (summary.get("performance", {}).get("cache", {}) or {}).get("hitRate"),
}

# Additional probes -----------------------------------------------------

token = get_token()
client = HttpClient(token, TENANT_ID)

# Tenant isolation: request evidence with another tenant token
try:
    payload = json.dumps({"tenant_id": "tenant-beta", "sub": "integration"}).encode("utf-8")
    req = urllib.request.Request(
        f"{os.getenv('ISSUER_URL', 'http://localhost:8081').rstrip('/')}/token",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        other_token = json.loads(response.read().decode("utf-8")).get("access_token")
    evidence_url = f"{SERVICE_URLS['evidence']}/v1/evidence/integration-candidate"
    forbidden = urllib.request.Request(
        evidence_url,
        method="GET",
        headers={
            "Authorization": f"Bearer {other_token}",
            "Accept": "application/json",
            "X-Tenant-ID": "tenant-beta",
        },
    )
    urllib.request.urlopen(forbidden, timeout=5)
    REPORT["issues"].append("Cross-tenant evidence request unexpectedly succeeded")
except urllib.error.HTTPError as exc:
    REPORT["tenant_isolation"] = {"code": exc.code}
except Exception as exc:  # noqa: BLE001
    REPORT["issues"].append(f"Tenant isolation probe failed: {exc}")

# Unauthorized access: request search without credentials
try:
    search_url = f"{SERVICE_URLS['search']}/v1/search/hybrid"
    req = urllib.request.Request(
        search_url,
        data=json.dumps({"query": "test", "limit": 1}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=5)
    REPORT["issues"].append("Unauthenticated search request unexpectedly succeeded")
except urllib.error.HTTPError as exc:
    REPORT["unauthorized_access"] = {"code": exc.code}
except Exception as exc:  # noqa: BLE001
    REPORT["issues"].append(f"Unauthorized probe failed: {exc}")

print(json.dumps(REPORT, indent=2, sort_keys=True))

if REPORT["issues"]:
    sys.exit(1)
PY
