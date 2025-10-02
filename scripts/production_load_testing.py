#!/usr/bin/env python3
"""Production load testing harness for Headhunter services."""
import argparse
import collections
import json
import logging
import math
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Optional, Sequence, Tuple

import requests
import yaml

try:
  from google.cloud import monitoring_v3  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
  monitoring_v3 = None

LOGGER = logging.getLogger("production_load_testing")
DEFAULT_TIMEOUT = 20


@dataclass
class TenantCredentials:
  tenant_id: str
  client_id: str
  client_secret: str


@dataclass
class LoadTargets:
  hybrid_rps: float
  rerank_rps: float
  duration_minutes: int
  burst_multiplier: float
  warmup_seconds: int
  cooldown_seconds: int
  target_concurrency: Optional[int] = None
  use_cache_namespace_header: bool = False


class InstanceScalingObserver:
  """Collect instance counts for a Cloud Run service via Cloud Monitoring."""

  def __init__(self, project_id: str, location: str, service_name: str) -> None:
    if monitoring_v3 is None:  # pragma: no cover - guarded by caller
      raise RuntimeError("monitoring_v3 client not available")
    self.project_id = project_id
    self.location = location
    self.service_name = service_name
    self._client = monitoring_v3.MetricServiceClient()
    self.samples: List[Dict[str, Any]] = []
    self._seen: set[Tuple[int, int]] = set()

  def poll(self) -> None:
    interval = monitoring_v3.TimeInterval()
    now = int(time.time())
    interval.end_time.seconds = now
    interval.start_time.seconds = now - 300
    filter_str = (
      'metric.type="run.googleapis.com/container/instances" '
      f'resource.label."service_name"="{self.service_name}" '
      f'resource.label."location"="{self.location}"'
    )
    request = monitoring_v3.ListTimeSeriesRequest(
      name=f"projects/{self.project_id}",
      filter=filter_str,
      interval=interval,
      view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
    )
    new_samples: List[Dict[str, Any]] = []
    for series in self._client.list_time_series(request=request):
      labels = dict(series.resource.labels)
      for point in series.points:
        timestamp = point.interval.end_time.seconds
        count = int(point.value.int64_value)
        key = (timestamp, count)
        if key in self._seen:
          continue
        self._seen.add(key)
        new_samples.append({"timestamp": timestamp, "instance_count": count, "resource": labels})
    if new_samples:
      new_samples.sort(key=lambda item: item["timestamp"])
      self.samples.extend(new_samples)


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
  if percentile <= 0:
    return min(data)
  if percentile >= 100:
    return max(data)
  data_sorted = sorted(data)
  rank = (percentile / 100) * (len(data_sorted) - 1)
  lower = math.floor(rank)
  upper = math.ceil(rank)
  if lower == upper:
    return data_sorted[int(rank)]
  lower_value = data_sorted[lower]
  upper_value = data_sorted[upper]
  return lower_value + (upper_value - lower_value) * (rank - lower)


class OAuthClient:
  def __init__(self, token_url: str, client_id: str, client_secret: str, audience: Optional[str]) -> None:
    self.token_url = token_url
    self.client_id = client_id
    self.client_secret = client_secret
    self.audience = audience
    self._lock = threading.Lock()
    self._token: Optional[Tuple[str, float]] = None

  def get_token(self) -> str:
    with self._lock:
      now = time.time()
      if self._token and self._token[1] - now > 60:
        return self._token[0]
      payload = {
        "grant_type": "client_credentials",
        "client_id": self.client_id,
        "client_secret": self.client_secret,
      }
      if self.audience:
        payload["audience"] = self.audience
      resp = requests.post(self.token_url, data=payload, timeout=DEFAULT_TIMEOUT)
      resp.raise_for_status()
      data = resp.json()
      token = data.get("access_token")
      if not token:
        raise RuntimeError("Token endpoint did not return access_token")
      expires_in = data.get("expires_in", 3600)
      self._token = (token, now + expires_in)
      return token


class MetricCollector:
  def __init__(self) -> None:
    self.latencies: DefaultDict[str, List[float]] = collections.defaultdict(list)
    self.status_counts: DefaultDict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    self.cache_hits: DefaultDict[str, int] = collections.defaultdict(int)
    self.cache_total: DefaultDict[str, int] = collections.defaultdict(int)
    self._lock = threading.Lock()

  def record(self, key: str, latency_ms: float, status_code: int, cache_header: Optional[str]) -> None:
    with self._lock:
      self.latencies[key].append(latency_ms)
      self.status_counts[key][status_code] += 1
      if cache_header is not None:
        self.cache_total[key] += 1
        if cache_header.lower() == "hit":
          self.cache_hits[key] += 1

  def summary(self, sla: Dict[str, Any]) -> Dict[str, Any]:
    with self._lock:
      latency_snapshot = {key: list(values) for key, values in self.latencies.items()}
      status_snapshot = {key: collections.Counter(counter) for key, counter in self.status_counts.items()}
      cache_hits_snapshot = dict(self.cache_hits)
      cache_total_snapshot = dict(self.cache_total)

    report: Dict[str, Any] = {}
    for key, values in latency_snapshot.items():
      statuses = status_snapshot.get(key, collections.Counter())
      total = sum(statuses.values())
      errors = sum(count for code, count in statuses.items() if code >= 400)
      cache_total = cache_total_snapshot.get(key, 0)
      cache_hits = cache_hits_snapshot.get(key, 0)
      cache_rate = (cache_hits / cache_total) if cache_total else None
      entry = {
        "samples": total,
        "error_rate": (errors / total) if total else 0,
        "avg_ms": sum(values) / len(values),
        "p95_ms": compute_percentile(values, 95),
        "p99_ms": compute_percentile(values, 99),
        "status_breakdown": dict(statuses),
      }
      if cache_rate is not None:
        entry["cache_hit_rate"] = cache_rate
        target = sla.get("cacheHitRateTarget")
        if target is not None:
          entry["cache_sla_pass"] = cache_rate >= target
      report[key] = entry
      if key == "search/hybrid" and sla.get("endToEndP95Ms") is not None:
        entry["sla_pass"] = (entry["p95_ms"] or float("inf")) <= sla["endToEndP95Ms"]
      if key == "search/rerank" and sla.get("rerankP95Ms") is not None:
        entry["sla_pass"] = (entry.get("p95_ms") or float("inf")) <= sla["rerankP95Ms"]
      if key == "evidence/get" and sla.get("cachedReadP95Ms") is not None:
        entry["sla_pass"] = (entry.get("p95_ms") or float("inf")) <= sla["cachedReadP95Ms"]
    return report


class LoadGenerator:
  def __init__(
    self,
    service_map: Dict[str, str],
    oauth: OAuthClient,
    tenant_id: str,
    metrics: Sequence[MetricCollector],
    cache_namespace: Optional[str] = None,
    cache_namespace_header_enabled: bool = False,
  ) -> None:
    self.service_map = service_map
    self.oauth = oauth
    self.tenant_id = tenant_id
    self.metrics = list(metrics)
    self.cache_namespace = cache_namespace or tenant_id
    self.cache_namespace_header_enabled = cache_namespace_header_enabled

  def execute_search(self) -> None:
    base = self.service_map["search"]
    url = f"{base}/v1/search/hybrid"
    body = {
      "tenant_id": self.tenant_id,
      "query": "Principal software engineer",
      "filters": {"skills": ["python", "cloud"]},
      "page_size": 10,
    }
    self._do_request("search/hybrid", url, "POST", body)

  def execute_rerank(self) -> None:
    base = self.service_map["rerank"]
    url = f"{base}/v1/search/rerank"
    body = {
      "tenant_id": self.tenant_id,
      "query": "Head of data platform",
      "documents": [
        {"id": f"cand-{idx:03d}", "text": "Seasoned data leader with ML background."}
        for idx in range(1, 11)
      ],
      "top_n": 5,
    }
    self._do_request("search/rerank", url, "POST", body)

  def execute_cached_evidence(self) -> None:
    base = self.service_map["evidence"]
    url = f"{base}/v1/evidence/demo-candidate"
    headers = {"X-Cache-Namespace": self.cache_namespace} if self.cache_namespace_header_enabled else None
    self._do_request("evidence/get", url, "GET", None, extra_headers=headers)

  def _do_request(
    self,
    metric_key: str,
    url: str,
    method: str,
    body: Optional[Dict[str, Any]],
    extra_headers: Optional[Dict[str, str]] = None,
  ) -> None:
    headers = {
      "Authorization": f"Bearer {self.oauth.get_token()}",
      "X-Tenant-ID": self.tenant_id,
      "X-Request-ID": f"load-{int(time.time()*1000)}",
    }
    if extra_headers:
      headers.update(extra_headers)
    start = time.perf_counter()
    response = requests.request(method, url, json=body, headers=headers, timeout=DEFAULT_TIMEOUT)
    latency_ms = (time.perf_counter() - start) * 1000
    cache_header = response.headers.get("X-Cache") if hasattr(response, "headers") else None
    for collector in self.metrics:
      collector.record(metric_key, latency_ms, response.status_code, cache_header)


def run_phase(
  name: str,
  duration_seconds: int,
  hybrid_rps: float,
  rerank_rps: float,
  cached_rps: float,
  generator: LoadGenerator,
  target_concurrency: Optional[int] = None,
) -> None:
  LOGGER.info(
    "Phase %s: hybrid=%.1frps rerank=%.1frps cached=%.1frps duration=%ss",
    name,
    hybrid_rps,
    rerank_rps,
    cached_rps,
    duration_seconds,
  )
  if duration_seconds <= 0:
    LOGGER.debug("Skipping %s phase due to non-positive duration", name)
    return

  total_rps = max(hybrid_rps + rerank_rps + cached_rps, 0.0)
  computed_concurrency = max(4, int(math.ceil(total_rps * 1.5))) if total_rps else 4
  pool_size = max(computed_concurrency, target_concurrency or 0)
  LOGGER.debug("Using thread pool of size %s for phase %s", pool_size, name)

  schedule = []
  now = time.perf_counter()
  if hybrid_rps > 0:
    schedule.append((generator.execute_search, 1.0 / hybrid_rps, now))
  if rerank_rps > 0:
    schedule.append((generator.execute_rerank, 1.0 / rerank_rps, now))
  if cached_rps > 0:
    schedule.append((generator.execute_cached_evidence, 1.0 / cached_rps, now))

  if not schedule:
    LOGGER.debug("Phase %s has no active request types", name)
    time.sleep(duration_seconds)
    return

  end_time = now + duration_seconds
  futures: List[Future[Any]] = []
  with ThreadPoolExecutor(max_workers=pool_size) as executor:
    while True:
      current = time.perf_counter()
      if current >= end_time:
        break
      dispatched = False
      for idx, (callable_fn, interval, next_ts) in enumerate(schedule):
        while next_ts <= current and next_ts < end_time:
          futures.append(executor.submit(callable_fn))
          dispatched = True
          next_ts += interval
        schedule[idx] = (callable_fn, interval, next_ts)
      if not dispatched:
        sleep_candidates = [max(0.0, next_ts - current) for _, _, next_ts in schedule]
        sleep_time = min(sleep_candidates) if sleep_candidates else 0.01
        time.sleep(min(max(sleep_time, 0.001), 0.05))

    # Flush any remaining invocations scheduled before end_time
    for callable_fn, interval, next_ts in schedule:
      while next_ts < end_time:
        futures.append(executor.submit(callable_fn))
        next_ts += interval

  for future in futures:
    try:
      future.result()
    except Exception as exc:  # pragma: no cover - surfaced to main
      LOGGER.error("Request execution failed during %s phase: %s", name, exc)
      raise


def parse_tenants(raw: List[str]) -> List[TenantCredentials]:
  tenants: List[TenantCredentials] = []
  for entry in raw:
    parts = entry.split(",")
    if len(parts) != 3:
      raise ValueError("Tenant entry must be tenant_id,client_id,client_secret")
    tenant_id, client_id, client_secret = [part.strip() for part in parts]
    tenants.append(TenantCredentials(tenant_id, client_id, client_secret))
  return tenants


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Production load testing")
  parser.add_argument("--config", default="config/testing/production-test-config.yaml")
  parser.add_argument("--environment", default="production")
  parser.add_argument("--service", action="append", dest="services", required=True, help="Service map service=url")
  parser.add_argument("--tenant", action="append", dest="tenants", required=True, help="tenant_id,client_id,client_secret")
  parser.add_argument("--token-url", default="https://oauth2.googleapis.com/token")
  parser.add_argument("--audience", default=None)
  parser.add_argument("--report", default=None)
  parser.add_argument("--verbose", action="store_true")
  parser.add_argument("--project-id", default=None, help="Project id for scaling observation")
  parser.add_argument("--location", default=None, help="Location for scaling observation")
  parser.add_argument("--observe-service", default=None, help="Service name for scaling observation")
  return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
  args = parse_args(argv)
  logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")
  config = load_config(Path(args.config), args.environment)
  service_map = resolve_service_map(args.services)
  tenants = parse_tenants(args.tenants)
  targets_cfg = config.get("loadTesting", {})
  targets = LoadTargets(
    hybrid_rps=float(targets_cfg.get("hybridSearchRps", 30)),
    rerank_rps=float(targets_cfg.get("rerankRps", 10)),
    duration_minutes=int(targets_cfg.get("testDurationMinutes", 10)),
    burst_multiplier=float(targets_cfg.get("burstMultiplier", 2)),
    warmup_seconds=int(targets_cfg.get("warmupSeconds", 60)),
    cooldown_seconds=int(targets_cfg.get("cooldownSeconds", 60)),
    target_concurrency=int(targets_cfg.get("targetConcurrency")) if targets_cfg.get("targetConcurrency") else None,
    use_cache_namespace_header=bool(targets_cfg.get("useCacheNamespaceHeader", False)),
  )

  overall_metrics = MetricCollector()
  results: Dict[str, Any] = {"tenants": {}, "phases": []}
  sla_targets = config.get("slaTargets", {})

  for tenant in tenants:
    tenant_metrics = MetricCollector()
    tenant_cfg = next(
      (item for item in targets_cfg.get("tenants", []) if item.get("tenantId") == tenant.tenant_id),
      {},
    )
    cache_namespace = tenant_cfg.get("cacheNamespace")
    oauth = OAuthClient(
      args.token_url,
      tenant.client_id,
      tenant.client_secret,
      args.audience or config.get("securityValidation", {}).get("oauth", {}).get("tokenAudience"),
    )
    generator = LoadGenerator(
      service_map,
      oauth,
      tenant.tenant_id,
      metrics=[tenant_metrics, overall_metrics],
      cache_namespace=cache_namespace,
      cache_namespace_header_enabled=targets.use_cache_namespace_header,
    )
    LOGGER.info("Warmup tenant %s for %ss", tenant.tenant_id, targets.warmup_seconds)
    run_phase(
      "warmup",
      targets.warmup_seconds,
      targets.hybrid_rps * 0.5,
      targets.rerank_rps * 0.5,
      targets.hybrid_rps * 0.2,
      generator,
      target_concurrency=targets.target_concurrency,
    )
    main_duration = targets.duration_minutes * 60
    LOGGER.info("Executing steady-state load for tenant %s", tenant.tenant_id)
    run_phase(
      "steady",
      main_duration,
      targets.hybrid_rps,
      targets.rerank_rps,
      targets.hybrid_rps * 0.3,
      generator,
      target_concurrency=targets.target_concurrency,
    )
    LOGGER.info("Executing burst phase for tenant %s", tenant.tenant_id)
    run_phase(
      "burst",
      int(main_duration / 2),
      targets.hybrid_rps * targets.burst_multiplier,
      targets.rerank_rps * targets.burst_multiplier,
      targets.hybrid_rps * targets.burst_multiplier * 0.3,
      generator,
      target_concurrency=targets.target_concurrency,
    )
    LOGGER.info("Cooldown tenant %s for %ss", tenant.tenant_id, targets.cooldown_seconds)
    run_phase(
      "cooldown",
      targets.cooldown_seconds,
      targets.hybrid_rps * 0.3,
      targets.rerank_rps * 0.2,
      targets.hybrid_rps * 0.1,
      generator,
      target_concurrency=targets.target_concurrency,
    )
    results["tenants"][tenant.tenant_id] = tenant_metrics.summary(sla_targets)

  results["overall"] = overall_metrics.summary(sla_targets)

  if args.observe_service and args.project_id and args.location:
    if monitoring_v3 is None:
      LOGGER.warning("google-cloud-monitoring not installed; skipping scaling observation")
    else:
      observer = InstanceScalingObserver(args.project_id, args.location, args.observe_service)
      observer.poll()
      results["scaling"] = observer.samples

  if args.report:
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as fh:
      json.dump(results, fh, indent=2)

  print(json.dumps(results, indent=2))
  hybrid_p95 = results["overall"].get("search/hybrid", {}).get("p95_ms", float("inf"))
  rerank_p95 = results["overall"].get("search/rerank", {}).get("p95_ms", float("inf"))
  cached_p95 = results["overall"].get("evidence/get", {}).get("p95_ms", float("inf"))
  cache_rate = results["overall"].get("evidence/get", {}).get("cache_hit_rate")
  cache_target = sla_targets.get("cacheHitRateTarget")
  cache_ok = True if cache_target is None or cache_rate is None else cache_rate >= cache_target
  sla_ok = (
    hybrid_p95 <= sla_targets.get("endToEndP95Ms", float("inf"))
    and rerank_p95 <= sla_targets.get("rerankP95Ms", float("inf"))
    and cached_p95 <= sla_targets.get("cachedReadP95Ms", float("inf"))
    and cache_ok
  )
  return 0 if sla_ok else 1


if __name__ == "__main__":
  sys.exit(main())
