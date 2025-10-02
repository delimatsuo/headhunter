#!/usr/bin/env python3
"""Publish aggregated cost metrics to Cloud Monitoring."""

from __future__ import annotations

import argparse
import json
import logging
import math
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

try:
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
except ImportError as exc:  # pragma: no cover - handled at runtime
    google = None
    AuthorizedSession = None  # type: ignore[assignment]
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None

LOG = logging.getLogger("publish_cost_metrics")
METRIC_BASE = "custom.googleapis.com/hh_costs"
DEFAULT_DATASET = "ops_observability"
DEFAULT_SOURCE = "v_cost_events"
DEFAULT_LOOKBACK_MINUTES = 60
DEFAULT_BIGQUERY_LOCATION = "US"
MAX_BATCH = 200


class MetricPublisherError(RuntimeError):
    """Raised when publishing fails."""


def run_bq_query(
    project_id: str,
    location: str,
    query: str,
    params: Optional[Mapping[str, Tuple[str, Any]]] = None,
    dry_run: bool = False,
) -> List[Dict[str, Any]]:
    """Execute a BigQuery query via the bq CLI and return JSON rows."""

    command: List[str] = [
        "bq",
        f"--project_id={project_id}",
        "--location",
        location,
        "query",
        "--use_legacy_sql=false",
        "--format=json",
        "--nouse_cache",
        "--quiet",
    ]

    if params:
        for name, (param_type, value) in params.items():
            command.append(f"--parameter={name}:{param_type}:{value}")

    command.append(query)

    if dry_run:
        LOG.debug("DRY-RUN: %s", " ".join(command))
        return []

    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        LOG.error("BigQuery query failed: %s", result.stderr.strip())
        raise MetricPublisherError("BigQuery query failed")

    output = result.stdout.strip()
    if not output:
        return []

    try:
        return json.loads(output)
    except json.JSONDecodeError:
        LOG.warning("Failed to decode BigQuery JSON output; returning empty result")
        return []


def chunked(sequence: Iterable[Any], size: int) -> Iterable[List[Any]]:
    buffer: List[Any] = []
    for item in sequence:
        buffer.append(item)
        if len(buffer) == size:
            yield buffer
            buffer = []
    if buffer:
        yield buffer


def iso_timestamp_now() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def clamp_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def build_series(metric: str, service_label: str, tenant_label: str, value: float, project_id: str, end_time: str) -> Dict[str, Any]:
    return {
        "metric": {
            "type": metric,
            "labels": {
                "service": service_label,
                "tenant": tenant_label,
            },
        },
        "resource": {
            "type": "global",
            "labels": {"project_id": project_id},
        },
        "points": [
            {
                "interval": {"endTime": end_time},
                "value": {"doubleValue": value},
            }
        ],
    }


def fetch_cost_aggregations(
    project_id: str,
    dataset: str,
    source: str,
    location: str,
    lookback_minutes: int,
    dry_run: bool,
) -> Dict[str, List[Dict[str, Any]]]:
    table_ref = f"{project_id}.{dataset}.{source}"
    params = {"lookback_minutes": ("INT64", lookback_minutes)}

    service_query = f"""
    SELECT
      COALESCE(service, 'unspecified') AS service,
      SUM(cost_usd) AS cost_usd
    FROM `{table_ref}`
    WHERE log_type = 'cost_metric'
      AND occurred_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @lookback_minutes MINUTE)
    GROUP BY service
    HAVING cost_usd > 0
    ORDER BY cost_usd DESC
    LIMIT 50
    """

    tenant_query = f"""
    SELECT
      COALESCE(tenant_id, 'unspecified') AS tenant_id,
      SUM(cost_usd) AS cost_usd
    FROM `{table_ref}`
    WHERE log_type = 'cost_metric'
      AND occurred_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @lookback_minutes MINUTE)
    GROUP BY tenant_id
    HAVING cost_usd > 0
    ORDER BY cost_usd DESC
    LIMIT 50
    """

    api_query = f"""
    SELECT
      COALESCE(service, 'unspecified') AS service,
      COALESCE(tenant_id, 'unspecified') AS tenant_id,
      COALESCE(api_name, 'unspecified') AS api_name,
      SUM(cost_usd) AS cost_usd,
      COUNT(*) AS events
    FROM `{table_ref}`
    WHERE log_type = 'cost_metric'
      AND occurred_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @lookback_minutes MINUTE)
    GROUP BY service, tenant_id, api_name
    HAVING events > 0
    ORDER BY cost_usd DESC
    LIMIT 100
    """

    totals_query = f"""
    SELECT
      SUM(IF(DATE(occurred_at) = CURRENT_DATE(), cost_usd, 0)) AS daily_total,
      SUM(IF(occurred_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY), cost_usd, 0)) AS weekly_total,
      SUM(IF(occurred_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY), cost_usd, 0)) AS monthly_total
    FROM `{table_ref}`
    WHERE log_type = 'cost_metric'
      AND occurred_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    """

    rerank_query = f"""
    SELECT
      COALESCE(service, 'unspecified') AS service,
      COALESCE(tenant_id, 'unspecified') AS tenant_id,
      SUM(cost_usd) AS cost_usd
    FROM `{table_ref}`
    WHERE log_type = 'cost_metric'
      AND source = 'together_ai_api'
      AND occurred_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @lookback_minutes MINUTE)
    GROUP BY service, tenant_id
    HAVING cost_usd > 0
    LIMIT 50
    """

    return {
        "service": run_bq_query(project_id, location, service_query, params, dry_run=dry_run),
        "tenant": run_bq_query(project_id, location, tenant_query, params, dry_run=dry_run),
        "api": run_bq_query(project_id, location, api_query, params, dry_run=dry_run),
        "totals": run_bq_query(project_id, location, totals_query, None, dry_run=dry_run),
        "rerank": run_bq_query(project_id, location, rerank_query, params, dry_run=dry_run),
    }


def ensure_session() -> AuthorizedSession:
    if IMPORT_ERROR:
        raise MetricPublisherError(
            "google-auth is required to publish metrics; install google-auth and google-auth-httplib2"
        ) from IMPORT_ERROR

    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/monitoring.write"])
    return AuthorizedSession(credentials)


def publish_time_series(
    session: AuthorizedSession,
    project_id: str,
    series: List[Dict[str, Any]],
    dry_run: bool = False,
) -> None:
    if not series:
        LOG.info("No cost metrics to publish")
        return

    url = f"https://monitoring.googleapis.com/v3/projects/{project_id}/timeSeries"
    for batch in chunked(series, MAX_BATCH):
        if dry_run:
            LOG.debug("DRY-RUN: would publish %s time series", len(batch))
            continue
        response = session.post(url, json={"timeSeries": batch}, timeout=30)
        if response.status_code >= 400:
            LOG.error("Failed to publish time series: %s", response.text)
            raise MetricPublisherError("Cloud Monitoring API rejected time series payload")
    LOG.info("Published %s cost metric time series", len(series))


def build_time_series(
    project_id: str,
    aggregations: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    end_time = iso_timestamp_now()
    series: List[Dict[str, Any]] = []

    for row in aggregations.get("service", []):
        value = clamp_float(row.get("cost_usd"))
        if value is None or value <= 0:
            continue
        service_label = str(row.get("service") or "unspecified")
        series.append(
            build_series(
                f"{METRIC_BASE}/service_cost_usd",
                service_label,
                "all",
                value,
                project_id,
                end_time,
            )
        )

    for row in aggregations.get("tenant", []):
        value = clamp_float(row.get("cost_usd"))
        if value is None or value <= 0:
            continue
        tenant_label = str(row.get("tenant_id") or "unspecified")
        series.append(
            build_series(
                f"{METRIC_BASE}/tenant_cost_usd",
                "all",
                tenant_label,
                value,
                project_id,
                end_time,
            )
        )

    for row in aggregations.get("api", []):
        events = clamp_float(row.get("events")) or 0
        total_cost = clamp_float(row.get("cost_usd")) or 0
        if events <= 0 or total_cost <= 0:
            continue
        average_cost = total_cost / events
        service_label = str(row.get("service") or "unspecified")
        tenant_label = str(row.get("api_name") or "unspecified")
        series.append(
            build_series(
                f"{METRIC_BASE}/api_cost_usd",
                service_label,
                tenant_label,
                average_cost,
                project_id,
                end_time,
            )
        )

    totals = aggregations.get("totals", [])
    if totals:
        total_row = totals[0]
        for key, metric_name in [
            ("daily_total", "daily_total_usd"),
            ("weekly_total", "weekly_total_usd"),
            ("monthly_total", "monthly_total_usd"),
        ]:
            value = clamp_float(total_row.get(key))
            if value is None or value <= 0:
                continue
            series.append(
                build_series(
                    f"{METRIC_BASE}/{metric_name}",
                    "all",
                    "all",
                    value,
                    project_id,
                    end_time,
                )
            )

    for row in aggregations.get("rerank", []):
        value_usd = clamp_float(row.get("cost_usd"))
        if value_usd is None or value_usd <= 0:
            continue
        service_label = str(row.get("service") or "unspecified")
        tenant_label = str(row.get("tenant_id") or "unspecified")
        series.append(
            build_series(
                "custom.googleapis.com/hh_rerank/together_cost_cents",
                service_label,
                tenant_label,
                value_usd * 100,
                project_id,
                end_time,
            )
        )

    return series


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish aggregated cost metrics to Cloud Monitoring")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--table", default=DEFAULT_SOURCE)
    parser.add_argument("--bigquery-location", default=DEFAULT_BIGQUERY_LOCATION)
    parser.add_argument("--lookback-minutes", type=int, default=DEFAULT_LOOKBACK_MINUTES)
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")

    try:
        aggregations = fetch_cost_aggregations(
            project_id=args.project_id,
            dataset=args.dataset,
            source=args.table,
            location=args.bigquery_location,
            lookback_minutes=args.lookback_minutes,
            dry_run=args.dry_run,
        )
        series = build_time_series(args.project_id, aggregations)
        if args.dry_run:
            LOG.info("Dry run complete; computed %s time series", len(series))
            return 0
        session = ensure_session()
        publish_time_series(session, args.project_id, series, dry_run=False)
    except MetricPublisherError as exc:
        LOG.error("Failed to publish cost metrics: %s", exc)
        return 1
    except Exception as exc:  # noqa: BLE001
        LOG.exception("Unexpected failure while publishing cost metrics: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
