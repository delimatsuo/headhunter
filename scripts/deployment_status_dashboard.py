#!/usr/bin/env python3
"""Display deployment status for Headhunter Cloud Run services."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

SERVICE_ORDER = [
    "hh-embed-svc",
    "hh-search-svc",
    "hh-rerank-svc",
    "hh-evidence-svc",
    "hh-eco-svc",
    "hh-enrich-svc",
    "hh-admin-svc",
    "hh-msgs-svc",
]


@dataclass
class ServiceStatus:
    name: str
    revision: Optional[str]
    url: Optional[str]
    status: Optional[str]
    traffic_percent: Optional[float]
    last_transition: Optional[str]
    ingress: Optional[str]


def run_cmd(cmd: List[str], *, dry_run: bool = False) -> subprocess.CompletedProcess[str]:
    if dry_run:
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def describe_service(service: str, project: str, region: str, environment: str, dry_run: bool) -> ServiceStatus:
    full_name = f"{service}-{environment}"
    result = run_cmd([
        "gcloud",
        "run",
        "services",
        "describe",
        full_name,
        "--project",
        project,
        "--region",
        region,
        "--platform",
        "managed",
        "--format",
        "json",
    ], dry_run=dry_run)
    if result.returncode != 0 or not result.stdout:
        return ServiceStatus(name=full_name, revision=None, url=None, status="missing", traffic_percent=None, last_transition=None, ingress=None)
    data = json.loads(result.stdout)
    traffic: Optional[float] = None
    if data.get("status", {}).get("traffic"):
        traffic = float(data["status"]["traffic"][0].get("percent", 0))
    status = None
    last_transition = None
    conditions = data.get("status", {}).get("conditions", [])
    for item in conditions:
        if item.get("type") == "Ready":
            status = item.get("status")
            last_transition = item.get("lastTransitionTime")
            break
    revision = data.get("status", {}).get("latestReadyRevisionName")
    ingress = data.get("metadata", {}).get("annotations", {}).get("run.googleapis.com/ingress")
    return ServiceStatus(
        name=full_name,
        revision=revision,
        url=data.get("status", {}).get("url"),
        status=status,
        traffic_percent=traffic,
        last_transition=last_transition,
        ingress=ingress,
    )


def load_uptime_checks(project: str, dry_run: bool) -> List[str]:
    result = run_cmd([
        "gcloud",
        "monitoring",
        "uptime-checks",
        "list",
        "--project",
        project,
        "--format",
        "value(displayName)",
    ], dry_run=dry_run)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def load_alert_policies(project: str, dry_run: bool) -> List[str]:
    result = run_cmd([
        "gcloud",
        "alpha",
        "monitoring",
        "policies",
        "list",
        "--project",
        project,
        "--format",
        "value(displayName)",
    ], dry_run=dry_run)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def format_table(statuses: List[ServiceStatus]) -> str:
    headers = ["Service", "Ready", "Traffic%", "Revision", "Ingress", "Last Transition"]
    rows: List[List[str]] = []
    for item in statuses:
        rows.append([
            item.name,
            item.status or "-",
            f"{item.traffic_percent:.0f}" if item.traffic_percent is not None else "-",
            item.revision or "-",
            item.ingress or "-",
            item.last_transition or "-",
        ])
    widths = [max(len(row[i]) for row in ([headers] + rows)) for i in range(len(headers))]
    def fmt(row: List[str]) -> str:
        return "  ".join(col.ljust(width) for col, width in zip(row, widths))
    lines = [fmt(headers), "  ".join("-" * w for w in widths)]
    lines.extend(fmt(row) for row in rows)
    return "\n".join(lines)


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deployment status dashboard")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--environment", default="production")
    parser.add_argument("--services", nargs="*", default=SERVICE_ORDER)
    parser.add_argument("--output", choices=["table", "json"], default="table")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    statuses: List[ServiceStatus] = []
    for svc in args.services:
        statuses.append(describe_service(svc, args.project_id, args.region, args.environment, args.dry_run))

    uptime = load_uptime_checks(args.project_id, args.dry_run)
    alerts = load_alert_policies(args.project_id, args.dry_run)

    timestamp = datetime.utcnow().isoformat() + "Z"
    payload: Dict[str, Any] = {
        "project": args.project_id,
        "region": args.region,
        "environment": args.environment,
        "generated": timestamp,
        "services": [asdict(item) for item in statuses],
        "uptimeChecks": uptime,
        "alertPolicies": alerts,
    }

    output: str
    if args.output == "json":
        output = json.dumps(payload, indent=2, sort_keys=True)
    else:
        output = format_table(statuses)
        output += "\n\nUptime checks: " + (", ".join(uptime) if uptime else "none")
        output += "\nAlert policies: " + (", ".join(alerts) if alerts else "none")
        output += f"\nGenerated: {timestamp}"

    if args.report:
        args.report.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
