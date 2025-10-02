#!/usr/bin/env python3
"""Production performance benchmarking suite for Headhunter services."""
import argparse
import concurrent.futures
import json
import logging
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml

try:
  from google.cloud import monitoring_v3  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
  monitoring_v3 = None

LOGGER = logging.getLogger("performance_benchmarking")
DEFAULT_TIMEOUT = 20


@dataclass
class Scenario:
  name: str
  iterations: int
  concurrency: int
  delay: float


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


def resolve_service_map(raw: List[str]) -> Dict[str, str]:
  mapping: Dict[str, str] = {}
  for item in raw:
    if "=" not in item:
      raise ValueError(f"Invalid service mapping '{item}'")
    key, url = item.split("=", 1)
    mapping[key.strip()] = url.strip().rstrip("/")
  return mapping


class OAuthClient:
  def __init__(self, token_url: str, client_id: str, client_secret: str, audience: Optional[str]) -> None:
    self.token_url = token_url
    self.client_id = client_id
    self.client_secret = client_secret
    self.audience = audience
    self._cached: Optional[Tuple[str, float]] = None

  def token(self) -> str:
    now = time.time()
    if self._cached and self._cached[1] - now > 60:
      return self._cached[0]
    payload = {
      "grant_type": "client_credentials",
      "client_id": self.client_id,
      "client_secret": self.client_secret,
    }
    if self.audience:
      payload["audience"] = self.audience
    resp = requests.post(self.token_url, data=payload, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
      raise RuntimeError("Token endpoint missing access_token")
    self._cached = (token, now + resp.json().get("expires_in", 3600))
    return token


class MetricRecorder:
  def __init__(self) -> None:
    self.samples: Dict[str, List[float]] = {}
    self.status_codes: Dict[str, List[int]] = {}

  def record(self, key: str, latency_ms: float, status_code: int) -> None:
    self.samples.setdefault(key, []).append(latency_ms)
    self.status_codes.setdefault(key, []).append(status_code)

  def summary(self) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    for key, values in self.samples.items():
      statuses = self.status_codes.get(key, [])
      errors = sum(1 for code in statuses if code >= 400)
      data[key] = {
        "avg_ms": sum(values) / len(values),
        "p95_ms": percentile(values, 95),
        "p99_ms": percentile(values, 99),
        "samples": len(values),
        "error_rate": errors / len(statuses) if statuses else 0,
      }
    return data


def percentile(values: List[float], percentile_value: float) -> float:
  if not values:
    return 0.0
  ordered = sorted(values)
  k = (len(ordered) - 1) * (percentile_value / 100)
  f = math.floor(k)
  c = math.ceil(k)
  if f == c:
    return ordered[int(k)]
  return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


class PerformanceBenchmarker:
  def __init__(
    self,
    service_map: Dict[str, str],
    tenant_id: str,
    oauth: OAuthClient,
    scenarios: List[Scenario],
    report_path: Optional[Path],
    project_id: Optional[str],
  ) -> None:
    self.service_map = service_map
    self.tenant_id = tenant_id
    self.oauth = oauth
    self.scenarios = scenarios
    self.report_path = report_path
    self.project_id = project_id
    self.metrics = {}

  def run(self) -> Dict[str, Any]:
    report = {"scenarios": []}
    for scenario in self.scenarios:
      LOGGER.info("Benchmarking scenario %s", scenario.name)
      recorder = MetricRecorder()
      start = time.perf_counter()
      with concurrent.futures.ThreadPoolExecutor(max_workers=scenario.concurrency) as executor:
        futures = []
        for iteration in range(scenario.iterations):
          futures.append(executor.submit(self._exercise_services, recorder))
          time.sleep(scenario.delay)
        concurrent.futures.wait(futures)
      duration = time.perf_counter() - start
      report["scenarios"].append(
        {
          "name": scenario.name,
          "duration_seconds": duration,
          "metrics": recorder.summary(),
          "throughput_rps": sum(len(values) for values in recorder.samples.values()) / duration if duration else 0,
        }
      )
    report["resource_usage"] = self._collect_resource_metrics()
    self._persist(report)
    return report

  def _exercise_services(self, recorder: MetricRecorder) -> None:
    token = self.oauth.token()
    headers = {
      "Authorization": f"Bearer {token}",
      "X-Tenant-ID": self.tenant_id,
    }
    self._capture(recorder, "embeddings_generate", lambda: requests.post(
      f"{self.service_map['embeddings']}/v1/embeddings/generate",
      json={"tenant_id": self.tenant_id, "text": "Benchmarking embeddings."},
      headers=headers,
      timeout=DEFAULT_TIMEOUT,
    ))
    self._capture(recorder, "hybrid_search", lambda: requests.post(
      f"{self.service_map['search']}/v1/search/hybrid",
      json={"tenant_id": self.tenant_id, "query": "Benchmark search"},
      headers=headers,
      timeout=DEFAULT_TIMEOUT,
    ))
    self._capture(recorder, "rerank", lambda: requests.post(
      f"{self.service_map['rerank']}/v1/search/rerank",
      json={
        "tenant_id": self.tenant_id,
        "query": "Benchmark search",
        "documents": [
          {"id": f"cand-{i}", "text": "Benchmark document"}
          for i in range(10)
        ],
        "top_n": 5,
      },
      headers=headers,
      timeout=DEFAULT_TIMEOUT,
    ))
    self._capture(recorder, "evidence_get", lambda: requests.get(
      f"{self.service_map['evidence']}/v1/evidence/benchmark-candidate",
      headers=headers,
      timeout=DEFAULT_TIMEOUT,
    ))
    self._capture(recorder, "eco_search", lambda: requests.get(
      f"{self.service_map['eco']}/v1/occupations/search",
      params={"query": "benchmark"},
      headers=headers,
      timeout=DEFAULT_TIMEOUT,
    ))
    self._capture(recorder, "admin_refresh", lambda: requests.post(
      f"{self.service_map['admin']}/v1/admin/refresh-profiles",
      json={"tenant_id": self.tenant_id},
      headers=headers,
      timeout=DEFAULT_TIMEOUT,
    ))
    self._capture(recorder, "msgs_roles", lambda: requests.post(
      f"{self.service_map['msgs']}/v1/roles/template",
      json={"tenant_id": self.tenant_id, "role": "Benchmark"},
      headers=headers,
      timeout=DEFAULT_TIMEOUT,
    ))

  def _capture(self, recorder: MetricRecorder, key: str, fn) -> None:
    start = time.perf_counter()
    response = fn()
    latency_ms = (time.perf_counter() - start) * 1000
    recorder.record(key, latency_ms, response.status_code)

  def _collect_resource_metrics(self) -> Dict[str, Any]:
    if not self.project_id or monitoring_v3 is None:
      return {"status": "skip", "reason": "monitoring not available"}
    client = monitoring_v3.MetricServiceClient()
    project_name = f"projects/{self.project_id}"
    metrics = {}
    metric_types = {
      "cpu": "run.googleapis.com/container/cpu/utilization",
      "memory": "run.googleapis.com/container/memory/utilization",
    }
    end = int(time.time())
    start = end - 1800
    interval = monitoring_v3.TimeInterval()
    interval.start_time.seconds = start
    interval.end_time.seconds = end
    aggregation = monitoring_v3.Aggregation()
    aggregation.per_series_aligner = monitoring_v3.Aggregation.Aligner.ALIGN_MEAN
    aggregation.alignment_period.seconds = 300
    for key, metric_type in metric_types.items():
      request = monitoring_v3.ListTimeSeriesRequest(
        name=project_name,
        filter=f'metric.type="{metric_type}"',
        interval=interval,
        aggregation=aggregation,
        view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
      )
      samples: List[float] = []
      for series in client.list_time_series(request=request):
        for point in series.points:
          value = point.value.double_value or float(point.value.int64_value)
          samples.append(value)
      metrics[key] = {
        "avg": sum(samples) / len(samples) if samples else None,
        "max": max(samples) if samples else None,
      }
    return metrics

  def _persist(self, report: Dict[str, Any]) -> None:
    if not self.report_path:
      return
    self.report_path.parent.mkdir(parents=True, exist_ok=True)
    with self.report_path.open("w", encoding="utf-8") as fh:
      json.dump(report, fh, indent=2)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Benchmark production service performance")
  parser.add_argument("--config", default="config/testing/production-test-config.yaml")
  parser.add_argument("--environment", default="production")
  parser.add_argument("--service", action="append", dest="services", required=True, help="service=url mapping")
  parser.add_argument("--tenant", required=True)
  parser.add_argument("--client-id", required=True)
  parser.add_argument("--client-secret", required=True)
  parser.add_argument("--token-url", default="https://oauth2.googleapis.com/token")
  parser.add_argument("--audience", default=None)
  parser.add_argument("--report", default=None)
  parser.add_argument("--project-id", default=None)
  parser.add_argument("--verbose", action="store_true")
  return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
  args = parse_args(argv)
  logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")
  config = load_config(Path(args.config), args.environment)
  service_map = resolve_service_map(args.services)
  scenarios = [
    Scenario("baseline", iterations=20, concurrency=4, delay=0.1),
    Scenario("normal_load", iterations=40, concurrency=8, delay=0.05),
    Scenario("peak_load", iterations=60, concurrency=12, delay=0.02),
    Scenario("burst", iterations=30, concurrency=16, delay=0.0),
  ]
  oauth = OAuthClient(
    args.token_url,
    args.client_id,
    args.client_secret,
    args.audience or config.get("securityValidation", {}).get("oauth", {}).get("tokenAudience"),
  )
  benchmarker = PerformanceBenchmarker(
    service_map=service_map,
    tenant_id=args.tenant,
    oauth=oauth,
    scenarios=scenarios,
    report_path=Path(args.report) if args.report else None,
    project_id=args.project_id,
  )
  report = benchmarker.run()
  print(json.dumps(report, indent=2))
  failures = []
  for scenario in report.get("scenarios", []):
    metrics = scenario.get("metrics", {})
    for key, metric in metrics.items():
      if metric.get("error_rate", 0) > config.get("slaTargets", {}).get("errorRateTarget", 1):
        failures.append(f"High error rate for {key} in scenario {scenario['name']}")
  return 1 if failures else 0


if __name__ == "__main__":
  sys.exit(main())
