#!/usr/bin/env python3
"""SLA monitoring validation for Headhunter production services."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

try:
  from google.cloud import monitoring_v3  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
  monitoring_v3 = None

LOGGER = logging.getLogger("production_sla_monitoring")


@dataclass
class MetricQuery:
  name: str
  metric_type: str
  filter_labels: Dict[str, str]
  aligner: Any
  reducer: Optional[Any]
  target_key: str


DEFAULT_METRICS: Dict[str, MetricQuery] = {}


def build_default_metrics() -> Dict[str, MetricQuery]:
  if DEFAULT_METRICS:
    return DEFAULT_METRICS
  if monitoring_v3 is None:
    raise RuntimeError("google-cloud-monitoring dependency missing")
  defaults = {
    "end_to_end": MetricQuery(
      name="Hybrid Search Latency",
      metric_type="run.googleapis.com/request_latencies",
      filter_labels={"service_name": "hh-search-svc-production"},
      aligner=monitoring_v3.Aggregation.Aligner.ALIGN_PERCENTILE_95,
      reducer=None,
      target_key="endToEndP95Ms",
    ),
    "rerank": MetricQuery(
      name="Rerank Latency",
      metric_type="run.googleapis.com/request_latencies",
      filter_labels={"service_name": "hh-rerank-svc-production"},
      aligner=monitoring_v3.Aggregation.Aligner.ALIGN_PERCENTILE_95,
      reducer=None,
      target_key="rerankP95Ms",
    ),
    "cached": MetricQuery(
      name="Evidence Cached Latency",
      metric_type="run.googleapis.com/request_latencies",
      filter_labels={"service_name": "hh-evidence-svc-production", "response_code_class": "2xx"},
      aligner=monitoring_v3.Aggregation.Aligner.ALIGN_PERCENTILE_95,
      reducer=None,
      target_key="cachedReadP95Ms",
    ),
    "error_rate": MetricQuery(
      name="Error Rate",
      metric_type="run.googleapis.com/request_count",
      filter_labels={"service_name": "hh-search-svc-production"},
      aligner=monitoring_v3.Aggregation.Aligner.ALIGN_RATE,
      reducer=monitoring_v3.Aggregation.Reducer.REDUCE_SUM,
      target_key="errorRateTarget",
    ),
  }
  DEFAULT_METRICS.update(defaults)
  return DEFAULT_METRICS


def load_config(path: Path, environment: str) -> Dict[str, Any]:
  with path.open("r", encoding="utf-8") as fh:
    data = yaml.safe_load(fh)
  overrides = data.get("environments", {}).get(environment, {}).get("overrides", {})
  if overrides:
    data = deep_merge(data, overrides)
  return data


def deep_merge(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
  for key, value in overrides.items():
    if isinstance(value, dict) and isinstance(base.get(key), dict):
      base[key] = deep_merge(dict(base[key]), value)
    else:
      base[key] = value
  return base


class SLAMonitor:
  def __init__(
    self,
    project_id: str,
    config: Dict[str, Any],
    report_path: Optional[Path] = None,
    metrics: Optional[Dict[str, MetricQuery]] = None,
    window_hours: int = 24,
    baseline_days: int = 7,
  ) -> None:
    self.metrics = metrics if metrics is not None else (build_default_metrics() if monitoring_v3 else {})
    if monitoring_v3 is None:
      raise RuntimeError("google-cloud-monitoring is required for this script")
    self.client = monitoring_v3.MetricServiceClient()
    self.project_id = project_id
    self.config = config
    self.report_path = report_path
    self.window_hours = window_hours
    self.baseline_days = baseline_days

  def run(self) -> Dict[str, Any]:
    now = dt.datetime.utcnow()
    window_start = now - dt.timedelta(hours=self.window_hours)
    baseline_start = now - dt.timedelta(days=self.baseline_days, hours=self.window_hours)
    baseline_end = now - dt.timedelta(days=self.baseline_days)

    report = {"generated_at": now.isoformat() + "Z", "metrics": {}, "alerts": []}
    sla_targets = self.config.get("slaTargets", {})

    for key, query in self.metrics.items():
      current = self._fetch_time_series(query, window_start, now)
      baseline = self._fetch_time_series(query, baseline_start, baseline_end)
      current_value = current.get("value")
      baseline_value = baseline.get("value")
      breach = False
      comparison = None

      target_key = query.target_key
      target_value = sla_targets.get(target_key)
      if target_value is not None and current_value is not None:
        if key == "error_rate":
          breach = current_value > target_value
        else:
          breach = current_value > target_value
      if current_value is not None and baseline_value is not None and baseline_value:
        comparison = (current_value - baseline_value) / baseline_value

      report["metrics"][key] = {
        "description": query.name,
        "current": current_value,
        "baseline": baseline_value,
        "delta": comparison,
        "target": target_value,
        "timeseries": current.get("series"),
      }
      if breach:
        alert = {
          "metric": key,
          "description": query.name,
          "current": current_value,
          "target": target_value,
          "delta": comparison,
        }
        report["alerts"].append(alert)

    report["recommendations"] = self._generate_recommendations(report)
    self._persist(report)
    return report

  def _fetch_time_series(self, query: MetricQuery, start: dt.datetime, end: dt.datetime) -> Dict[str, Any]:
    project_name = f"projects/{self.project_id}"
    interval = monitoring_v3.TimeInterval()
    interval.start_time.seconds = int(start.timestamp())
    interval.end_time.seconds = int(end.timestamp())
    aggregation = monitoring_v3.Aggregation()
    aggregation.per_series_aligner = query.aligner
    aggregation.alignment_period.seconds = 300
    if query.reducer:
      aggregation.cross_series_reducer = query.reducer
      aggregation.group_by_fields.append("resource.label.service_name")

    filter_parts = [f'metric.type="{query.metric_type}"']
    for label, value in query.filter_labels.items():
      if label.startswith("metric.") or label.startswith("resource."):
        filter_parts.append(f'{label}="{value}"')
      elif label in {"response_code_class", "response_code"}:
        filter_parts.append(f'metric.label."{label}"="{value}"')
      else:
        filter_parts.append(f'resource.label."{label}"="{value}"')
    request = monitoring_v3.ListTimeSeriesRequest(
      name=project_name,
      filter=" AND ".join(filter_parts),
      interval=interval,
      aggregation=aggregation,
      view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
    )
    series_data: List[Dict[str, Any]] = []
    values: List[float] = []
    for series in self.client.list_time_series(request=request):
      points = []
      for point in series.points:
        points.append({
          "time": point.interval.end_time.seconds,
          "value": point.value.double_value or point.value.int64_value,
        })
        value = point.value.double_value or float(point.value.int64_value)
        values.append(value)
      series_data.append({
        "labels": dict(series.resource.labels),
        "points": points,
      })
    value = sum(values) / len(values) if values else None
    return {"value": value, "series": series_data}

  def _generate_recommendations(self, report: Dict[str, Any]) -> List[str]:
    recs: List[str] = []
    for metric_key, entry in report.get("metrics", {}).items():
      current = entry.get("current")
      target = entry.get("target")
      if current is None or target is None:
        continue
      if metric_key == "error_rate" and current > target:
        recs.append("Investigate recent deploys affecting search error rate; check logs for spikes and rollback if necessary.")
      elif current > target:
        recs.append(f"Latency for {metric_key} above target; consider scaling min instances or reviewing recent code paths.")
    if not recs:
      recs.append("All monitored metrics within SLA targets.")
    return recs

  def _persist(self, report: Dict[str, Any]) -> None:
    if not self.report_path:
      return
    self.report_path.parent.mkdir(parents=True, exist_ok=True)
    with self.report_path.open("w", encoding="utf-8") as fh:
      json.dump(report, fh, indent=2)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Validate production SLA compliance via monitoring")
  parser.add_argument("--config", default="config/testing/production-test-config.yaml")
  parser.add_argument("--environment", default="production")
  parser.add_argument("--project-id", required=True)
  parser.add_argument("--window-hours", type=int, default=24)
  parser.add_argument("--baseline-days", type=int, default=7)
  parser.add_argument("--report", default=None)
  parser.add_argument("--verbose", action="store_true")
  return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
  args = parse_args(argv)
  logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")
  config = load_config(Path(args.config), args.environment)
  if monitoring_v3 is None:
    LOGGER.error("google-cloud-monitoring dependency missing")
    return 2
  monitor = SLAMonitor(
    project_id=args.project_id,
    config=config,
    report_path=Path(args.report) if args.report else None,
    window_hours=args.window_hours,
    baseline_days=args.baseline_days,
  )
  report = monitor.run()
  print(json.dumps(report, indent=2))
  return 1 if report.get("alerts") else 0


if __name__ == "__main__":
  sys.exit(main())
