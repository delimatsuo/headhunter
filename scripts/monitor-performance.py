#!/usr/bin/env python3
"""Continuous performance monitoring for the local stack."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List

from run_integration import (  # type: ignore[import-untyped]
    CACHED_READ_P95_TARGET_MS,
    CACHE_HIT_RATE_TARGET,
    END_TO_END_P95_TARGET_MS,
    RERANK_P95_TARGET_MS,
)

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_REPORT_DIR = SCRIPT_DIR.parent / ".integration"


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor local performance targets")
    parser.add_argument("--cycles", type=int, default=1, help="Number of monitoring iterations")
    parser.add_argument(
        "--interval", type=float, default=30.0, help="Seconds to wait between cycles (ignored for final cycle)"
    )
    parser.add_argument("--report", type=Path, help="Optional path to write aggregated JSON report")
    parser.add_argument(
        "--workdir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help="Directory used to store intermediate JSON artifacts",
    )
    return parser.parse_args(argv)


def run_validate(report_path: Path) -> Dict[str, Any]:
    cmd = [
        "python3",
        str(SCRIPT_DIR / "validate-performance-slas.py"),
        "--iterations",
        "1",
        "--warmups",
        "0",
        "--report",
        str(report_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if report_path.exists():
        data = json.loads(report_path.read_text(encoding="utf-8"))
    else:
        data = {"issues": ["validate-performance-slas failed"], "stderr": result.stderr}
    data["returncode"] = result.returncode
    data["stdout"] = result.stdout
    data["stderr"] = result.stderr
    return data


def run_cache_analysis(report_path: Path) -> Dict[str, Any]:
    cmd = [
        "python3",
        str(SCRIPT_DIR / "analyze-cache-performance.py"),
        "--samples",
        "3",
        "--report",
        str(report_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if report_path.exists():
        data = json.loads(report_path.read_text(encoding="utf-8"))
    else:
        data = {"issues": ["analyze-cache-performance failed"], "stderr": result.stderr}
    data["returncode"] = result.returncode
    data["stdout"] = result.stdout
    data["stderr"] = result.stderr
    return data


def aggregate(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"avg": None, "min": None, "max": None}
    return {
        "avg": round(mean(values), 2),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
    }


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    args.workdir.mkdir(parents=True, exist_ok=True)

    timeline: List[Dict[str, Any]] = []
    alerts: List[str] = []
    recommendations: List[str] = []

    for cycle in range(1, args.cycles + 1):
        print(f"[monitor-performance] Cycle {cycle}/{args.cycles}")
        sla_path = args.workdir / f"monitor_sla_cycle_{cycle}.json"
        cache_path = args.workdir / f"monitor_cache_cycle_{cycle}.json"

        sla_snapshot = run_validate(sla_path)
        cache_snapshot = run_cache_analysis(cache_path)

        timeline.append({"cycle": cycle, "sla": sla_snapshot, "cache": cache_snapshot})

        sla_results = sla_snapshot.get("sla", {})
        if sla_snapshot.get("returncode") != 0 or sla_snapshot.get("issues"):
            alerts.extend([f"Cycle {cycle}: {msg}" for msg in sla_snapshot.get("issues", []) or ["SLA script failed"]])
        for name, status in sla_results.items():
            if not status.get("pass"):
                alerts.append(
                    f"Cycle {cycle}: {name} metric failing (observed={status.get('p95') or status.get('observed')})"
                )
        recommendations.extend(sla_snapshot.get("recommendations", []))

        cache_overall = cache_snapshot.get("overall", {})
        if cache_snapshot.get("returncode") != 0 or cache_snapshot.get("issues"):
            alerts.extend([f"Cycle {cycle}: {msg}" for msg in cache_snapshot.get("issues", []) or ["Cache script failed"]])
        hit_rate = cache_overall.get("hitRate")
        if hit_rate is not None and hit_rate < CACHE_HIT_RATE_TARGET:
            alerts.append(
                f"Cycle {cycle}: overall cache hitRate={hit_rate} below target {CACHE_HIT_RATE_TARGET:.2f}"
            )
        recommendations.extend(cache_snapshot.get("recommendations", []))

        if cycle != args.cycles:
            time.sleep(max(args.interval, 0))

    end_to_end_values = [entry["sla"].get("sla", {}).get("endToEnd", {}).get("p95") for entry in timeline]
    end_to_end_values = [v for v in end_to_end_values if v is not None]
    rerank_values = [entry["sla"].get("sla", {}).get("rerank", {}).get("p95") for entry in timeline]
    rerank_values = [v for v in rerank_values if v is not None]
    cached_values = [entry["sla"].get("sla", {}).get("cachedRead", {}).get("p95") for entry in timeline]
    cached_values = [v for v in cached_values if v is not None]
    cache_rates = [entry["cache"].get("overall", {}).get("hitRate") for entry in timeline]
    cache_rates = [v for v in cache_rates if v is not None]

    aggregate_metrics = {
        "endToEndP95": aggregate(end_to_end_values),
        "rerankP95": aggregate(rerank_values),
        "cachedReadP95": aggregate(cached_values),
        "cacheHitRate": aggregate(cache_rates),
        "targets": {
            "endToEndP95": END_TO_END_P95_TARGET_MS,
            "rerankP95": RERANK_P95_TARGET_MS,
            "cachedReadP95": CACHED_READ_P95_TARGET_MS,
            "cacheHitRate": CACHE_HIT_RATE_TARGET,
        },
    }

    final_report = {
        "cycles": args.cycles,
        "timeline": timeline,
        "aggregate": aggregate_metrics,
        "alerts": alerts,
        "recommendations": sorted(set(filter(None, recommendations))),
    }

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(final_report, indent=2, sort_keys=True), encoding="utf-8")

    print("[monitor-performance] Aggregate summary:")
    print(
        f"  end-to-end p95 avg={aggregate_metrics['endToEndP95']['avg']} (target {END_TO_END_P95_TARGET_MS})"
    )
    print(f"  rerank p95 avg={aggregate_metrics['rerankP95']['avg']} (target {RERANK_P95_TARGET_MS})")
    print(
        f"  cached read p95 avg={aggregate_metrics['cachedReadP95']['avg']} (target {CACHED_READ_P95_TARGET_MS})"
    )
    print(f"  cache hit rate avg={aggregate_metrics['cacheHitRate']['avg']} (target {CACHE_HIT_RATE_TARGET})")

    if alerts:
        for alert in alerts:
            print(f"[monitor-performance] alert -> {alert}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
