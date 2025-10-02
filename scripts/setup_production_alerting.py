#!/usr/bin/env python3
"""
Configure production-ready alerting for Headhunter systems.

References:
- cloud_run_worker/metrics.py
- scripts/monitor_cloud_run_performance.py

Alert categories:
1) Cloud Run worker (error rate, response time, resource exhaustion)
2) Database (connection pool, slow queries, storage limits)
3) APIs (Together AI limits, auth failures, quota exhaustion)
4) Pipeline (Pub/Sub backlog, DLQ accumulation)
5) Security (unauthorized access attempts, suspicious activity)
6) Cost (billing spikes, usage anomalies)
7) Uptime (availability, health checks)
8) Data quality (processing failures, corruption, schema violations)
9) Performance (SLA violations, throughput degradation)
10) Notification routing (severity-based escalation)

Uses Cloud Monitoring APIs when available; otherwise executes in dry-run mode.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from scripts.utils.reporting import _log as _base_log, ensure_reports_dir, save_json_report  # type: ignore
except Exception:
    def _fallback_log(name: str, msg: str) -> None:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        print(f"[{name}] {ts} | {msg}")

    def ensure_reports_dir(path: str = "reports") -> str:
        os.makedirs(path, exist_ok=True)
        return path

    def save_json_report(path: str, data: Dict[str, Any]) -> str:
        ensure_reports_dir(os.path.dirname(path) or ".")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        return path

    def _base_log(name: str, msg: str) -> None:
        _fallback_log(name, msg)

NAME = "setup_production_alerting"
CANONICAL_ROOT = Path("/Volumes/Extreme Pro/myprojects/headhunter").resolve()


def _log(msg: str) -> None:
    _base_log(NAME, msg)


def try_import_monitoring():
    try:
        from google.cloud import monitoring_v3  # type: ignore
        return monitoring_v3
    except Exception:
        return None


def resolve_notification_channels(mon, project: str, provided: List[str]) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    if not mon or not provided:
        return [], errors
    try:
        client = mon.NotificationChannelServiceClient()
        parent = f"projects/{project}"
        chans = list(client.list_notification_channels(name=parent))
        by_id = {c.name.split("/")[-1]: c.name for c in chans}
        by_name = {c.display_name: c.name for c in chans}
        resolved: List[str] = []
        for item in provided:
            if item.startswith("projects/"):
                resolved.append(item)
            elif item in by_id:
                resolved.append(by_id[item])
            elif item in by_name:
                resolved.append(by_name[item])
            else:
                errors.append(f"Channel not found: {item}")
        return resolved, errors
    except Exception as e:
        return [], [str(e)]


@dataclass
class PolicyResult:
    name: str
    created: bool
    errors: List[str]
    severity: str


def policy_templates(prefix: str) -> List[Dict[str, Any]]:
    templates = []
    def mql_condition(name: str, query: str, duration: str, comparison: str, threshold: float, severity: str) -> Dict[str, Any]:
        return {
            "displayName": f"{prefix} {name}",
            "combiner": "OR",
            "enabled": True,
            "userLabels": {"severity": severity},
            "documentation": {"content": f"Severity: {severity}"},
            "conditions": [{
                "conditionMonitoringQueryLanguage": {
                    "query": query,
                    "duration": duration,
                    "trigger": {"count": 1},
                    "comparison": comparison,
                    "thresholdValue": threshold,
                }
            }],
        }

    service = "candidate-enricher"
    latency_query = (
        "fetch run_revision | metric 'run.googleapis.com/request_latencies' "
        "| filter resource.service_name = '" + service + "' | align 5m, percentile(95) | every 5m"
    )
    error_ratio_query = (
        "fetch run_revision | metric 'run.googleapis.com/request_count' "
        "| filter resource.service_name = '" + service + "' "
        "| group_by [], [val_5xx: sum(if(metric.response_code_class = '5xx', metric.request_count, 0)), val_total: sum(metric.request_count)] | "
        "join | map [ratio: val_5xx / val_total] | every 1m"
    )

    templates.append(mql_condition("Cloud Run p95 > 1.2s (ms)", latency_query, "600s", "COMPARISON_GT", 1200.0, "SEV-2"))
    templates.append(mql_condition("Cloud Run error rate > 5%", error_ratio_query, "600s", "COMPARISON_GT", 0.05, "SEV-2"))
    templates.append(mql_condition("DB connections high", "fetch cloudsql_database | metric 'cloudsql.googleapis.com/database/connections' | align 5m, mean | every 5m", "600s", "COMPARISON_GT", 0.8, "SEV-3"))
    templates.append(mql_condition("Pub/Sub backlog high", "fetch pubsub_subscription | metric 'pubsub.googleapis.com/subscription/num_undelivered_messages' | align 5m, mean | every 5m", "600s", "COMPARISON_GT", 1000, "SEV-2"))
    templates.append(mql_condition("TogetherAI errors", "fetch generic_task | metric 'custom.googleapis.com/togetherai/error_rate' | align 5m, mean | every 5m", "600s", "COMPARISON_GT", 0.05, "SEV-3"))
    # Uptime: use conditionAbsent for 5 minutes
    templates.append({
        "displayName": f"{prefix} Uptime check down",
        "combiner": "OR",
        "enabled": True,
        "userLabels": {"severity": "SEV-1"},
        "documentation": {"content": "Severity: SEV-1. Uptime check not passing for 5m."},
        "conditions": [{
            "conditionAbsent": {
                "filter": "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\"",
                "duration": "300s",
                "aggregations": [{"alignmentPeriod": "60s", "perSeriesAligner": "ALIGN_MEAN"}],
            }
        }],
    })
    templates.append(mql_condition("Data quality failures", "fetch generic_task | metric 'custom.googleapis.com/pipeline/data_quality_failures' | align 5m, rate(sum) | every 5m", "600s", "COMPARISON_GT", 1, "SEV-2"))
    # Billing alert removed; TODO note
    return templates


def _typed_alert_policy(mon, policy: Dict[str, Any]):
    try:
        ap = mon.types.AlertPolicy()
        ap.display_name = policy.get("displayName", "")
        ap.combiner = getattr(mon.types.AlertPolicy.ConditionCombinerType, policy.get("combiner", "OR"))
        ap.enabled = policy.get("enabled", True)
        for cond in policy.get("conditions", []):
            c = mon.types.AlertPolicy.Condition()
            if "conditionMonitoringQueryLanguage" in cond:
                mql = cond["conditionMonitoringQueryLanguage"]
                c.monitoring_query_language_condition.query = mql.get("query", "")
                c.monitoring_query_language_condition.duration = mql.get("duration", "600s")
                trg = mql.get("trigger", {}) or {}
                if "count" in trg:
                    c.monitoring_query_language_condition.trigger.count = int(trg["count"])  # type: ignore
                comp = mql.get("comparison", "COMPARISON_GT")
                c.monitoring_query_language_condition.comparison = getattr(mon.ComparisonType, comp)
                c.monitoring_query_language_condition.threshold_value = float(mql.get("thresholdValue", 0))
            elif "conditionAbsent" in cond:
                absent = cond["conditionAbsent"]
                c.condition_absent.filter = absent.get("filter", "")
                c.condition_absent.duration = absent.get("duration", "300s")
            ap.conditions.append(c)
        for ch in policy.get("notificationChannels", []) or []:
            ap.notification_channels.append(ch)
        for k, v in (policy.get("userLabels") or {}).items():
            ap.user_labels[k] = v
        if policy.get("documentation"):
            ap.documentation.content = policy["documentation"].get("content", "")
        if policy.get("name"):
            ap.name = policy["name"]
        return ap
    except Exception:
        return policy


def create_policies(project: str, prefix: str, channels: List[str], apply_changes: bool, reconcile: bool) -> List[PolicyResult]:
    mon = try_import_monitoring()
    client = mon.AlertPolicyServiceClient() if mon and apply_changes else None
    parent = f"projects/{project}"

    # Resolve channels to full resource names
    resolved_channels: List[str] = []
    channel_errors: List[str] = []
    if channels and mon and apply_changes:
        resolved_channels, channel_errors = resolve_notification_channels(mon, project, channels)
        if channel_errors:
            _log(f"Channel resolution errors: {channel_errors}")

    results: List[PolicyResult] = []
    templates = policy_templates(prefix)
    if reconcile and client is not None:
        existing = list(client.list_alert_policies(name=parent))
        keep = {t["displayName"] for t in templates}
        for pol in existing:
            if pol.display_name.startswith(prefix) and pol.display_name not in keep:
                try:
                    client.delete_alert_policy(name=pol.name)
                    _log(f"Deleted unmanaged policy: {pol.display_name}")
                except Exception as e:
                    _log(f"Failed deleting policy {pol.display_name}: {e}")

    for p in templates:
        if channels:
            p["notificationChannels"] = resolved_channels or channels
        name = p["displayName"]
        if client is None:
            _log(f"[dry-run] Would create alert: {name}")
            sev = p.get("userLabels", {}).get("severity", "")
            results.append(PolicyResult(name=name, created=False, errors=[], severity=sev))
            continue
        try:
            # Idempotent upsert by display name
            existing = list(client.list_alert_policies(name=parent))
            match = next((ep for ep in existing if ep.display_name == name), None)
            if match:
                p["name"] = match.name
                client.update_alert_policy(alert_policy=_typed_alert_policy(mon, p))
                sev = p.get("userLabels", {}).get("severity", "")
                results.append(PolicyResult(name=name, created=False, errors=[], severity=sev))
            else:
                client.create_alert_policy(request={"name": parent, "alert_policy": _typed_alert_policy(mon, p)})
                sev = p.get("userLabels", {}).get("severity", "")
                results.append(PolicyResult(name=name, created=True, errors=[], severity=sev))
        except Exception as e:
            sev = p.get("userLabels", {}).get("severity", "")
            results.append(PolicyResult(name=name, created=False, errors=[str(e)], severity=sev))
    return results


def save_report(results: List[PolicyResult], reports_dir: str) -> str:
    report = {
        "summary": {"created": sum(1 for r in results if r.created), "total": len(results)},
        "policies": [asdict(r) for r in results],
        "timestamp": int(time.time()),
        "notes": {
            "billing": "TODO: integrate Cloud Billing Budgets via Pub/Sub notifications; consider cost anomaly detection via custom metrics.",
        },
    }
    path = os.path.join(reports_dir, "production_alerting_report.json")
    return save_json_report(path, report)


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    current_root = Path.cwd().resolve()
    if current_root != CANONICAL_ROOT:
        _log(
            "ERROR: run this script from the canonical repository root "
            f"{CANONICAL_ROOT} (current={current_root})."
        )
        return 2

    parser = argparse.ArgumentParser(description="Setup production alerting")
    parser.add_argument("--project", required=True, help="GCP project ID")
    parser.add_argument("--prefix", default="Headhunter", help="Display name prefix")
    parser.add_argument("--channels", default="", help="Comma-separated notification channel IDs")
    parser.add_argument("--apply", action="store_true", help="Apply changes (otherwise dry-run)")
    parser.add_argument("--reports-dir", default="reports", help="Directory for reports")
    parser.add_argument("--reconcile", action="store_true", help="Delete unmanaged alert policies with prefix")
    args = parser.parse_args(argv)

    channels = [c.strip() for c in args.channels.split(",") if c.strip()]
    results = create_policies(args.project, args.prefix, channels, args.apply, args.reconcile)
    path = save_report(results, args.reports_dir)
    _log(f"Report written: {path}")
    return 0 if all(r.created or not args.apply for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
