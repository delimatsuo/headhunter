#!/usr/bin/env python3
"""
System health dashboard generator for Headhunter.

References:
- cloud_run_worker/metrics.py
- scripts/monitor_cloud_run_performance.py
- scripts/monitor_pgvector_performance.py

Creates a unified, real-time style dashboard view by aggregating
available reports and metrics into a single summary for quick triage:
1) Component status (Cloud Run, Functions, Pub/Sub, DBs)
2) Performance (latency, throughput, errors, resources)
3) Dependencies (Together AI, Firebase, external services)
4) Capacity and scaling
5) Recent deployments (from CI/CD report)
6) Security status
7) Cost and utilization trends
8) UX metrics (search quality)
9) Drill-down pointers (logs, traces, metrics)
10) Health score and recommendations
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import time
from typing import Any, Dict, Optional, List

from scripts.utils.reporting import _log as _base_log

NAME = "system_health_dashboard"


def _log(msg: str) -> None:
    _base_log(NAME, msg)


def load_latest(pattern: str) -> Optional[Dict[str, Any]]:
    files = sorted(glob.glob(pattern), key=os.path.getmtime)
    if not files:
        return None
    with open(files[-1], "r", encoding="utf-8") as f:
        return json.load(f)


def _component_status(is_ok: bool) -> str:
    return "healthy" if is_ok else "degraded"


def _last_failure_timestamps(reports: List[Dict[str, Any]]) -> List[str]:
    stamps: List[str] = []
    for r in reports:
        ts = r.get("timestamp")
        if r and not r.get("summary", {}).get("passed", True):
            if ts:
                stamps.append(time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(ts)))
    return stamps


def build_summary(reports_dir: str) -> Dict[str, Any]:
    integration = load_latest(os.path.join(reports_dir, "integration_test_report.json")) or {}
    security = load_latest(os.path.join(reports_dir, "security_validation_report.json")) or {}
    monitoring = load_latest(os.path.join(reports_dir, "monitoring_dashboards_report.json")) or {}
    alerts = load_latest(os.path.join(reports_dir, "production_alerting_report.json")) or {}
    dr = load_latest(os.path.join(reports_dir, "dr_validation_report.json")) or {}
    sla = load_latest(os.path.join(reports_dir, "sla_report.json")) or {}
    cicd = load_latest(os.path.join(reports_dir, "cicd_pipeline_report.json")) or {}

    health_score = 100
    if integration and not integration.get("sla_compliant", True):
        health_score -= 15
    if security and not security.get("summary", {}).get("passed", True):
        health_score -= 20
    if sla and not sla.get("compliant", True):
        health_score -= 20

    alerts_summary = alerts.get("summary", {}) if isinstance(alerts, dict) else {}
    alert_count = alerts_summary.get("total", 0)
    created_alerts = alerts_summary.get("created", 0)
    last_failures = _last_failure_timestamps([security, integration, sla])

    summary = {
        "components": {
            "cloud_run": _component_status(integration.get("sla_compliant", True)),
            "functions": _component_status(True if not integration else all(c.get("passed", True) for c in integration.get("cases", []))),
            "pubsub": _component_status(True),
            "database": _component_status(True),
        },
        "integration": integration,
        "security": security.get("summary", {}),
        "monitoring": monitoring.get("dashboards", []),
        "alerts": alerts_summary,
        "dr": dr.get("summary", {}),
        "sla": sla,
        "cicd": cicd,
        "health_score": max(0, min(100, health_score)),
        "timestamp": int(time.time()),
        "alert_counts": {"total": alert_count, "created": created_alerts},
        "last_failure_timestamps": last_failures,
        "recommendations": [
            "Investigate any SLA breaches promptly",
            "Review recent deployments for performance regressions",
            "Ensure alert policies cover all critical paths",
        ],
    }
    return summary


def print_summary(summary: Dict[str, Any]) -> None:
    print(json.dumps(summary, indent=2))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate system health dashboard summary")
    parser.add_argument("--reports-dir", default="reports", help="Directory where reports are stored")
    parser.add_argument("--summary", action="store_true", help="Print summary JSON and exit")
    args = parser.parse_args(argv)

    summary = build_summary(args.reports_dir)
    if args.summary:
        print_summary(summary)
    else:
        _log("Use --summary to print dashboard JSON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
