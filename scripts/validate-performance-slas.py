#!/usr/bin/env python3
"""Validate performance SLAs for the local stack."""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Tuple

from run_integration import (  # type: ignore[import-untyped]
    CACHED_READ_P95_TARGET_MS,
    CACHE_HIT_RATE_TARGET,
    END_TO_END_P95_TARGET_MS,
    RERANK_P95_TARGET_MS,
    SERVICE_URLS,
    TENANT_ID,
    compute_percentile,
    execute_flow,
    extract_cache_flag,
    get_token,
    HttpClient,
)


@dataclass
class CachedSample:
    """Simple container for cached read measurements."""

    sample_type: str
    latency_ms: float | None
    cache_hit: bool | None
    candidate_id: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.sample_type,
            "latencyMs": None if self.latency_ms is None else round(self.latency_ms, 2),
            "cacheHit": self.cache_hit,
            "candidate": self.candidate_id,
        }


def default_search_payload() -> Dict[str, Any]:
    return {
        "query": "cientista de dados senior",
        "limit": 5,
        "filters": {
            "skills": ["python", "spark"],
            "locations": ["Sao Paulo"],
        },
        "includeDebug": True,
    }


def measure_cached_search(client: HttpClient) -> CachedSample:
    payload = default_search_payload()
    client.request("POST", SERVICE_URLS["search"], "/v1/search/hybrid", payload)
    warmed = client.request("POST", SERVICE_URLS["search"], "/v1/search/hybrid", payload)
    cache_flag = extract_cache_flag(warmed["data"])
    return CachedSample("search", warmed["latency_ms"], cache_flag)


def measure_cached_evidence(client: HttpClient, candidate_id: str | None) -> CachedSample:
    if not candidate_id:
        return CachedSample("evidence", None, None, candidate_id=candidate_id)
    response = client.request("GET", SERVICE_URLS["evidence"], f"/v1/evidence/{candidate_id}")
    cache_flag = extract_cache_flag(response["data"])
    return CachedSample("evidence", response["latency_ms"], cache_flag, candidate_id=candidate_id)


def aggregate_cache_flags(report: Dict[str, Any]) -> List[Tuple[str, bool]]:
    flags: List[Tuple[str, bool]] = []
    for name, step in report.get("steps", {}).items():
        data = step.get("data", {}) if isinstance(step, dict) else {}
        cache_flag = extract_cache_flag(data)
        if cache_flag is not None:
            flags.append((name, cache_flag))
    return flags


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate local performance SLAs")
    parser.add_argument("--iterations", type=int, default=3, help="Number of measured iterations")
    parser.add_argument("--warmups", type=int, default=1, help="Warm-up runs that are not scored")
    parser.add_argument("--report", type=Path, help="Optional path to emit JSON report")
    parser.add_argument(
        "--cached-only",
        action="store_true",
        help="Skip executing the full integration pipeline and only validate cached reads",
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    iterations: List[Dict[str, Any]] = []
    cached_samples: List[float] = []
    end_to_end_samples: List[float] = []
    rerank_samples: List[float] = []
    cache_hits = 0
    cache_misses = 0
    issues: List[str] = []

    token = get_token()
    client = HttpClient(token, TENANT_ID)

    total_runs = args.iterations + args.warmups
    if total_runs <= 0:
        print("[validate-performance-slas] No iterations requested", file=sys.stderr)
        return 1

    for run_index in range(1, total_runs + 1):
        is_warmup = run_index <= args.warmups
        iteration_label = f"warmup-{run_index}" if is_warmup else f"iteration-{run_index - args.warmups}"
        print(f"[validate-performance-slas] Starting {iteration_label}")

        start = time.perf_counter()
        iteration_report: Dict[str, Any] | None = None

        if not args.cached_only:
            try:
                iteration_report = execute_flow()
            except Exception as exc:  # noqa: BLE001
                issues.append(f"Pipeline execution failed during {iteration_label}: {exc}")
                print(f"[validate-performance-slas] ERROR {exc}", file=sys.stderr)
                continue
        end_to_end_ms = (time.perf_counter() - start) * 1000

        cached_measurements: List[CachedSample] = []
        rerank_latency = None
        iteration_hits = 0
        iteration_misses = 0

        if iteration_report:
            end_to_end_samples.append(end_to_end_ms)
            rerank_step = iteration_report["steps"].get("search_rerank", {})
            rerank_timings = rerank_step.get("data", {}).get("timings", {}) if isinstance(rerank_step, dict) else {}
            rerank_latency = rerank_timings.get("totalMs")
            if rerank_latency is None and isinstance(rerank_step, dict):
                rerank_latency = rerank_step.get("latencyMs")
            if rerank_latency is not None:
                rerank_samples.append(float(rerank_latency))

            for name, flag in aggregate_cache_flags(iteration_report):
                if flag:
                    iteration_hits += 1
                else:
                    iteration_misses += 1

            top_candidate = None
            rerank_data = iteration_report["steps"].get("search_rerank", {}).get("data", {})
            if isinstance(rerank_data, dict):
                top_candidate = rerank_data.get("top_candidate_id")
            sample = measure_cached_evidence(client, top_candidate)
            cached_measurements.append(sample)

        search_sample = measure_cached_search(client)
        cached_measurements.append(search_sample)

        for sample in cached_measurements:
            if sample.cache_hit is True:
                iteration_hits += 1
                cached_samples.append(sample.latency_ms or 0.0)
            elif sample.cache_hit is False:
                iteration_misses += 1

        if is_warmup:
            continue

        cache_hits += iteration_hits
        cache_misses += iteration_misses

        iteration_payload = {
            "label": iteration_label,
            "endToEndMs": round(end_to_end_ms, 2),
            "rerankMs": None if rerank_latency is None else round(float(rerank_latency), 2),
            "cachedSamples": [sample.to_dict() for sample in cached_measurements],
            "cacheHits": iteration_hits,
            "cacheMisses": iteration_misses,
        }
        iterations.append(iteration_payload)

    observed_runs = len(iterations)
    if observed_runs == 0:
        issues.append("No successful iterations recorded for SLA evaluation")

    def _safe_stats(samples: List[float]) -> Dict[str, Any]:
        if not samples:
            return {"count": 0, "avg": None, "p95": None, "max": None, "min": None}
        return {
            "count": len(samples),
            "avg": round(mean(samples), 2),
            "p95": compute_percentile(samples, 95),
            "max": round(max(samples), 2),
            "min": round(min(samples), 2),
        }

    metrics = {
        "endToEndMs": _safe_stats(end_to_end_samples),
        "rerankMs": _safe_stats(rerank_samples),
        "cachedReadMs": _safe_stats(cached_samples),
        "cache": {
            "hits": cache_hits,
            "misses": cache_misses,
            "hitRate": round(cache_hits / (cache_hits + cache_misses), 3)
            if (cache_hits + cache_misses)
            else None,
        },
    }

    cache_hit_rate = metrics["cache"]["hitRate"]
    sla = {
        "endToEnd": {
            "p95": metrics["endToEndMs"]["p95"],
            "target": END_TO_END_P95_TARGET_MS,
            "pass": metrics["endToEndMs"]["p95"] is not None
            and metrics["endToEndMs"]["p95"] <= END_TO_END_P95_TARGET_MS,
        },
        "rerank": {
            "p95": metrics["rerankMs"]["p95"],
            "target": RERANK_P95_TARGET_MS,
            "pass": metrics["rerankMs"]["p95"] is not None
            and metrics["rerankMs"]["p95"] <= RERANK_P95_TARGET_MS,
        },
        "cachedRead": {
            "p95": metrics["cachedReadMs"]["p95"],
            "target": CACHED_READ_P95_TARGET_MS,
            "pass": metrics["cachedReadMs"]["p95"] is not None
            and metrics["cachedReadMs"]["p95"] <= CACHED_READ_P95_TARGET_MS,
        },
        "cacheHitRate": {
            "observed": cache_hit_rate,
            "target": CACHE_HIT_RATE_TARGET,
            "pass": cache_hit_rate is not None and cache_hit_rate >= CACHE_HIT_RATE_TARGET,
        },
    }

    for key, status in sla.items():
        if not status["pass"]:
            issues.append(f"SLA violation: {key} -> {status}")

    recommendations: List[str] = []
    if not sla["cacheHitRate"]["pass"]:
        recommendations.append(
            "Investigate Redis connectivity, ensure caches are warmed, and review TTL settings for hot keys."
        )
    if not sla["cachedRead"]["pass"]:
        recommendations.append(
            "Consider increasing cache prefetching or optimizing serialization for cached read paths."
        )
    if not sla["endToEnd"]["pass"]:
        recommendations.append(
            "Profile service trace to locate slow segments across enrich→embed→search→rerank→evidence pipeline."
        )
    if not sla["rerank"]["pass"]:
        recommendations.append("Evaluate rerank model configuration and ensure Together mock responds within budget.")

    report = {
        "tenant": TENANT_ID,
        "iterations": observed_runs,
        "warmups": args.warmups,
        "metrics": metrics,
        "sla": sla,
        "issues": issues,
        "recommendations": recommendations,
        "samples": iterations,
    }

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print("[validate-performance-slas] Summary:")
    for name, status in sla.items():
        label = "PASS" if status["pass"] else "FAIL"
        if name == "cacheHitRate":
            observed = status["observed"]
            print(
                f"  - {name}: {label} observed={observed if observed is not None else 'n/a'} target={status['target']}"
            )
        else:
            print(f"  - {name}: {label} p95={status['p95']} target={status['target']}")

    if issues:
        for note in issues:
            print(f"[validate-performance-slas] issue -> {note}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
