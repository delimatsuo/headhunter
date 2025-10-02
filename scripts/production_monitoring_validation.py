#!/usr/bin/env python3
"""Monitoring and observability validation for Headhunter production."""
import argparse
import json
import time
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

try:
  from google.cloud import logging_v2  # type: ignore
  from google.cloud import monitoring_dashboard_v1  # type: ignore
  from google.cloud import monitoring_v3  # type: ignore
except ImportError:  # pragma: no cover - optional deps
  logging_v2 = None
  monitoring_dashboard_v1 = None
  monitoring_v3 = None

LOGGER = logging.getLogger("production_monitoring_validation")


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


def _contains_key(data: Any, target: str) -> bool:
  if isinstance(data, dict):
    for key, value in data.items():
      if key == target:
        return True
      if _contains_key(value, target):
        return True
  elif isinstance(data, list):
    return any(_contains_key(item, target) for item in data)
  return False


class MonitoringValidator:
  def __init__(self, project_id: str, config: Dict[str, Any], report_path: Optional[Path]) -> None:
    self.project_id = project_id
    self.config = config
    self.report_path = report_path

  def run(self) -> Dict[str, Any]:
    results = {
      "dashboards": self._validate_dashboards(),
      "alerts": self._validate_alerts(),
      "logs": self._validate_logging(),
      "cost_metrics": self._validate_cost_metrics(),
    }
    self._persist(results)
    return results

  def _validate_dashboards(self) -> List[Dict[str, Any]]:
    if monitoring_dashboard_v1 is None:
      return [{"status": "skip", "reason": "monitoring_dashboard_v1 missing"}]
    client = monitoring_dashboard_v1.DashboardsServiceClient()
    parent = f"projects/{self.project_id}"
    expected = {entry.get("name") for entry in self.config.get("monitoring", {}).get("dashboards", [])}
    dashboards = list(client.list_dashboards(parent=parent))
    names = {dashboard.display_name for dashboard in dashboards}
    missing = expected - names
    return [{
      "status": "pass" if not missing else "fail",
      "expected": list(expected),
      "found": list(names),
      "missing": list(missing),
    }]

  def _validate_alerts(self) -> List[Dict[str, Any]]:
    if monitoring_v3 is None:
      return [{"status": "skip", "reason": "monitoring_v3 missing"}]
    client = monitoring_v3.AlertPolicyServiceClient()
    parent = f"projects/{self.project_id}"
    policies = list(client.list_alert_policies(name=parent))
    expected = {entry.get("name") for entry in self.config.get("monitoring", {}).get("alertPolicies", [])}
    names = {policy.display_name for policy in policies}
    missing = expected - names
    return [{
      "status": "pass" if not missing else "fail",
      "expected": list(expected),
      "missing": list(missing),
    }]

  def _validate_logging(self) -> List[Dict[str, Any]]:
    if logging_v2 is None:
      return [{"status": "skip", "reason": "logging_v2 missing"}]
    client = logging_v2.Client(project=self.project_id)
    logger_name = f"projects/{self.project_id}/logs/run.googleapis.com%2Frequests"
    entries = list(client.list_entries(filter_=f"logName={logger_name}", page_size=10))
    tenant_labeled = 0
    cost_labeled = 0
    for entry in entries:
      api_repr = entry.to_api_repr()
      json_payload = api_repr.get("jsonPayload", {})
      proto_payload = api_repr.get("protoPayload", {})
      text_payload = api_repr.get("textPayload")
      resource_labels = api_repr.get("resource", {}).get("labels", {})
      entry_labels = api_repr.get("labels", {})

      tenant_detected = (
        _contains_key(json_payload, "tenant_id")
        or _contains_key(proto_payload, "tenant_id")
        or (isinstance(text_payload, str) and "tenant_id" in text_payload)
        or ("tenant_id" in resource_labels)
        or ("tenant_id" in entry_labels)
      )
      cost_detected = (
        _contains_key(json_payload, "cost_cents")
        or _contains_key(proto_payload, "cost_cents")
        or (isinstance(text_payload, str) and "cost_cents" in text_payload)
        or ("cost_cents" in entry_labels)
      )
      if tenant_detected:
        tenant_labeled += 1
      if cost_detected:
        cost_labeled += 1
    return [{
      "status": "pass" if tenant_labeled and cost_labeled else "fail",
      "sample_count": len(entries),
      "tenant_labeled": tenant_labeled,
      "cost_labeled": cost_labeled,
    }]

  def _validate_cost_metrics(self) -> List[Dict[str, Any]]:
    if monitoring_v3 is None:
      return [{"status": "skip", "reason": "monitoring_v3 missing"}]
    client = monitoring_v3.MetricServiceClient()
    project_name = f"projects/{self.project_id}"
    interval = monitoring_v3.TimeInterval()
    now = int(time.time())
    interval.end_time.seconds = now
    interval.start_time.seconds = now - 3600
    request = monitoring_v3.ListTimeSeriesRequest(
      name=project_name,
      filter='metric.type="custom.googleapis.com/headhunter/cost_cents"',
      interval=interval,
      view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
    )
    series = list(client.list_time_series(request=request))
    has_tenant = any(
      ("tenant_id" in (stream.metric.labels or {}))
      or ("tenant_id" in (stream.resource.labels or {}))
      for stream in series
    )
    return [{
      "status": "pass" if series and has_tenant else "fail",
      "series_count": len(series),
      "tenant_labeled": has_tenant,
    }]

  def _persist(self, results: Dict[str, Any]) -> None:
    if not self.report_path:
      return
    self.report_path.parent.mkdir(parents=True, exist_ok=True)
    with self.report_path.open("w", encoding="utf-8") as fh:
      json.dump(results, fh, indent=2)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Validate monitoring and observability setup")
  parser.add_argument("--config", default="config/testing/production-test-config.yaml")
  parser.add_argument("--environment", default="production")
  parser.add_argument("--project-id", required=True)
  parser.add_argument("--report", default=None)
  parser.add_argument("--verbose", action="store_true")
  return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
  args = parse_args(argv)
  logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")
  config = load_config(Path(args.config), args.environment)
  validator = MonitoringValidator(
    project_id=args.project_id,
    config=config,
    report_path=Path(args.report) if args.report else None,
  )
  results = validator.run()
  print(json.dumps(results, indent=2))
  failures = []
  for group in results.values():
    for entry in group:
      if entry.get("status") == "fail":
        failures.append(entry)
  return 1 if failures else 0


if __name__ == "__main__":
  sys.exit(main())
