#!/usr/bin/env python3
"""Cost analysis and optimization utility for Headhunter monitoring."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

LOG = logging.getLogger("cost_analysis")


def run_command(command: List[str], dry_run: bool = False) -> subprocess.CompletedProcess[str]:
    if dry_run:
        LOG.debug("DRY-RUN: %s", " ".join(command))
        return subprocess.CompletedProcess(command, 0, stdout="[]\n", stderr="")
    LOG.debug("Executing: %s", " ".join(command))
    return subprocess.run(command, check=False, text=True, capture_output=True)


def parse_bq_json(output: str) -> List[Dict[str, Any]]:
    output = output.strip()
    if not output:
        return []
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        LOG.debug("BigQuery output not valid JSON, returning empty list")
        return []


@dataclass
class CostAnalysisConfig:
    project_id: str
    dataset: str
    table: str
    lookback_days: int
    dry_run: bool = False


class CostAnalyzer:
    def __init__(self, config: CostAnalysisConfig) -> None:
        self.config = config

    def _time_window(self) -> str:
        start = datetime.utcnow() - timedelta(days=self.config.lookback_days)
        return start.strftime("%Y-%m-%dT%H:%M:%SZ")

    def query_costs(self) -> Dict[str, List[Dict[str, Any]]]:
        start_ts = self._time_window()
        base = f"{self.config.project_id}.{self.config.dataset}.{self.config.table}"

        per_service_sql = f"""
        SELECT service, SUM(cost_usd) AS cost_usd
        FROM `{base}`
        WHERE occurred_at >= TIMESTAMP('{start_ts}')
          AND log_type = 'cost_metric'
        GROUP BY service
        ORDER BY cost_usd DESC
        LIMIT 20
        """

        per_tenant_sql = f"""
        SELECT tenant_id, SUM(cost_usd) AS cost_usd
        FROM `{base}`
        WHERE occurred_at >= TIMESTAMP('{start_ts}')
          AND log_type = 'cost_metric'
        GROUP BY tenant_id
        ORDER BY cost_usd DESC
        LIMIT 20
        """

        trend_sql = f"""
        SELECT
          DATE(occurred_at) AS day,
          SUM(cost_usd) AS cost_usd
        FROM `{base}`
        WHERE occurred_at >= TIMESTAMP_SUB(TIMESTAMP('{start_ts}'), INTERVAL 14 DAY)
          AND log_type = 'cost_metric'
        GROUP BY day
        ORDER BY day ASC
        """

        def run_query(query: str) -> List[Dict[str, Any]]:
            result = run_command(
                [
                    "bq",
                    f"--project_id={self.config.project_id}",
                    "query",
                    "--use_legacy_sql=false",
                    "--format=json",
                    query,
                ],
                dry_run=self.config.dry_run,
            )
            if result.returncode != 0:
                LOG.warning("BigQuery query failed: %s", result.stderr.strip())
                return []
            return parse_bq_json(result.stdout)

        return {
            "per_service": run_query(per_service_sql),
            "per_tenant": run_query(per_tenant_sql),
            "trend": run_query(trend_sql),
        }

    def identify_anomalies(self, trend: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(trend) < 5:
            return {"status": "insufficient_data"}

        values = [float(row.get("cost_usd", 0)) for row in trend]
        mean = sum(values[:-1]) / max(len(values) - 1, 1)
        latest = values[-1]
        increase = (latest - mean) / mean if mean else 0
        return {
            "status": "anomalous" if increase >= 0.5 else "normal",
            "latest": latest,
            "baseline": mean,
            "increase_ratio": increase,
        }

    def optimization_recommendations(self, per_service: List[Dict[str, Any]]) -> List[str]:
        recommendations: List[str] = []
        for row in per_service[:5]:
            service = row.get("service")
            cost = float(row.get("cost_usd", 0))
            if service and cost > 100:
                recommendations.append(
                    f"Review scaling policies for {service}: ${cost:.2f} in the lookback window."
                )
            if service == "hh-rerank-svc":
                recommendations.append("Evaluate Together AI token usage and caching effectiveness.")
            if service == "hh-search-svc":
                recommendations.append("Increase cache TTL or tune vector query batching to reduce compute spend.")
        if not recommendations:
            recommendations.append("No high-cost services detected in the analysis window.")
        return recommendations

    def analyze(self) -> Dict[str, Any]:
        data = self.query_costs()
        anomalies = self.identify_anomalies(data.get("trend", []))
        recommendations = self.optimization_recommendations(data.get("per_service", []))
        return {
            "window_days": self.config.lookback_days,
            "per_service": data.get("per_service", []),
            "per_tenant": data.get("per_tenant", []),
            "trend": data.get("trend", []),
            "anomalies": anomalies,
            "recommendations": recommendations,
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze cost trends and surface optimization recommendations")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--dataset", default="ops_observability")
    parser.add_argument("--table", default="v_cost_events", help="Cost view/table name (default: v_cost_events)")
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")

    config = CostAnalysisConfig(
        project_id=args.project_id,
        dataset=args.dataset,
        table=args.table,
        lookback_days=args.lookback_days,
        dry_run=args.dry_run,
    )
    analyzer = CostAnalyzer(config)
    report = analyzer.analyze()

    if args.output:
        try:
            with args.output.open("w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2)
        except OSError as exc:
            LOG.error("Failed to write report: %s", exc)
            return 1

    LOG.info("Generated cost analysis for last %s day(s)", args.lookback_days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
