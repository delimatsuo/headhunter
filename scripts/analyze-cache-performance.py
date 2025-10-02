#!/usr/bin/env python3
"""Analyze cache performance across local services."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from run_integration import (  # type: ignore[import-untyped]
    CACHE_HIT_RATE_TARGET,
    SERVICE_URLS,
    TENANT_ID,
    compute_percentile,
    execute_flow,
    extract_cache_flag,
    get_token,
    HttpClient,
)


@dataclass
class ScenarioDefinition:
    name: str
    service: str
    method: str
    path: str
    payload: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, Any]] = None
    warmups: int = 1


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze cache hit rates across services")
    parser.add_argument("--samples", type=int, default=5, help="Number of measured requests per scenario")
    parser.add_argument("--report", type=Path, help="Optional file to store JSON results")
    return parser.parse_args(argv)


def build_scenarios(baseline: Dict[str, Any]) -> List[ScenarioDefinition]:
    steps = baseline.get("steps", {})
    rerank_data = steps.get("search_rerank", {}).get("data", {})
    search_results = rerank_data.get("results") or []

    rerank_payload = None
    if search_results:
        condensed = []
        for item in search_results[:5]:
            condensed.append(
                {
                    "candidateId": item.get("candidateId"),
                    "summary": item.get("headline") or item.get("title"),
                    "initialScore": float(item.get("score", 0)),
                    "features": item.get("features", {}),
                    "payload": item.get("metadata", {}),
                }
            )
        rerank_payload = {
            "jobDescription": "Buscamos Cientista de Dados senior para liderar iniciativas de IA.",
            "query": "cientista de dados senior",
            "candidates": condensed,
            "limit": 5,
            "includeReasons": True,
        }

    eco_id = steps.get("eco_search", {}).get("data", {}).get("primary_eco_id")
    cached_candidate = rerank_data.get("top_candidate_id")

    scenarios: List[ScenarioDefinition] = [
        ScenarioDefinition(
            name="search-hybrid",
            service="search",
            method="POST",
            path="/v1/search/hybrid",
            payload={
                "query": "engenheiro de software",
                "limit": 5,
                "filters": {"skills": ["python"], "locations": ["Sao Paulo"]},
                "includeDebug": True,
            },
        ),
        ScenarioDefinition(
            name="eco-search",
            service="eco",
            method="GET",
            path="/v1/occupations/search",
            params={"title": "engenheiro de software", "locale": "pt-BR", "limit": 5},
        ),
    ]

    if eco_id:
        scenarios.append(
            ScenarioDefinition(
                name="eco-detail",
                service="eco",
                method="GET",
                path=f"/v1/occupations/{eco_id}",
                params={"locale": "pt-BR"},
            )
        )

    if rerank_payload is not None:
        scenarios.append(
            ScenarioDefinition(
                name="rerank",
                service="rerank",
                method="POST",
                path="/v1/search/rerank",
                payload=rerank_payload,
            )
        )

    if cached_candidate:
        scenarios.append(
            ScenarioDefinition(
                name="evidence",
                service="evidence",
                method="GET",
                path=f"/v1/evidence/{cached_candidate}",
            )
        )

    scenarios.extend(
        [
            ScenarioDefinition(
                name="msgs-skill-expand",
                service="msgs",
                method="POST",
                path="/v1/skills/expand",
                payload={"skillId": "python", "topK": 5, "includeRelatedRoles": True},
            ),
            ScenarioDefinition(
                name="msgs-role-template",
                service="msgs",
                method="POST",
                path="/v1/roles/template",
                payload={"ecoId": eco_id or "eco-1", "locale": "pt-BR", "includeDemand": True},
            ),
        ]
    )

    return scenarios


def execute_scenario(
    client: HttpClient,
    scenario: ScenarioDefinition,
    samples: int,
) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    hits = 0
    misses = 0

    total_iterations = scenario.warmups + samples
    base_url = SERVICE_URLS[scenario.service]

    for idx in range(1, total_iterations + 1):
        response = client.request(
            scenario.method,
            base_url,
            scenario.path,
            payload=scenario.payload,
            params=scenario.params,
        )
        cache_flag = extract_cache_flag(response["data"])
        record = {
            "iteration": idx,
            "latencyMs": round(response["latency_ms"], 2),
            "cacheHit": cache_flag,
            "measured": idx > scenario.warmups,
        }
        if idx > scenario.warmups:
            results.append(record)
            if cache_flag is True:
                hits += 1
            elif cache_flag is False:
                misses += 1
        else:
            # warmup iteration for caching
            pass

    hit_rate = round(hits / (hits + misses), 3) if (hits + misses) else None
    hit_latencies = [item["latencyMs"] for item in results if item.get("cacheHit") is True]
    miss_latencies = [item["latencyMs"] for item in results if item.get("cacheHit") is False]

    metrics = {
        "hitRate": hit_rate,
        "hits": hits,
        "misses": misses,
        "hitLatency": {
            "count": len(hit_latencies),
            "avg": round(mean(hit_latencies), 2) if hit_latencies else None,
            "p95": compute_percentile(hit_latencies, 95) if hit_latencies else None,
        },
        "missLatency": {
            "count": len(miss_latencies),
            "avg": round(mean(miss_latencies), 2) if miss_latencies else None,
            "p95": compute_percentile(miss_latencies, 95) if miss_latencies else None,
        },
    }

    return {
        "name": scenario.name,
        "service": scenario.service,
        "metrics": metrics,
        "samples": results,
    }


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    token = get_token()
    client = HttpClient(token, TENANT_ID)

    print("[analyze-cache-performance] Running baseline pipeline warm-up")
    baseline_report = execute_flow()
    scenarios = build_scenarios(baseline_report)

    if not scenarios:
        print("[analyze-cache-performance] No scenarios available", file=sys.stderr)
        return 1

    scenario_reports: List[Dict[str, Any]] = []
    total_hits = 0
    total_misses = 0
    issues: List[str] = []

    for scenario in scenarios:
        print(f"[analyze-cache-performance] Measuring {scenario.name}")
        report = execute_scenario(client, scenario, args.samples)
        scenario_reports.append(report)
        metrics = report["metrics"]
        hits = metrics.get("hits", 0)
        misses = metrics.get("misses", 0)
        total_hits += hits
        total_misses += misses
        hit_rate = metrics.get("hitRate")
        if hit_rate is not None and hit_rate < CACHE_HIT_RATE_TARGET:
            issues.append(
                f"Scenario {scenario.name} hitRate={hit_rate} below target {CACHE_HIT_RATE_TARGET:.2f}"
            )

    overall_hit_rate = round(total_hits / (total_hits + total_misses), 3) if (total_hits + total_misses) else None
    if overall_hit_rate is not None and overall_hit_rate < CACHE_HIT_RATE_TARGET:
        issues.append(
            f"Overall cache hit rate {overall_hit_rate:.2f} below target {CACHE_HIT_RATE_TARGET:.2f}"
        )

    recommendations: List[str] = []
    for entry in scenario_reports:
        metrics = entry["metrics"]
        hit_rate = metrics.get("hitRate")
        if hit_rate is None:
            recommendations.append(
                f"Scenario {entry['name']} did not expose a cache flag; ensure service returns cache metadata"
            )
        elif hit_rate < CACHE_HIT_RATE_TARGET:
            recommendations.append(
                f"Increase cache warming or adjust TTLs for {entry['name']} (hitRate={hit_rate})."
            )

    if overall_hit_rate is not None and overall_hit_rate < CACHE_HIT_RATE_TARGET:
        recommendations.append(
            "Review Redis sizing and confirm frequent queries are stored with sufficient TTL values."
        )

    report = {
        "tenant": TENANT_ID,
        "baseline": {
            "completedSteps": baseline_report.get("completed_steps"),
            "issues": baseline_report.get("issues", []),
        },
        "scenarios": scenario_reports,
        "overall": {
            "hitRate": overall_hit_rate,
            "hits": total_hits,
            "misses": total_misses,
        },
        "issues": issues,
        "recommendations": recommendations,
    }

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print("[analyze-cache-performance] Summary:")
    for entry in scenario_reports:
        metrics = entry["metrics"]
        print(
            f"  - {entry['name']}: hitRate={metrics.get('hitRate')} hits={metrics.get('hits')} misses={metrics.get('misses')}"
        )

    if overall_hit_rate is not None:
        print(f"  Overall hit rate: {overall_hit_rate}")

    if issues:
        for note in issues:
            print(f"[analyze-cache-performance] issue -> {note}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
