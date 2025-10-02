#!/usr/bin/env python3
"""
Automated incident response playbooks for Headhunter monitoring alerts.

This script executes opinionated remediation flows for the primary alert classes
used across production: SLA violations, cost anomalies, service availability,
and performance degradations. It integrates with the runbook guidance captured in
`docs/PRODUCTION_OPERATIONS_RUNBOOK.md` while orchestrating the repetitive
checks, diagnostics collection, and first-line mitigations.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

LOG = logging.getLogger("incident_response")
DEFAULT_RUNBOOK = Path(__file__).resolve().parents[1] / "docs" / "PRODUCTION_OPERATIONS_RUNBOOK.md"
DEFAULT_COST_DATASET = "ops_observability"
DEFAULT_COST_VIEW = "v_cost_events"


def run_command(command: List[str], dry_run: bool = False) -> subprocess.CompletedProcess[str]:
    """Execute a shell command, respecting dry-run mode."""
    if dry_run:
        LOG.debug("DRY-RUN: %s", " ".join(command))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    LOG.debug("Executing command: %s", " ".join(command))
    return subprocess.run(command, check=False, text=True, capture_output=True)


@dataclass
class ResponseContext:
    project_id: str
    environment: str
    dry_run: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class AutomatedIncidentResponse:
    """Coordinates first-line remediation steps for common alerts."""

    def __init__(self, context: ResponseContext) -> None:
        self.context = context

    # --- Public orchestrators -------------------------------------------------
    def handle_event(self, event_type: str) -> None:
        LOG.info("Handling event '%s' for %s", event_type, self.context.environment)
        handlers = {
            "sla_violation": self._handle_sla_violation,
            "cost_anomaly": self._handle_cost_anomaly,
            "service_failure": self._handle_service_failure,
            "performance_degradation": self._handle_performance_regression,
        }

        if event_type not in handlers:
            raise ValueError(f"Unsupported event type: {event_type}")

        handlers[event_type]()

    # --- SLA violations -------------------------------------------------------
    def _handle_sla_violation(self) -> None:
        sla_target = self.context.metadata.get("sla_target", "p95 <= 1200ms")
        service = self.context.metadata.get("service", "search")
        LOG.info("Starting SLA remediation for service=%s target=%s", service, sla_target)

        self._collect_request_profiles(service)
        self._scale_service(service)
        self._warm_cache_if_needed(service)
        self._notify_runbook_section("SLA Violation", "See section 'SLA Playbooks'")

    # --- Cost anomalies -------------------------------------------------------
    def _handle_cost_anomaly(self) -> None:
        tenant = self.context.metadata.get("tenant_id", "all-tenants")
        magnitude = float(self.context.metadata.get("anomaly_score", 0))
        LOG.info("Investigating cost anomaly tenant=%s score=%.2f", tenant, magnitude)

        self._collect_cost_breakdown(tenant)
        self._flag_budget_controls(tenant)
        self._notify_runbook_section("Cost Anomaly", "See 'FinOps Response'")

    # --- Service failure ------------------------------------------------------
    def _handle_service_failure(self) -> None:
        service = self.context.metadata.get("service", "unknown-service")
        LOG.warning("Service failure detected for %s", service)

        self._run_health_checks(service)
        self._collect_recent_logs(service)
        self._trigger_safe_rollback(service)
        self._notify_runbook_section("Service Failure", "See 'Service Restoration'")

    # --- Performance degradation ---------------------------------------------
    def _handle_performance_regression(self) -> None:
        service = self.context.metadata.get("service", "search")
        metric = self.context.metadata.get("metric", "latency")
        LOG.info("Handling performance regression for %s (%s)", service, metric)

        self._collect_resource_metrics(service)
        self._adjust_scaling_parameters(service)
        self._rebuild_caches(service)
        self._notify_runbook_section("Performance Regression", "See 'Performance Tuning'")

    # --- Diagnostics helpers --------------------------------------------------
    def _collect_request_profiles(self, service: str) -> None:
        LOG.debug("Collecting request profiles for %s", service)
        run_command(
            [
                "gcloud",
                "logging",
                "read",
                f"resource.type=cloud_run_revision AND resource.labels.service_name={service}",
                "--limit=50",
                f"--project={self.context.project_id}",
            ],
            dry_run=self.context.dry_run,
        )

    def _scale_service(self, service: str) -> None:
        LOG.debug("Evaluating auto-scaling posture for %s", service)
        run_command(
            [
                "gcloud",
                "run",
                "services",
                "update",
                service,
                f"--project={self.context.project_id}",
                f"--region={self.context.metadata.get('region', 'us-central1')}",
                "--min-instances=2",
                "--max-instances=50",
            ],
            dry_run=self.context.dry_run,
        )

    def _warm_cache_if_needed(self, service: str) -> None:
        if service not in {"hh-search-svc", "hh-embed-svc", "hh-evidence-svc"}:
            return
        LOG.debug("Scheduling cache warm-up for %s", service)
        warmup_script = Path(__file__).resolve().parent / "cache_warmup.py"
        if not warmup_script.exists():
            LOG.warning("Cache warm-up script missing at %s; skipping", warmup_script)
            return
        run_command(
            [
                "python3",
                str(warmup_script),
                "--service",
                service,
                f"--project-id={self.context.project_id}",
                f"--environment={self.context.environment}",
            ],
            dry_run=self.context.dry_run,
        )

    def _collect_cost_breakdown(self, tenant: str) -> None:
        LOG.debug("Collecting cost breakdown for tenant=%s", tenant)
        dataset = self.context.metadata.get("cost_dataset", DEFAULT_COST_DATASET)
        cost_source = (
            self.context.metadata.get("cost_view")
            or self.context.metadata.get("cost_table")
            or DEFAULT_COST_VIEW
        )
        source_ref = f"{self.context.project_id}.{dataset}.{cost_source}"
        query = textwrap.dedent(
            f"""
            SELECT
              tenant_id,
              service,
              SUM(cost_cents) / 100 AS cost_usd,
              COUNT(*) AS events
            FROM `{source_ref}`
            WHERE (@tenant = 'all-tenants' OR tenant_id = @tenant)
              AND occurred_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
            GROUP BY tenant_id, service
            ORDER BY cost_usd DESC
            LIMIT 20
            """
        ).strip()
        run_command(
            [
                "bq",
                f"--project_id={self.context.project_id}",
                "query",
                "--use_legacy_sql=false",
                f"--parameter=tenant::STRING:{tenant}",
                query,
            ],
            dry_run=self.context.dry_run,
        )

    def _flag_budget_controls(self, tenant: str) -> None:
        LOG.debug("Flagging budget controls for tenant=%s", tenant)
        request_body = json.dumps({"tenant": tenant, "environment": self.context.environment})
        run_command(
            [
                "gcloud",
                "pubsub",
                "topics",
                "publish",
                "cost-anomaly-events",
                f"--project={self.context.project_id}",
                f"--message={request_body}",
            ],
            dry_run=self.context.dry_run,
        )

    def _run_health_checks(self, service: str) -> None:
        LOG.debug("Running health checks for %s", service)
        run_command(
            [
                "gcloud",
                "run",
                "services",
                "describe",
                service,
                f"--project={self.context.project_id}",
                f"--region={self.context.metadata.get('region', 'us-central1')}",
            ],
            dry_run=self.context.dry_run,
        )

    def _collect_recent_logs(self, service: str) -> None:
        LOG.debug("Collecting recent error logs for %s", service)
        run_command(
            [
                "gcloud",
                "logging",
                "read",
                f"resource.type=cloud_run_revision AND resource.labels.service_name={service} AND severity>=ERROR",
                "--limit=100",
                f"--project={self.context.project_id}",
            ],
            dry_run=self.context.dry_run,
        )

    def _trigger_safe_rollback(self, service: str) -> None:
        LOG.debug("Triggering safe rollback for %s", service)
        run_command(
            [
                "gcloud",
                "run",
                "services",
                "update-traffic",
                service,
                f"--project={self.context.project_id}",
                f"--region={self.context.metadata.get('region', 'us-central1')}",
                "--to-latest",
            ],
            dry_run=self.context.dry_run,
        )

    def _collect_resource_metrics(self, service: str) -> None:
        LOG.debug("Collecting CPU/memory metrics for %s", service)
        run_command(
            [
                "gcloud",
                "beta",
                "monitoring",
                "time-series",
                "list",
                f"projects/{self.context.project_id}",
                f"--filter=metric.type=\"run.googleapis.com/container/cpu/allocation_time\" AND resource.label.service_name=\"{service}\"",
                "--format=value(points[0].value.doubleValue)",
                "--limit=5",
            ],
            dry_run=self.context.dry_run,
        )

    def _adjust_scaling_parameters(self, service: str) -> None:
        LOG.debug("Adjusting scaling parameters for %s", service)
        run_command(
            [
                "gcloud",
                "run",
                "services",
                "update",
                service,
                f"--project={self.context.project_id}",
                f"--region={self.context.metadata.get('region', 'us-central1')}",
                "--set-env-vars=SCALING_MODE=AUTO",
            ],
            dry_run=self.context.dry_run,
        )

    def _rebuild_caches(self, service: str) -> None:
        LOG.debug("Rebuilding caches for %s", service)
        run_command(
            [
                "gcloud",
                "tasks",
                "enqueue",
                "cache-refresh",
                f"--project={self.context.project_id}",
                f"--region={self.context.metadata.get('region', 'us-central1')}",
                f"--payload={{\"service\":\"{service}\"}}",
            ],
            dry_run=self.context.dry_run,
        )

    def _notify_runbook_section(self, title: str, note: str) -> None:
        LOG.info("Refer to runbook: %s (%s)", title, DEFAULT_RUNBOOK)
        if note:
            LOG.info(note)


def parse_metadata(values: Iterable[str]) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"Invalid metadata '{item}'. Expected key=value format")
        key, raw_value = item.split("=", 1)
        try:
            metadata[key] = json.loads(raw_value)
        except json.JSONDecodeError:
            metadata[key] = raw_value
    return metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automated incident response playbooks")
    parser.add_argument("event_type", choices=[
        "sla_violation",
        "cost_anomaly",
        "service_failure",
        "performance_degradation",
    ])
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--environment", default="production")
    parser.add_argument("--cost-dataset", default=DEFAULT_COST_DATASET)
    parser.add_argument("--cost-view", default=DEFAULT_COST_VIEW)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--metadata",
        metavar="KEY=VALUE",
        nargs="*",
        default=[],
        help="Arbitrary metadata to steer remediation flow (JSON values supported)",
    )
    parser.add_argument("--log-level", default="INFO")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")
    metadata = parse_metadata(args.metadata)
    metadata.setdefault("cost_dataset", args.cost_dataset)
    metadata.setdefault("cost_view", args.cost_view)
    context = ResponseContext(
        project_id=args.project_id,
        environment=args.environment,
        dry_run=args.dry_run,
        metadata=metadata,
    )
    responder = AutomatedIncidentResponse(context)

    try:
        responder.handle_event(args.event_type)
    except Exception as exc:  # noqa: BLE001
        LOG.error("Failed to process incident: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
