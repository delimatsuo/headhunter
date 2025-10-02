#!/usr/bin/env python3
"""Generate SLA compliance reports from Cloud Monitoring time series."""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

LOG = logging.getLogger("sla_compliance")


def run_command(command: List[str], dry_run: bool = False) -> subprocess.CompletedProcess[str]:
    if dry_run:
        LOG.debug("DRY-RUN: %s", " ".join(command))
        return subprocess.CompletedProcess(command, 0, stdout="0\n", stderr="")
    LOG.debug("Executing: %s", " ".join(command))
    return subprocess.run(command, check=False, text=True, capture_output=True)


@dataclass
class SLATarget:
    name: str
    metric_filter: str
    threshold: float
    comparison: str
    description: str

    def evaluate(self, project_id: str, alignment_window: str, dry_run: bool = False) -> Dict[str, Any]:
        command = [
            "gcloud",
            "beta",
            "monitoring",
            "time-series",
            "list",
            f"projects/{project_id}",
            f"--filter={self.metric_filter}",
            f"--aggregation.alignmentPeriod={alignment_window}",
            "--format=value(points[0].value.doubleValue)",
            "--limit=20",
        ]
        result = run_command(command, dry_run=dry_run)
        if result.returncode != 0:
            LOG.warning("Failed to fetch metric %s: %s", self.name, result.stderr.strip())
            values: List[float] = []
        else:
            try:
                values = [float(line.strip()) for line in result.stdout.splitlines() if line.strip()]
            except ValueError:
                LOG.warning("Unable to parse metric values for %s", self.name)
                values = []

        if not values:
            return {
                "name": self.name,
                "status": "no_data",
                "values": [],
                "threshold": self.threshold,
                "comparison": self.comparison,
                "description": self.description,
            }

        percentile = statistics.fmean(values)
        passed = percentile <= self.threshold if self.comparison == "le" else percentile >= self.threshold
        return {
            "name": self.name,
            "status": "pass" if passed else "fail",
            "observed": percentile,
            "values": values,
            "threshold": self.threshold,
            "comparison": self.comparison,
            "description": self.description,
        }


SLA_TARGETS: List[SLATarget] = [
    SLATarget(
        name="End-to-End Search Latency (p95)",
        metric_filter=\
            "metric.type=\"custom.googleapis.com/hh_search/end_to_end_latency_ms\" "
            "AND metric.label.percentile=\"p95\"",
        threshold=1200.0,
        comparison="le",
        description="Target p95 search latency ≤ 1.2s",
    ),
    SLATarget(
        name="Rerank Latency (p95)",
        metric_filter=\
            "metric.type=\"custom.googleapis.com/hh_rerank/latency_ms\" "
            "AND metric.label.percentile=\"p95\"",
        threshold=350.0,
        comparison="le",
        description="Target rerank p95 latency ≤ 350ms",
    ),
    SLATarget(
        name="Cached Evidence Latency (p95)",
        metric_filter=\
            "metric.type=\"custom.googleapis.com/hh_evidence/latency_ms\" "
            "AND metric.label.cache_state=\"hit\" "
            "AND metric.label.percentile=\"p95\"",
        threshold=250.0,
        comparison="le",
        description="Target cached evidence latency ≤ 250ms",
    ),
    SLATarget(
        name="Search Error Ratio",
        metric_filter="metric.type=\"custom.googleapis.com/hh_search/error_ratio\"",
        threshold=0.05,
        comparison="le",
        description="Error ratio must remain below 5%",
    ),
    SLATarget(
        name="Search Cache Hit Ratio",
        metric_filter="metric.type=\"custom.googleapis.com/hh_search/cache_hit_ratio\"",
        threshold=0.7,
        comparison="ge",
        description="Cache hit ratio must be ≥ 70%",
    ),
    SLATarget(
        name="API Availability",
        metric_filter="metric.type=\"custom.googleapis.com/hh_platform/service_availability_ratio\"",
        threshold=0.99,
        comparison="ge",
        description="Availability must remain ≥ 99%",
    ),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate SLA compliance reports")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--environment", default="production")
    parser.add_argument("--alignment", default="300s", help="Alignment window for metric aggregation")
    parser.add_argument("--output", type=Path, default=None, help="Optional path to write JSON report")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")

    report = {
        "project_id": args.project_id,
        "environment": args.environment,
        "alignment_window": args.alignment,
        "results": [],
    }

    failures = 0
    for target in SLA_TARGETS:
        outcome = target.evaluate(args.project_id, args.alignment, dry_run=args.dry_run)
        report["results"].append(outcome)
        if outcome.get("status") == "fail":
            failures += 1
            LOG.warning("SLA failure: %s observed=%s threshold=%s", target.name, outcome.get("observed"), target.threshold)
        elif outcome.get("status") == "no_data":
            LOG.warning("No data for SLA target %s", target.name)

    if args.output:
        try:
            with args.output.open("w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2)
        except OSError as exc:
            LOG.error("Unable to write report: %s", exc)
            return 1

    summary = {"passed": len(SLA_TARGETS) - failures, "failed": failures}
    LOG.info("SLA compliance summary: %s", summary)

    return 0 if failures == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
