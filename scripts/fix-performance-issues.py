#!/usr/bin/env python3
"""Attempt automated remediation for local performance issues."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from run_integration import (  # type: ignore[import-untyped]
    SERVICE_URLS,
    TENANT_ID,
    execute_flow,
    extract_cache_flag,
    get_token,
    HttpClient,
)

DEFAULT_SEARCH_PAYLOAD = {
    "query": "cientista de dados",
    "limit": 5,
    "filters": {"skills": ["python"], "locations": ["Sao Paulo"]},
    "includeDebug": True,
}


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply automated fixes for performance issues")
    parser.add_argument("--source-report", type=Path, required=True, help="Path to performance SLA report")
    parser.add_argument("--cache-report", type=Path, help="Optional cache analysis report")
    parser.add_argument("--apply", action="store_true", help="Execute remediation actions")
    parser.add_argument("--report", type=Path, help="Location to write remediation summary")
    return parser.parse_args(argv)


def load_json(path: Path) -> Dict[str, Any]:
    if not path or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_action_plan(sla_report: Dict[str, Any], cache_report: Dict[str, Any]) -> List[Dict[str, Any]]:
    plan: List[Dict[str, Any]] = []
    sla = sla_report.get("sla", {})

    if not sla.get("endToEnd", {}).get("pass", True):
        plan.append({"name": "warm_pipeline", "reason": "End-to-end SLA failed"})
    if not sla.get("rerank", {}).get("pass", True):
        plan.append({"name": "warm_rerank_cache", "reason": "Rerank latency above budget"})
    if not sla.get("cachedRead", {}).get("pass", True):
        plan.append({"name": "warm_evidence_cache", "reason": "Cached reads too slow"})
    if not sla.get("cacheHitRate", {}).get("pass", True):
        plan.append({"name": "warm_search_cache", "reason": "Cache hit rate below target"})

    for scenario in cache_report.get("scenarios", []):
        metrics = scenario.get("metrics", {})
        hit_rate = metrics.get("hitRate")
        name = scenario.get("name")
        if hit_rate is None or hit_rate >= sla_report.get("sla", {}).get("cacheHitRate", {}).get("target", 0.7):
            continue
        mapped = SCENARIO_ACTIONS.get(name)
        if mapped:
            plan.append({"name": mapped, "reason": f"Scenario {name} hitRate={hit_rate}"})

    if not plan:
        plan.append({"name": "cache_health_check", "reason": "No specific issues identified"})
    return plan


def warm_search_cache(client: HttpClient) -> Dict[str, Any]:
    latencies: List[float] = []
    for _ in range(3):
        response = client.request("POST", SERVICE_URLS["search"], "/v1/search/hybrid", DEFAULT_SEARCH_PAYLOAD)
        latencies.append(response["latency_ms"])
        extract_cache_flag(response["data"])
    return {"latencies": latencies}


def warm_rerank_cache(client: HttpClient) -> Dict[str, Any]:
    initial = client.request("POST", SERVICE_URLS["search"], "/v1/search/hybrid", DEFAULT_SEARCH_PAYLOAD)
    candidates = initial["data"].get("results", [])[:5]
    payload = {
        "jobDescription": "Buscamos Cientista de Dados senior para liderar iniciativas de IA.",
        "query": DEFAULT_SEARCH_PAYLOAD["query"],
        "candidates": candidates,
        "limit": 5,
        "includeReasons": True,
    }
    response = client.request("POST", SERVICE_URLS["rerank"], "/v1/search/rerank", payload)
    return {"latency": response["latency_ms"], "results": len(response["data"].get("results", []))}


def warm_evidence_cache(client: HttpClient, candidate_id: str | None) -> Dict[str, Any]:
    target_candidate = candidate_id or "cand-001"
    response = client.request("GET", SERVICE_URLS["evidence"], f"/v1/evidence/{target_candidate}")
    flag = extract_cache_flag(response["data"])
    return {"latency": response["latency_ms"], "cacheHit": flag, "candidate": target_candidate}


def warm_msgs_cache(client: HttpClient, eco_id: str | None) -> Dict[str, Any]:
    skill_payload = {"skillId": "python", "topK": 5, "includeRelatedRoles": True}
    template_payload = {"ecoId": eco_id or "eco-1", "locale": "pt-BR", "includeDemand": True}
    skill_response = client.request("POST", SERVICE_URLS["msgs"], "/v1/skills/expand", skill_payload)
    template_response = client.request("POST", SERVICE_URLS["msgs"], "/v1/roles/template", template_payload)
    return {
        "skillLatency": skill_response["latency_ms"],
        "templateLatency": template_response["latency_ms"],
        "skillCache": extract_cache_flag(skill_response["data"]),
        "templateCache": extract_cache_flag(template_response["data"]),
    }


def warm_eco_cache(client: HttpClient, eco_id: str | None) -> Dict[str, Any]:
    search_response = client.request(
        "GET",
        SERVICE_URLS["eco"],
        "/v1/occupations/search",
        params={"title": "engenheiro de software", "locale": "pt-BR", "limit": 5},
    )
    target = eco_id or search_response["data"].get("results", [{}])[0].get("ecoId")
    detail_response = client.request(
        "GET",
        SERVICE_URLS["eco"],
        f"/v1/occupations/{target}",
        params={"locale": "pt-BR"},
    )
    return {
        "searchLatency": search_response["latency_ms"],
        "detailLatency": detail_response["latency_ms"],
        "detailEcoId": target,
    }


def cache_health_check(client: HttpClient) -> Dict[str, Any]:
    response = client.request("GET", SERVICE_URLS["search"], "/health")
    return {"latency": response["latency_ms"], "status": response["data"].get("status")}


SCENARIO_ACTIONS = {
    "search-hybrid": "warm_search_cache",
    "rerank": "warm_rerank_cache",
    "evidence": "warm_evidence_cache",
    "msgs-skill-expand": "warm_msgs_cache",
    "msgs-role-template": "warm_msgs_cache",
    "eco-search": "warm_eco_cache",
    "eco-detail": "warm_eco_cache",
}

ACTION_EXECUTORS = {
    "warm_pipeline": lambda client, context: {"reportSteps": execute_flow()},
    "warm_rerank_cache": lambda client, context: warm_rerank_cache(client),
    "warm_evidence_cache": lambda client, context: warm_evidence_cache(client, context.get("top_candidate")),
    "warm_search_cache": lambda client, context: warm_search_cache(client),
    "warm_msgs_cache": lambda client, context: warm_msgs_cache(client, context.get("eco_id")),
    "warm_eco_cache": lambda client, context: warm_eco_cache(client, context.get("eco_id")),
    "cache_health_check": lambda client, context: cache_health_check(client),
}


def derive_context(report: Dict[str, Any]) -> Dict[str, Any]:
    context: Dict[str, Any] = {}
    samples = report.get("samples", [])
    for sample in samples:
        for entry in sample.get("cachedSamples", []):
            if entry.get("type") != "evidence":
                continue
            candidate = entry.get("candidate")
            if candidate:
                context.setdefault("top_candidate", candidate)
            elif entry.get("cacheHit") is True:
                context.setdefault("top_candidate", candidate)
    # fallback using report structure from validate script is limited; run integration for more detail later if needed
    return context


def apply_actions(plan: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    outcomes: List[Dict[str, Any]] = []
    token = get_token()
    client = HttpClient(token, TENANT_ID)

    # Optionally run integration flow once to enrich context when needed
    if any(action["name"] == "warm_pipeline" for action in plan):
        flow_report = execute_flow()
        context.setdefault("top_candidate", flow_report["steps"].get("search_rerank", {}).get("data", {}).get("top_candidate_id"))
        eco_id = flow_report["steps"].get("eco_search", {}).get("data", {}).get("primary_eco_id")
        if eco_id:
            context.setdefault("eco_id", eco_id)
        outcomes.append({"name": "warm_pipeline", "status": "ok", "details": {"stepsPassed": flow_report["completed_steps"]}})

    for action in plan:
        name = action["name"]
        if name == "warm_pipeline":
            continue  # already executed above
        executor = ACTION_EXECUTORS.get(name)
        if not executor:
            outcomes.append({"name": name, "status": "skipped", "details": {"reason": "no executor"}})
            continue
        try:
            details = executor(client, context)
            outcomes.append({"name": name, "status": "ok", "details": details})
        except Exception as exc:  # noqa: BLE001
            outcomes.append({"name": name, "status": "error", "details": {"error": str(exc)}})
    return outcomes


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    sla_report = load_json(args.source_report)
    cache_report = load_json(args.cache_report) if args.cache_report else {}

    plan = build_action_plan(sla_report, cache_report)
    context = derive_context(sla_report)
    outcomes: List[Dict[str, Any]] = []

    if args.apply:
        outcomes = apply_actions(plan, context)
    else:
        outcomes = [{"name": action["name"], "status": "planned", "details": {}} for action in plan]

    summary = {
        "tenant": TENANT_ID,
        "plan": plan,
        "executed": outcomes,
    }

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    failures = [item for item in outcomes if item.get("status") == "error"]
    if failures:
        for failure in failures:
            print(f"[fix-performance-issues] failed -> {failure}", file=sys.stderr)
        return 1

    print("[fix-performance-issues] Actions executed:")
    for outcome in outcomes:
        print(f"  - {outcome['name']}: {outcome['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
