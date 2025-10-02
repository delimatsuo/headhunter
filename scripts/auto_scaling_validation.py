#!/usr/bin/env python3
"""Auto-scaling and resource validation for Headhunter Cloud Run services."""
import argparse
import collections
import json
import logging
import math
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Optional, Tuple

import requests
import yaml

try:
  from google.cloud import monitoring_v3  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
  monitoring_v3 = None

LOGGER = logging.getLogger("auto_scaling_validation")
DEFAULT_TIMEOUT = 20


@dataclass
class RampStep:
  rps: float
  duration_seconds: int


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


def compute_percentile(data: List[float], percentile: float) -> Optional[float]:
  if not data:
    return None
  data_sorted = sorted(data)
  k = (len(data_sorted) - 1) * (percentile / 100)
  f = math.floor(k)
  c = math.ceil(k)
  if f == c:
    return data_sorted[int(k)]
  d0 = data_sorted[int(f)] * (c - k)
  d1 = data_sorted[int(c)] * (k - f)
  return d0 + d1


class OAuthClient:
  def __init__(self, token_url: str, client_id: str, client_secret: str, audience: Optional[str]) -> None:
    self.token_url = token_url
    self.client_id = client_id
    self.client_secret = client_secret
    self.audience = audience
    self._cached: Optional[Tuple[str, float]] = None

  def get_token(self) -> str:
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
    response = requests.post(self.token_url, data=payload, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
      raise RuntimeError("Token endpoint did not return access_token")
    expires_in = response.json().get("expires_in", 3600)
    self._cached = (token, now + expires_in)
    return token


class MetricCollector:
  def __init__(self) -> None:
    self.latencies: DefaultDict[str, List[float]] = collections.defaultdict(list)
    self.status_counts: DefaultDict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    self.cold_start_latencies: List[float] = []

  def record(self, key: str, latency_ms: float, status_code: int, cold_start: bool) -> None:
    self.latencies[key].append(latency_ms)
    self.status_counts[key][status_code] += 1
    if cold_start:
      self.cold_start_latencies.append(latency_ms)

  def summary(self) -> Dict[str, Any]:
    report: Dict[str, Any] = {}
    for key, values in self.latencies.items():
      statuses = self.status_counts[key]
      total = sum(statuses.values())
      errors = sum(count for code, count in statuses.items() if code >= 400)
      report[key] = {
        "samples": total,
        "error_rate": (errors / total) if total else 0,
        "avg_ms": sum(values) / len(values) if values else None,
        "p95_ms": compute_percentile(values, 95),
        "p99_ms": compute_percentile(values, 99),
      }
    if self.cold_start_latencies:
      report["cold_starts"] = {
        "count": len(self.cold_start_latencies),
        "avg_ms": statistics.mean(self.cold_start_latencies),
        "p95_ms": compute_percentile(self.cold_start_latencies, 95),
      }
    return report


class ScalingObserver:
  def __init__(self, project: str, location: str, service: str) -> None:
    self.project = project
    self.location = location
    self.service = service
    self.samples: List[Tuple[int, int]] = []
    self._client = monitoring_v3.MetricServiceClient() if monitoring_v3 else None
    self._seen: set[Tuple[int, int]] = set()
    self._latest_count: Optional[int] = None

  def snapshot(self) -> Optional[int]:
    if not self._client:
      LOGGER.debug("monitoring client unavailable, skipping snapshot")
      return None
    interval = monitoring_v3.TimeInterval()
    now = int(time.time())
    interval.end_time.seconds = now
    interval.start_time.seconds = now - 120
    filter_str = (
      'metric.type="run.googleapis.com/container/instances" '
      'resource.label."service_name"="{service}" '
      'resource.label."location"="{location}"'
    ).format(service=self.service, location=self.location)
    iterator = self._client.list_time_series(
      request={
        "name": f"projects/{self.project}",
        "filter": filter_str,
        "interval": interval,
        "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
      }
    )
    new_samples: List[Tuple[int, int]] = []
    for series in iterator:
      for point in series.points:
        ts = point.interval.end_time.seconds
        count = int(point.value.int64_value)
        key = (ts, count)
        if key in self._seen:
          continue
        self._seen.add(key)
        new_samples.append(key)
    if new_samples:
      new_samples.sort(key=lambda item: item[0])
      self.samples.extend(new_samples)
      self._latest_count = new_samples[-1][1]
    return self._latest_count


class AutoScalingValidator:
  def __init__(
    self,
    service_map: Dict[str, str],
    oauth: OAuthClient,
    tenant_id: str,
    report_path: Optional[Path],
    project_id: Optional[str],
    location: Optional[str],
    service_name: Optional[str],
    sla_targets: Dict[str, Any],
  ) -> None:
    self.service_map = service_map
    self.oauth = oauth
    self.tenant_id = tenant_id
    self.report_path = report_path
    self.observer = None
    if project_id and location and service_name and monitoring_v3:
      self.observer = ScalingObserver(project_id, location, service_name)
    self.metrics = MetricCollector()
    self.sla_targets = sla_targets
    self._last_instance_count: Optional[int] = None
    self._scaling_events: List[float] = []
    self._last_scaling_poll = 0.0
    self._scaling_poll_interval = 5.0
    self._scaling_event_window = 60.0

  def run(self, ramp: List[RampStep]) -> Dict[str, Any]:
    results: Dict[str, Any] = {"steps": []}
    if self.observer:
      self._update_scaling_events(force=True)
    for step in ramp:
      LOGGER.info("Executing ramp step at %.1f RPS for %ss", step.rps, step.duration_seconds)
      if self.observer:
        self._update_scaling_events(force=True)
      self._execute_step(step)
      step_summary = self.metrics.summary()
      results["steps"].append({
        "target_rps": step.rps,
        "duration_seconds": step.duration_seconds,
        "metrics": step_summary,
      })
    if self.observer:
      self._update_scaling_events(force=True)
      results["scaling_samples"] = self.observer.samples
    self._persist(results)
    results["sla_compliance"] = self._evaluate_sla(results)
    return results

  def _execute_step(self, step: RampStep) -> None:
    base_search = self.service_map["search"]
    base_rerank = self.service_map["rerank"]
    start = time.perf_counter()
    end = start + step.duration_seconds
    effective_rps = step.rps
    while time.perf_counter() < end:
      self._update_scaling_events()
      cycle_end = min(end, time.perf_counter() + 1)
      hybrid_calls = max(1, int(effective_rps * 0.7))
      rerank_calls = max(1, int(effective_rps * 0.3))
      for _ in range(hybrid_calls):
        self._call_endpoint(
          "search/hybrid",
          f"{base_search}/v1/search/hybrid",
          {
            "tenant_id": self.tenant_id,
            "query": "Backend engineer",
            "filters": {"locations": ["Remote"]},
            "page_size": 10,
          },
        )
      for _ in range(rerank_calls):
        self._call_endpoint(
          "search/rerank",
          f"{base_rerank}/v1/search/rerank",
          {
            "tenant_id": self.tenant_id,
            "query": "Backend engineer",
            "documents": [
              {"id": "cand-001", "text": "Cloud native expert"},
              {"id": "cand-002", "text": "Works with autoscaling"},
            ],
            "top_n": 2,
          },
        )
      time.sleep(max(0, cycle_end - time.perf_counter()))
    self._update_scaling_events(force=True)

  def _call_endpoint(self, metric: str, url: str, payload: Dict[str, Any]) -> None:
    headers = {
      "Authorization": f"Bearer {self.oauth.get_token()}",
      "X-Tenant-ID": self.tenant_id,
      "X-Request-ID": f"autoscale-{int(time.time()*1000)}",
    }
    start = time.perf_counter()
    response = requests.post(url, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT)
    end = time.perf_counter()
    latency_ms = (end - start) * 1000
    cold_header = response.headers.get("X-Cold-Start")
    cold_start = bool(cold_header and cold_header.lower() == "true")
    if not cold_start and self._has_recent_scale_out(end):
      cold_targets = self.sla_targets.get("coldStartTargets")
      target_value = cold_targets.get("maxColdStartMs") if isinstance(cold_targets, dict) else None
      threshold = float(target_value) if target_value is not None else 1000.0
      if latency_ms >= threshold:
        cold_start = True
    self.metrics.record(metric, latency_ms, response.status_code, bool(cold_start))

  def _persist(self, results: Dict[str, Any]) -> None:
    if not self.report_path:
      return
    self.report_path.parent.mkdir(parents=True, exist_ok=True)
    with self.report_path.open("w", encoding="utf-8") as fh:
      json.dump(results, fh, indent=2)

  def _update_scaling_events(self, force: bool = False) -> None:
    if not self.observer:
      return
    now = time.perf_counter()
    if not force and (now - self._last_scaling_poll) < self._scaling_poll_interval:
      return
    snapshot = self.observer.snapshot()
    self._last_scaling_poll = now
    if snapshot is None:
      return
    if self._last_instance_count is None:
      self._last_instance_count = snapshot
      return
    if snapshot > self._last_instance_count:
      LOGGER.debug("Detected scale-out event from %s to %s", self._last_instance_count, snapshot)
      self._scaling_events.append(now)
    self._last_instance_count = snapshot
    self._prune_scaling_events(now)

  def _prune_scaling_events(self, reference_time: float) -> None:
    if not self._scaling_events:
      return
    window = self._scaling_event_window
    self._scaling_events = [ts for ts in self._scaling_events if reference_time - ts <= window]

  def _has_recent_scale_out(self, reference_time: float) -> bool:
    self._prune_scaling_events(reference_time)
    return any(reference_time - ts <= self._scaling_event_window for ts in self._scaling_events)

  def _evaluate_sla(self, results: Dict[str, Any]) -> Dict[str, Any]:
    end_to_end_target = self.sla_targets.get("endToEndP95Ms")
    rerank_target = self.sla_targets.get("rerankP95Ms")
    cold_start_target = self.sla_targets.get("coldStartTargets", {}).get("maxColdStartMs")
    cold_start_rate_target = self.sla_targets.get("coldStartTargets", {}).get("acceptableColdStartRate")
    hybrid_p95: List[float] = []
    rerank_p95: List[float] = []
    cold_count = 0
    total_count = 0
    for step in results.get("steps", []):
      metrics = step.get("metrics", {})
      hybrid = metrics.get("search/hybrid", {})
      rerank = metrics.get("search/rerank", {})
      if hybrid.get("p95_ms") is not None:
        hybrid_p95.append(hybrid["p95_ms"])
      if rerank.get("p95_ms") is not None:
        rerank_p95.append(rerank["p95_ms"])
      cold = metrics.get("cold_starts", {})
      cold_count += cold.get("count", 0)
      total_count += hybrid.get("samples", 0) + rerank.get("samples", 0)
    compliance = {
      "max_hybrid_p95_ms": max(hybrid_p95) if hybrid_p95 else None,
      "max_rerank_p95_ms": max(rerank_p95) if rerank_p95 else None,
      "cold_start_count": cold_count,
      "cold_start_rate": (cold_count / total_count) if total_count else None,
    }
    if end_to_end_target is not None and hybrid_p95:
      compliance["hybrid_sla_pass"] = max(hybrid_p95) <= end_to_end_target
    if rerank_target is not None and rerank_p95:
      compliance["rerank_sla_pass"] = max(rerank_p95) <= rerank_target
    cold_p95 = self.metrics.summary().get("cold_starts", {}).get("p95_ms")
    if cold_start_target is not None and cold_p95 is not None:
      compliance["cold_start_latency_pass"] = cold_p95 <= cold_start_target
    if cold_start_rate_target is not None and compliance.get("cold_start_rate") is not None:
      compliance["cold_start_rate_pass"] = compliance["cold_start_rate"] <= cold_start_rate_target
    return compliance


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Validate Cloud Run auto-scaling behavior")
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
  parser.add_argument("--location", default=None)
  parser.add_argument("--service-name", default=None, help="Cloud Run service name for scaling observation")
  parser.add_argument("--verbose", action="store_true")
  return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
  args = parse_args(argv)
  logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")
  config = load_config(Path(args.config), args.environment)
  service_map = resolve_service_map(args.services)
  audience = args.audience or config.get("securityValidation", {}).get("oauth", {}).get("tokenAudience")
  oauth = OAuthClient(args.token_url, args.client_id, args.client_secret, audience)
  ramp_cfg = config.get("autoScaling", {})
  max_rps = int(ramp_cfg.get("maxInstances", 20)) * int(ramp_cfg.get("scalingThresholds", {}).get("requestConcurrency", 60))
  ramp_sequence = [1, 5, 10, 25, 50, 75, 100, 150]
  ramp: List[RampStep] = []
  for target in ramp_sequence:
    rps = min(target, max_rps)
    ramp.append(RampStep(rps=rps, duration_seconds=60))
  validator = AutoScalingValidator(
    service_map,
    oauth,
    args.tenant,
    Path(args.report) if args.report else None,
    args.project_id,
    args.location,
    args.service_name,
    config.get("autoScaling", {}),
  )
  results = validator.run(ramp)
  print(json.dumps(results, indent=2))
  compliance = results.get("sla_compliance", {})
  passes = all(value for key, value in compliance.items() if key.endswith("_pass")) if compliance else True
  return 0 if passes else 1


if __name__ == "__main__":
  sys.exit(main())
