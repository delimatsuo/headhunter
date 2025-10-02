#!/usr/bin/env python3
"""Production security validation suite for Headhunter Cloud Run deployment."""
import argparse
import collections
import json
import logging
import shutil
import subprocess
import sys
import time
import math
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from concurrent.futures import ThreadPoolExecutor

import requests
import yaml

LOGGER = logging.getLogger("production_security_validation")
DEFAULT_TIMEOUT = 15


@dataclass
class TenantCredential:
  tenant_id: str
  client_id: str
  client_secret: str


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


def parse_tenants(raw: List[str]) -> List[TenantCredential]:
  tenants: List[TenantCredential] = []
  for entry in raw:
    parts = entry.split(",")
    if len(parts) != 3:
      raise ValueError("Tenant entry must be tenant_id,client_id,client_secret")
    tenant_id, client_id, client_secret = [part.strip() for part in parts]
    tenants.append(TenantCredential(tenant_id, client_id, client_secret))
  return tenants


def compute_percentile(data: List[float], percentile: float) -> Optional[float]:
  if not data:
    return None
  data_sorted = sorted(data)
  k = (len(data_sorted) - 1) * (percentile / 100)
  floor = math.floor(k)
  ceil = math.ceil(k)
  if floor == ceil:
    return data_sorted[int(k)]
  lower = data_sorted[floor]
  upper = data_sorted[ceil]
  return lower * (ceil - k) + upper * (k - floor)


class OAuthValidator:
  def __init__(self, token_url: str, audience: Optional[str]) -> None:
    self.token_url = token_url
    self.audience = audience

  def fetch_token(self, credential: TenantCredential) -> str:
    payload = {
      "grant_type": "client_credentials",
      "client_id": credential.client_id,
      "client_secret": credential.client_secret,
    }
    if self.audience:
      payload["audience"] = self.audience
    resp = requests.post(self.token_url, data=payload, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
      raise RuntimeError("Token endpoint missing access_token")
    return token


class SecurityValidator:
  def __init__(
    self,
    config: Dict[str, Any],
    service_map: Dict[str, str],
    tenants: List[TenantCredential],
    oauth: OAuthValidator,
    project_id: Optional[str],
    region: Optional[str],
    report_path: Optional[Path] = None,
  ) -> None:
    self.config = config
    self.service_map = service_map
    self.tenants = tenants
    self.oauth = oauth
    self.project_id = project_id
    self.region = region
    self.report_path = report_path

  def run(self) -> Dict[str, Any]:
    results = {
      "oauth": [],
      "rate_limit": [],
      "cors": [],
      "auth_enforcement": [],
      "network": [],
      "secrets": [],
      "dependency_scan": [],
    }
    for tenant in self.tenants:
      results["oauth"].append(self._validate_oauth(tenant))
      results["rate_limit"].append(self._validate_rate_limit(tenant))
      results["cors"].append(self._validate_cors(tenant))
      results["auth_enforcement"].extend(self._validate_auth_enforcement(tenant))
    results["network"] = self._validate_network()
    results["secrets"] = self._validate_secrets()
    results["dependency_scan"] = self._run_dependency_scan()
    self._persist(results)
    return results

  def _validate_oauth(self, tenant: TenantCredential) -> Dict[str, Any]:
    try:
      token = self.oauth.fetch_token(tenant)
    except Exception as exc:  # pragma: no cover - runtime validation
      return {"tenant": tenant.tenant_id, "status": "fail", "reason": str(exc)}
    return {"tenant": tenant.tenant_id, "status": "pass", "token_preview": token[:10] + "..."}

  def _validate_rate_limit(self, tenant: TenantCredential) -> Dict[str, Any]:
    search_url = f"{self.service_map['search']}/v1/search/hybrid"
    token = self.oauth.fetch_token(tenant)
    headers = {
      "Authorization": f"Bearer {token}",
      "X-Tenant-ID": tenant.tenant_id,
    }
    rate_limits = self.config.get("securityValidation", {}).get("rateLimits", {})
    target_rps = float(rate_limits.get("hybridSearchRps", 30))
    burst_rps = max(float(rate_limits.get("burstRps", target_rps * 2)), 60.0)
    duration_seconds = float(rate_limits.get("burstDurationSeconds", 3))
    latency_threshold = float(rate_limits.get("latencySpikeMs", 800))
    total_requests = max(1, int(burst_rps * duration_seconds))
    max_workers = max(4, int(burst_rps))
    latencies: List[float] = []
    status_counts: collections.Counter[int] = collections.Counter()
    errors: List[str] = []
    lock = threading.Lock()

    def issue_request(index: int) -> None:
      scheduled = start_time + (index / burst_rps)
      sleep_for = scheduled - time.perf_counter()
      if sleep_for > 0:
        time.sleep(sleep_for)
      req_start = time.perf_counter()
      try:
        resp = requests.post(
          search_url,
          json={"tenant_id": tenant.tenant_id, "query": "Security validation"},
          headers=headers,
          timeout=DEFAULT_TIMEOUT,
        )
        latency = (time.perf_counter() - req_start) * 1000
        with lock:
          latencies.append(latency)
          status_counts[resp.status_code] += 1
      except requests.RequestException as exc:  # pragma: no cover - network interaction
        with lock:
          status_counts[-1] += 1
          errors.append(str(exc))

    start_time = time.perf_counter() + 0.1  # small offset to prime scheduling
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
      futures = [executor.submit(issue_request, idx) for idx in range(total_requests)]
      for future in futures:
        future.result()

    throttled = status_counts[429]
    allowed = sum(count for code, count in status_counts.items() if 0 <= code < 400)
    latency_p95 = compute_percentile(latencies, 95)
    latency_spike = latency_p95 is not None and latency_p95 >= latency_threshold
    status = "pass" if throttled > 0 or latency_spike else "fail"

    return {
      "tenant": tenant.tenant_id,
      "status": status,
      "requested_rps": burst_rps,
      "duration_seconds": duration_seconds,
      "requests_before_throttle": allowed,
      "throttled": throttled,
      "latency_p95_ms": latency_p95,
      "latency_spike": latency_spike,
      "errors": errors,
    }

  def _validate_cors(self, tenant: TenantCredential) -> Dict[str, Any]:
    search_url = f"{self.service_map['search']}/v1/search/hybrid"
    resp = requests.options(
      search_url,
      headers={
        "Origin": "https://app.headhunter.ai",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
      },
      timeout=DEFAULT_TIMEOUT,
    )
    allowed_origin = resp.headers.get("Access-Control-Allow-Origin")
    pass_cond = resp.status_code < 400 and allowed_origin in {"*", "https://app.headhunter.ai"}
    return {
      "tenant": tenant.tenant_id,
      "status": "pass" if pass_cond else "fail",
      "status_code": resp.status_code,
      "allow_origin": allowed_origin,
    }

  def _validate_auth_enforcement(self, tenant: TenantCredential) -> List[Dict[str, Any]]:
    base_url = self.service_map["admin"]
    tests: List[Dict[str, Any]] = []
    url = f"{base_url}/v1/admin/refresh-postings"
    resp = requests.post(url, timeout=DEFAULT_TIMEOUT)
    enforced = resp.status_code in (401, 403)
    tests.append({
      "endpoint": "admin_refresh_postings_no_auth",
      "status": "pass" if enforced else "fail",
      "status_code": resp.status_code,
    })
    token = self.oauth.fetch_token(tenant)
    headers = {
      "Authorization": f"Bearer {token}",
      "X-Tenant-ID": "other-tenant",
    }
    resp = requests.post(
      url,
      json={"tenant_id": tenant.tenant_id},
      headers=headers,
      timeout=DEFAULT_TIMEOUT,
    )
    enforced_tenant = resp.status_code in (401, 403)
    tests.append({
      "endpoint": "admin_refresh_postings_wrong_tenant",
      "status": "pass" if enforced_tenant else "fail",
      "status_code": resp.status_code,
    })
    return tests

  def _validate_network(self) -> List[Dict[str, Any]]:
    if not (self.project_id and self.region):
      return [{"status": "skip", "reason": "project or region not provided"}]
    if shutil.which("gcloud") is None:
      return [{"status": "skip", "reason": "gcloud CLI not available"}]
    results: List[Dict[str, Any]] = []
    connector_cmd = [
      "gcloud",
      "compute",
      "networks",
      "vpc-access",
      "connectors",
      "list",
      f"--project={self.project_id}",
      f"--region={self.region}",
      "--format=json",
    ]
    nat_cmd = [
      "gcloud",
      "compute",
      "routers",
      "nats",
      "list",
      f"--project={self.project_id}",
      "--format=json",
    ]
    try:
      connectors = json.loads(subprocess.check_output(connector_cmd, text=True))
      results.append({
        "check": "vpc_connector_present",
        "status": "pass" if connectors else "fail",
        "details": connectors,
      })
    except subprocess.CalledProcessError as exc:
      results.append({"check": "vpc_connector_present", "status": "fail", "reason": str(exc)})
    try:
      nats = json.loads(subprocess.check_output(nat_cmd, text=True))
      results.append({
        "check": "cloud_nat_present",
        "status": "pass" if nats else "fail",
        "details": nats,
      })
    except subprocess.CalledProcessError as exc:
      results.append({"check": "cloud_nat_present", "status": "fail", "reason": str(exc)})
    return results

  def _validate_secrets(self) -> List[Dict[str, Any]]:
    if not self.project_id:
      return [{"status": "skip", "reason": "project not provided"}]
    if shutil.which("gcloud") is None:
      return [{"status": "skip", "reason": "gcloud CLI not available"}]
    secret_cmd = [
      "gcloud",
      "secrets",
      "list",
      f"--project={self.project_id}",
      "--format=json",
    ]
    try:
      secrets = json.loads(subprocess.check_output(secret_cmd, text=True))
    except subprocess.CalledProcessError as exc:
      return [{"status": "fail", "reason": str(exc)}]
    violations = [s for s in secrets if not s["name"].startswith(f"projects/{self.project_id}/secrets/hh-")]
    return [{
      "status": "pass" if not violations else "fail",
      "secret_count": len(secrets),
      "violations": violations,
    }]

  def _run_dependency_scan(self) -> List[Dict[str, Any]]:
    pip_audit = shutil.which("pip-audit")
    if not pip_audit:
      return [{"status": "skip", "reason": "pip-audit not installed"}]
    try:
      output = subprocess.check_output([pip_audit, "-r", "cloud_run_worker/requirements.txt", "-f", "json"], text=True)
      findings = json.loads(output)
    except subprocess.CalledProcessError as exc:
      return [{"status": "fail", "reason": str(exc)}]
    return [{"status": "pass" if not findings else "fail", "findings": findings}]

  def _persist(self, results: Dict[str, Any]) -> None:
    if not self.report_path:
      return
    self.report_path.parent.mkdir(parents=True, exist_ok=True)
    with self.report_path.open("w", encoding="utf-8") as fh:
      json.dump(results, fh, indent=2)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Production security validation")
  parser.add_argument("--config", default="config/testing/production-test-config.yaml")
  parser.add_argument("--environment", default="production")
  parser.add_argument("--service", action="append", dest="services", required=True, help="service=url mapping")
  parser.add_argument("--tenant", action="append", dest="tenants", required=True, help="tenant_id,client_id,client_secret")
  parser.add_argument("--token-url", default="https://oauth2.googleapis.com/token")
  parser.add_argument("--audience", default=None)
  parser.add_argument("--project-id", default=None)
  parser.add_argument("--region", default=None)
  parser.add_argument("--report", default=None)
  parser.add_argument("--verbose", action="store_true")
  return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
  args = parse_args(argv)
  logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")
  config = load_config(Path(args.config), args.environment)
  service_map = resolve_service_map(args.services)
  tenants = parse_tenants(args.tenants)
  oauth = OAuthValidator(args.token_url, args.audience or config.get("securityValidation", {}).get("oauth", {}).get("tokenAudience"))
  validator = SecurityValidator(
    config=config,
    service_map=service_map,
    tenants=tenants,
    oauth=oauth,
    project_id=args.project_id,
    region=args.region,
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
