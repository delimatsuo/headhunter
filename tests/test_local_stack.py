#!/usr/bin/env python3
"""Integration tests for the local multi-tenant API stack."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict

import pytest

from scripts.run_integration import (
    HttpClient,
    SERVICE_URLS,
    execute_flow,
    extract_cache_flag,
    get_token,
)

BASE_ENDPOINTS = {
    "hh-embed-svc": "http://localhost:7101/health",
    "hh-search-svc": "http://localhost:7102/health",
    "hh-rerank-svc": "http://localhost:7103/health",
    "hh-evidence-svc": "http://localhost:7104/health",
    "hh-eco-svc": "http://localhost:7105/health",
    "hh-admin-svc": "http://localhost:7106/health",
    "hh-msgs-svc": "http://localhost:7107/health",
    "hh-enrich-svc": "http://localhost:7108/health",
    "mock-oauth": "http://localhost:8081/health",
    "mock-together": "http://localhost:7500/health",
}

SLA_TARGET_MS = 1200
RERANK_SLA_MS = 350
CACHED_READ_SLA_MS = 250
CACHE_HIT_RATE_TARGET = 0.7
TENANT_ID = os.getenv("TENANT_ID", "tenant-alpha")


def _ping(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status in {200, 204}
    except urllib.error.URLError:
        return False


@pytest.fixture(scope="module")
def ensure_stack_running() -> None:
    missing = [name for name, url in BASE_ENDPOINTS.items() if not _ping(url, timeout=2.0)]
    if missing:
        pytest.skip(f"Local stack not running for endpoints: {missing}")


@pytest.fixture(scope="module")
def integration_report(ensure_stack_running: None) -> Dict[str, Any]:
    start = time.perf_counter()
    report = execute_flow()
    elapsed = (time.perf_counter() - start) * 1000
    assert report["failed_steps"] == 0, f"Integration suite failures: {report}"
    assert report["tenant"] == TENANT_ID
    report["elapsedMs"] = elapsed
    return report


@pytest.fixture(scope="module")
def performance_report(integration_report: Dict[str, Any]) -> Dict[str, Any]:
    performance = integration_report.get("performance")
    assert performance is not None, "Performance summary missing"
    return performance


@pytest.mark.integration
def test_end_to_end_pipeline(integration_report: Dict[str, Any]) -> None:
    steps = integration_report["steps"]
    for key in [
        "enrich_submit",
        "enrich_wait",
        "embeddings_generate",
        "embeddings_upsert",
        "search_hybrid",
        "search_rerank",
        "evidence_retrieve",
    ]:
        assert steps[key]["status"] == "passed"
    search = steps["search_hybrid"]["data"]
    rerank = steps["search_rerank"]["data"]
    evidence = steps["evidence_retrieve"]["data"]
    assert search["timings"]["totalMs"] < SLA_TARGET_MS
    assert rerank["timings"]["totalMs"] < RERANK_SLA_MS
    assert len(evidence["sections"]) >= 1


@pytest.mark.integration
def test_admin_operations(integration_report: Dict[str, Any]) -> None:
    steps = integration_report["steps"]
    refresh = steps["admin_refresh"]["data"]
    monitor = steps["admin_monitor"]["data"]
    snapshots = steps["admin_snapshots"]["data"]

    assert refresh["postings"]["status"] in {"pending", "queued", "running", "completed"}
    assert refresh["profiles"]["status"] in {"pending", "queued", "running", "completed"}
    assert len(monitor["statuses"]) == 2
    assert snapshots["postingsLag"] >= 0
    assert snapshots["profilesLag"] >= 0


@pytest.mark.integration
def test_msgs_capabilities(integration_report: Dict[str, Any]) -> None:
    steps = integration_report["steps"]
    expand = steps["msgs_skill_expand"]["data"]
    template = steps["msgs_role_template"]["data"]
    demand = steps["msgs_market_demand"]["data"]

    assert expand["adjacent_count"] > 0
    assert expand["cacheHit"] is not None
    assert template["requiredSkills"] >= 1
    assert demand["points"] >= 4
    assert demand["trend"] in {"rising", "steady", "declining"}


@pytest.mark.integration
def test_eco_operations(integration_report: Dict[str, Any]) -> None:
    steps = integration_report["steps"]
    eco_search = steps["eco_search"]["data"]
    eco_detail = steps["eco_detail"]["data"]

    assert eco_search["total"] >= 1
    assert eco_detail["summary"]["aliases"] >= 0
    assert eco_detail["summary"]["industries"] >= 0


@pytest.mark.integration
def test_performance_profile(integration_report: Dict[str, Any]) -> None:
    stats = integration_report["stats"]
    assert stats["avgLatencyMs"] < SLA_TARGET_MS
    assert stats["p95LatencyMs"] < SLA_TARGET_MS
    assert integration_report["elapsedMs"] < SLA_TARGET_MS * len(integration_report["steps"])


@pytest.mark.integration
def test_performance_targets(performance_report: Dict[str, Any]) -> None:
    assert performance_report["stepLatencyP95Ms"] <= SLA_TARGET_MS
    rerank_latency = performance_report.get("rerankLatencyMs")
    assert rerank_latency is not None and rerank_latency <= RERANK_SLA_MS


@pytest.mark.integration
def test_cached_read_latency(performance_report: Dict[str, Any]) -> None:
    cached_latency = performance_report.get("cachedReadLatencyMs")
    assert cached_latency is not None, "Cached read probe missing"
    assert cached_latency <= CACHED_READ_SLA_MS
    assert performance_report.get("cachedReadSamples"), "Cached read samples missing"


@pytest.mark.integration
def test_cache_hit_rate_threshold(performance_report: Dict[str, Any]) -> None:
    cache_summary = performance_report.get("cache", {})
    hit_rate = cache_summary.get("hitRate")
    assert hit_rate is not None and hit_rate >= CACHE_HIT_RATE_TARGET
    observations = cache_summary.get("observations", [])
    assert observations, "No cache observations captured"
    assert any(obs.get("cacheHit") for obs in observations), "No cache hits recorded"


@pytest.mark.integration
def test_no_performance_issues(integration_report: Dict[str, Any]) -> None:
    assert not integration_report.get("issues"), integration_report.get("issues")


@pytest.mark.integration
def test_search_cache_hit(ensure_stack_running: None) -> None:
    token = get_token()
    client = HttpClient(token, TENANT_ID)

    payload = {
        "query": "cientista de dados",
        "limit": 3,
        "filters": {"skills": ["python"]},
    }

    first = client.request("POST", SERVICE_URLS["search"], "/v1/search/hybrid", payload)
    assert extract_cache_flag(first["data"]) is False

    second = client.request("POST", SERVICE_URLS["search"], "/v1/search/hybrid", payload)
    assert extract_cache_flag(second["data"]) is True


@pytest.mark.integration
def test_tenant_isolation_on_evidence(ensure_stack_running: None) -> None:
    token = get_token()
    client = HttpClient(token, TENANT_ID)
    payload = client.request("GET", SERVICE_URLS["evidence"], "/v1/evidence/cand-001")
    metadata = payload["data"].get("metadata", {})
    assert metadata.get("orgId") == TENANT_ID

    foreign = urllib.request.Request(
        f"http://localhost:8081/token",
        data=json.dumps({"tenant_id": "tenant-beta", "sub": "pytest"}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(foreign, timeout=5) as response_token:
        other_token = json.loads(response_token.read().decode("utf-8"))["access_token"]

    forbidden = urllib.request.Request(
        f"{SERVICE_URLS['evidence']}/v1/evidence/cand-001",
        method="GET",
        headers={
            "Authorization": f"Bearer {other_token}",
            "Accept": "application/json",
            "X-Tenant-ID": "tenant-beta",
        },
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(forbidden, timeout=5)
    assert exc.value.code in {403, 404}
