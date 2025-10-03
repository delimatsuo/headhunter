#!/usr/bin/env python3
"""
Setup Cloud Monitoring dashboards and alerting for Headhunter.

References:
- cloud_run_worker/metrics.py
- scripts/monitor_cloud_run_performance.py
- scripts/monitor_pgvector_performance.py

This script prepares production-ready dashboards and alerting policies:
1) Cloud Run worker performance (latency, error rates, throughput, resources)
2) pgvector database monitoring (pool health, query performance, indexing)
3) Firebase Functions monitoring (invocations, errors, cold starts)
4) Pub/Sub pipeline monitoring (rates, backlog, DLQ)
5) Together AI API monitoring (latency, error, tokens)
6) Embedding generation monitoring (throughput, success, latency)
7) Alert policies (p95 > 1.2s, error rate > 5%, high resources)
8) Notification channels (email, Slack, PagerDuty)

The script supports a dry-run mode by default to operate without cloud credentials.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

from scripts.utils.reporting import _log as _base_log, save_json_report

NAME = "setup_cloud_monitoring_dashboards"


def _log(msg: str) -> None:
    _base_log(NAME, msg)


def try_import_google_clients():
    try:
        from google.cloud import monitoring_dashboard_v1  # type: ignore
        from google.cloud import monitoring_v3  # type: ignore
        return monitoring_dashboard_v1, monitoring_v3
    except Exception:
        return None, None


@dataclass
class DashboardResult:
    name: str
    created: bool
    resource: Dict[str, Any]
    errors: List[str]


@dataclass
class AlertPolicyResult:
    name: str
    created: bool
    conditions: List[Dict[str, Any]]
    notification_channels: List[str]
    errors: List[str]


def resolve_notification_channels(mon_api, project: str, provided: List[str]) -> Tuple[List[str], List[str]]:
    """Map provided channel names/IDs to full resource names.
    Returns (resolved, errors)."""
    errors: List[str] = []
    if not mon_api or not provided:
        return [], errors
    try:
        nclient = mon_api.NotificationChannelServiceClient()
        parent = f"projects/{project}"
        chans = list(nclient.list_notification_channels(name=parent))
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


def build_cloud_run_dashboard(project: str, prefix: str) -> Dict[str, Any]:
    # Use MQL with service scoping and proper aligners
    service = 'candidate-enricher'
    return {
        "displayName": f"{prefix} Cloud Run - Worker Performance",
        "gridLayout": {
            "columns": 2,
            "widgets": [
                {"title": "p95 latency (ms)", "xyChart": {"dataSets": [
                    {"timeSeriesQuery": {"timeSeriesQueryLanguage": (
                        "fetch run_revision | metric 'run.googleapis.com/request_latencies' "
                        "| filter resource.service_name = '" + service + "' "
                        "| align 5m, percentile(95) | every 5m"
                    )}}
                ]}},
                {"title": "Error rate (5xx/total)", "xyChart": {"dataSets": [
                    {"timeSeriesQuery": {"timeSeriesQueryLanguage": (
                        "fetch run_revision | metric 'run.googleapis.com/request_count' "
                        "| filter resource.service_name = '" + service + "' "
                        "| group_by [], [val_5xx: sum(if(metric.response_code_class = '5xx', metric.request_count, 0)), "
                        "val_total: sum(metric.request_count)] | "
                        "join | map [ratio: val_5xx / val_total] | every 5m"
                    )}}
                ]}},
                {"title": "Throughput (req/min)", "xyChart": {"dataSets": [
                    {"timeSeriesQuery": {"timeSeriesQueryLanguage": (
                        "fetch run_revision | metric 'run.googleapis.com/request_count' "
                        "| filter resource.service_name = '" + service + "' | align 1m, rate(sum) | every 1m"
                    )}}
                ]}},
                {"title": "CPU / Memory util", "xyChart": {"dataSets": [
                    {"timeSeriesQuery": {"timeSeriesQueryLanguage": (
                        "fetch run_revision | metric 'run.googleapis.com/container/cpu/utilization' "
                        "| filter resource.service_name = '" + service + "' | align 1m, mean | every 1m"
                    )}},
                    {"timeSeriesQuery": {"timeSeriesQueryLanguage": (
                        "fetch run_revision | metric 'run.googleapis.com/container/memory/utilization' "
                        "| filter resource.service_name = '" + service + "' | align 1m, mean | every 1m"
                    )}}
                ]}},
            ],
        },
    }


def build_pgvector_dashboard(project: str, prefix: str) -> Dict[str, Any]:
    # Replace non-latency panel with meaningful DB health indicators
    return {
        "displayName": f"{prefix} Cloud SQL - pgvector",
        "gridLayout": {
            "columns": 2,
            "widgets": [
                {"title": "Connections (num_backends)", "xyChart": {"dataSets": [
                    {"timeSeriesQuery": {"timeSeriesQueryLanguage": (
                        "fetch cloudsql_database | metric 'cloudsql.googleapis.com/postgresql/num_backends' "
                        "| align 1m, mean | every 1m"
                    )}}
                ]}},
                {"title": "CPU / Memory util", "xyChart": {"dataSets": [
                    {"timeSeriesQuery": {"timeSeriesQueryLanguage": (
                        "fetch cloudsql_database | metric 'cloudsql.googleapis.com/database/cpu/utilization' | align 1m, mean | every 1m"
                    )}},
                    {"timeSeriesQuery": {"timeSeriesQueryLanguage": (
                        "fetch cloudsql_database | metric 'cloudsql.googleapis.com/database/memory/utilization' | align 1m, mean | every 1m"
                    )}}
                ]}},
                {"title": "Lock wait time", "xyChart": {"dataSets": [
                    {"timeSeriesQuery": {"timeSeriesQueryLanguage": (
                        "fetch cloudsql_database | metric 'cloudsql.googleapis.com/postgresql/lock_wait_time' | align 5m, mean | every 5m"
                    )}}
                ]}},
                {"title": "Index scans", "xyChart": {"dataSets": [
                    {"timeSeriesQuery": {"timeSeriesQueryLanguage": (
                        "fetch cloudsql_database | metric 'cloudsql.googleapis.com/postgresql/index_scans' | align 5m, rate(sum) | every 5m"
                    )}}
                ]}},
            ],
        },
        # TODO: Consider exporting pg_stat_statements latency as custom metric for deeper query latency tracking.
    }


def build_functions_dashboard(project: str, prefix: str) -> Dict[str, Any]:
    # Prefer Cloud Run Gen2 metrics where possible; scope by service
    service = 'candidate-enricher-functions'
    return {
        "displayName": f"{prefix} Firebase Functions (Gen2)",
        "gridLayout": {
            "columns": 2,
            "widgets": [
                {"title": "Invocations (req/min)", "xyChart": {"dataSets": [
                    {"timeSeriesQuery": {"timeSeriesQueryLanguage": (
                        "fetch run_revision | metric 'run.googleapis.com/request_count' "
                        "| filter resource.service_name = '" + service + "' | align 1m, rate(sum) | every 1m"
                    )}}
                ]}},
                {"title": "Errors (5xx)", "xyChart": {"dataSets": [
                    {"timeSeriesQuery": {"timeSeriesQueryLanguage": (
                        "fetch run_revision | metric 'run.googleapis.com/request_count' "
                        "| filter resource.service_name = '" + service + "' and metric.response_code_class = '5xx' "
                        "| align 1m, rate(sum) | every 1m"
                    )}}
                ]}},
                {"title": "Cold starts (cf if Gen1)", "xyChart": {"dataSets": [
                    {"timeSeriesQuery": {"timeSeriesQueryLanguage": (
                        "fetch cloud_function | metric 'cloudfunctions.googleapis.com/function/cold_starts_count' | align 5m, rate(sum) | every 5m"
                    )}}
                ]}},
                {"title": "Latency p95 (ms)", "xyChart": {"dataSets": [
                    {"timeSeriesQuery": {"timeSeriesQueryLanguage": (
                        "fetch run_revision | metric 'run.googleapis.com/request_latencies' "
                        "| filter resource.service_name = '" + service + "' | align 5m, percentile(95) | every 5m"
                    )}}
                ]}},
            ],
        },
    }


def build_pubsub_dashboard(project: str, prefix: str) -> Dict[str, Any]:
    return {
        "displayName": f"{prefix} Pub/Sub Pipeline",
        "gridLayout": {
            "columns": 2,
            "widgets": [
                {"title": "Publish rate", "xyChart": {"dataSets": [
                    {"timeSeriesQuery": {"timeSeriesQueryLanguage": (
                        "fetch pubsub_topic | metric 'pubsub.googleapis.com/topic/send_request_count' | align 1m, rate(sum) | every 1m"
                    )}}
                ]}},
                {"title": "Backlog size (undelivered)", "xyChart": {"dataSets": [
                    {"timeSeriesQuery": {"timeSeriesQueryLanguage": (
                        "fetch pubsub_subscription | metric 'pubsub.googleapis.com/subscription/num_undelivered_messages' | align 1m, mean | every 1m"
                    )}}
                ]}},
                {"title": "DLQ count", "xyChart": {"dataSets": [
                    {"timeSeriesQuery": {"timeSeriesQueryLanguage": (
                        "fetch pubsub_subscription | metric 'pubsub.googleapis.com/subscription/dead_letter_message_count' | align 5m, rate(sum) | every 5m"
                    )}}
                ]}},
                {"title": "Backlog age (oldest unacked)", "xyChart": {"dataSets": [
                    {"timeSeriesQuery": {"timeSeriesQueryLanguage": (
                        "fetch pubsub_subscription | metric 'pubsub.googleapis.com/subscription/oldest_unacked_message_age' | align 1m, max | every 1m"
                    )}}
                ]}},
            ],
        },
    }


def build_external_apis_dashboard(project: str, prefix: str) -> Dict[str, Any]:
    return {
        "displayName": f"{prefix} External APIs (Together AI, Embeddings)",
        "gridLayout": {
            "columns": 2,
            "widgets": [
                {"title": "TogetherAI latency", "xyChart": {"dataSets": [{"timeSeriesQuery": {"timeSeriesQueryLanguage": "fetch generic_task | metric 'custom.googleapis.com/togetherai/latency' | align 1m, mean | every 1m"}}]}},
                {"title": "TogetherAI errors", "xyChart": {"dataSets": [{"timeSeriesQuery": {"timeSeriesQueryLanguage": "fetch generic_task | metric 'custom.googleapis.com/togetherai/error_rate' | align 1m, mean | every 1m"}}]}},
                {"title": "Embedding throughput", "xyChart": {"dataSets": [{"timeSeriesQuery": {"timeSeriesQueryLanguage": "fetch generic_task | metric 'custom.googleapis.com/embeddings/throughput' | align 1m, rate(sum) | every 1m"}}]}},
                {"title": "Embedding latency", "xyChart": {"dataSets": [{"timeSeriesQuery": {"timeSeriesQueryLanguage": "fetch generic_task | metric 'custom.googleapis.com/embeddings/latency' | align 1m, mean | every 1m"}}]}},
            ],
        },
    }

def build_alert_policies(prefix: str) -> List[Dict[str, Any]]:
    # Use MQL; latency in ms and error-rate ratio over 10 minutes
    service = 'candidate-enricher'
    latency_query = (
        "fetch run_revision | metric 'run.googleapis.com/request_latencies' "
        "| filter resource.service_name = '" + service + "' "
        "| align 5m, percentile(95) | every 5m"
    )
    error_ratio_query = (
        "fetch run_revision | metric 'run.googleapis.com/request_count' "
        "| filter resource.service_name = '" + service + "' "
        "| group_by [], [val_5xx: sum(if(metric.response_code_class = '5xx', metric.request_count, 0)), val_total: sum(metric.request_count)] | "
        "join | map [ratio: val_5xx / val_total] | every 1m"
    )
    return [
        {
            "displayName": f"{prefix} SLA - p95 latency > 1.2s (ms)",
            "conditions": [
                {
                    "conditionMonitoringQueryLanguage": {
                        "query": latency_query,
                        "duration": "600s",
                        "trigger": {"count": 1},
                        "comparison": "COMPARISON_GT",
                        "thresholdValue": 1200.0,
                    }
                }
            ],
            "combiner": "OR",
            "enabled": True,
            "notificationChannels": [],
        },
        {
            "displayName": f"{prefix} Error rate > 5% (5xx/total)",
            "conditions": [
                {
                    "conditionMonitoringQueryLanguage": {
                        "query": error_ratio_query,
                        "duration": "600s",
                        "trigger": {"count": 1},
                        "comparison": "COMPARISON_GT",
                        "thresholdValue": 0.05,
                    }
                }
            ],
            "combiner": "OR",
            "enabled": True,
            "notificationChannels": [],
        },
    ]


def create_or_update_dashboard(client, project: str, dashboard: Dict[str, Any], dry_run: bool) -> DashboardResult:
    name = dashboard.get("displayName", "Unnamed Dashboard")
    if dry_run or client is None:
        _log(f"[dry-run] Would upsert dashboard: {name}")
        return DashboardResult(name=name, created=False, resource=dashboard, errors=[])
    try:
        parent = f"projects/{project}"
        # Idempotency: check for existing by display name
        existing = [d for d in client.list_dashboards(parent=parent) if d.display_name == name]
        if existing:
            d = existing[0]
            # Build a typed Dashboard if possible; else pass dict
            try:
                dash_type = type(d)
                typed = dash_type(display_name=name)
                # For simplicity, update display name only; full widget reconciliation omitted
                updated = client.update_dashboard(dashboard=typing_cast_dashboard(d, dashboard))
                return DashboardResult(name=name, created=False, resource={"name": updated.name}, errors=[])
            except Exception:
                updated = client.update_dashboard(dashboard={**dashboard, "name": d.name})
                return DashboardResult(name=name, created=False, resource={"name": updated.name}, errors=[])
        created = client.create_dashboard(request={"parent": parent, "dashboard": dashboard})
        return DashboardResult(name=name, created=True, resource={"name": created.name}, errors=[])
    except Exception as e:
        return DashboardResult(name=name, created=False, resource=dashboard, errors=[str(e)])


def typing_cast_dashboard(existing_obj: Any, dash: Dict[str, Any]) -> Any:
    # Minimal builder to cast raw dict into typed Dashboard preserving name
    try:
        from google.cloud import monitoring_dashboard_v1  # type: ignore
        d = monitoring_dashboard_v1.types.Dashboard()
        d.name = existing_obj.name
        d.display_name = dash.get("displayName", existing_obj.display_name)
        # Assign raw layout dict; client library accepts struct pb
        if "gridLayout" in dash:
            d.grid_layout = dash["gridLayout"]  # type: ignore
        return d
    except Exception:
        return {**dash, "name": getattr(existing_obj, "name", "")}


def typing_build_alert_policy(policy: Dict[str, Any]) -> Any:
    from google.cloud import monitoring_v3  # type: ignore
    ap = monitoring_v3.types.AlertPolicy()
    if "name" in policy:
        ap.name = policy["name"]
    ap.display_name = policy.get("displayName", "")
    combiner = policy.get("combiner", "OR")
    ap.combiner = getattr(monitoring_v3.types.AlertPolicy.ConditionCombinerType, combiner)
    ap.enabled = policy.get("enabled", True)
    for cond in policy.get("conditions", []):
        c = monitoring_v3.types.AlertPolicy.Condition()
        if "conditionMonitoringQueryLanguage" in cond:
            mql = cond["conditionMonitoringQueryLanguage"]
            c.monitoring_query_language_condition.query = mql.get("query", "")
            c.monitoring_query_language_condition.duration = mql.get("duration", "600s")
            trg = mql.get("trigger", {}) or {}
            if "count" in trg:
                c.monitoring_query_language_condition.trigger.count = int(trg["count"])  # type: ignore
            comp = mql.get("comparison", "COMPARISON_GT")
            c.monitoring_query_language_condition.comparison = getattr(monitoring_v3.ComparisonType, comp)
            c.monitoring_query_language_condition.threshold_value = float(mql.get("thresholdValue", 0))
        elif "conditionAbsent" in cond:
            absent = cond["conditionAbsent"]
            c.condition_absent.filter = absent.get("filter", "")
            c.condition_absent.duration = absent.get("duration", "300s")
            for agg in (absent.get("aggregations") or []):
                c.condition_absent.aggregations.add(alignment_period=agg.get("alignmentPeriod", "60s"))
        ap.conditions.append(c)
    for ch in (policy.get("notificationChannels") or []):
        ap.notification_channels.append(ch)
    for k, v in (policy.get("userLabels") or {}).items():
        ap.user_labels[k] = v
    if policy.get("documentation"):
        ap.documentation.content = policy["documentation"].get("content", "")
    return ap


def create_or_update_alert_policy(client, project: str, policy: Dict[str, Any], dry_run: bool, channels: Optional[List[str]]) -> AlertPolicyResult:
    name = policy.get("displayName", "Unnamed Policy")
    if channels:
        policy["notificationChannels"] = channels
    if dry_run or client is None:
        _log(f"[dry-run] Would upsert alert policy: {name}")
        return AlertPolicyResult(name=name, created=False, conditions=policy.get("conditions", []), notification_channels=policy.get("notificationChannels", []), errors=[])
    try:
        parent = f"projects/{project}"
        policies = list(client.list_alert_policies(name=parent))
        match = next((p for p in policies if p.display_name == name), None)
        if match:
            policy["name"] = match.name
            try:
                updated = client.update_alert_policy(alert_policy=typing_build_alert_policy(policy))
            except Exception:
                updated = client.update_alert_policy(alert_policy=policy)
            return AlertPolicyResult(name=name, created=False, conditions=policy.get("conditions", []), notification_channels=policy.get("notificationChannels", []), errors=[])
        try:
            created = client.create_alert_policy(request={"name": parent, "alert_policy": typing_build_alert_policy(policy)})
        except Exception:
            created = client.create_alert_policy(request={"name": parent, "alert_policy": policy})
        return AlertPolicyResult(name=name, created=True, conditions=policy.get("conditions", []), notification_channels=policy.get("notificationChannels", []), errors=[])
    except Exception as e:
        return AlertPolicyResult(name=name, created=False, conditions=policy.get("conditions", []), notification_channels=policy.get("notificationChannels", []), errors=[str(e)])


def save_report(results: Dict[str, Any], reports_dir: str) -> str:
    path = os.path.join(reports_dir, "monitoring_dashboards_report.json")
    return save_json_report(path, results)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Setup Cloud Monitoring dashboards and alerting.")
    parser.add_argument("--project", required=True, help="GCP project ID")
    parser.add_argument("--prefix", default="Headhunter", help="Dashboard/Alert display name prefix")
    parser.add_argument("--reports-dir", default="reports", help="Directory to write reports")
    parser.add_argument("--apply", action="store_true", help="Apply changes (otherwise dry-run)")
    parser.add_argument("--channels", default="", help="Comma-separated notification channel names/IDs")
    parser.add_argument("--reconcile", action="store_true", help="Delete unmanaged resources with given prefix")
    args = parser.parse_args(argv)

    dry_run = not args.apply
    channels = [c.strip() for c in args.channels.split(",") if c.strip()]

    dash_api, mon_api = try_import_google_clients()
    dash_client = dash_api.DashboardsServiceClient() if dash_api and not dry_run else None
    pol_client = mon_api.AlertPolicyServiceClient() if mon_api and not dry_run else None

    resolved_channels: List[str] = []
    channel_errors: List[str] = []
    if channels and not dry_run and mon_api:
        resolved_channels, channel_errors = resolve_notification_channels(mon_api, args.project, channels)
        if channel_errors:
            _log(f"Channel resolution errors: {channel_errors}")

    _log(f"Starting dashboard setup (dry-run={dry_run}) for project={args.project}")

    dashboards = [
        build_cloud_run_dashboard(args.project, args.prefix),
        build_pgvector_dashboard(args.project, args.prefix),
        build_functions_dashboard(args.project, args.prefix),
        build_pubsub_dashboard(args.project, args.prefix),
        build_external_apis_dashboard(args.project, args.prefix),
    ]

    dash_results: List[DashboardResult] = []
    # Optional reconcile: delete dashboards/policies not matching prefix
    if args.reconcile and dash_client and not dry_run:
        parent = f"projects/{args.project}"
        for d in dash_client.list_dashboards(parent=parent):
            if d.display_name.startswith(args.prefix) and all(d.display_name != x.get("displayName") for x in dashboards):
                try:
                    dash_client.delete_dashboard(name=d.name)
                    _log(f"Deleted unmanaged dashboard: {d.display_name}")
                except Exception as e:
                    _log(f"Failed to delete dashboard {d.display_name}: {e}")

    for d in dashboards:
        dash_results.append(create_or_update_dashboard(dash_client, args.project, d, dry_run))

    alert_policies = build_alert_policies(args.prefix)
    alert_results: List[AlertPolicyResult] = []
    if args.reconcile and pol_client and not dry_run:
        parent = f"projects/{args.project}"
        existing = list(pol_client.list_alert_policies(name=parent))
        keep = {p["displayName"] for p in alert_policies}
        for pol in existing:
            if pol.display_name.startswith(args.prefix) and pol.display_name not in keep:
                try:
                    pol_client.delete_alert_policy(name=pol.name)
                    _log(f"Deleted unmanaged alert policy: {pol.display_name}")
                except Exception as e:
                    _log(f"Failed to delete alert policy {pol.display_name}: {e}")

    for p in alert_policies:
        alert_results.append(create_or_update_alert_policy(pol_client, args.project, p, dry_run, (resolved_channels or channels) or None))

    result = {
        "project": args.project,
        "dry_run": dry_run,
        "dashboards": [asdict(r) for r in dash_results],
        "alerts": [asdict(r) for r in alert_results],
        "timestamp": int(time.time()),
    }
    report_path = save_report(result, args.reports_dir)
    _log(f"Report written: {report_path}")
    _log("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
