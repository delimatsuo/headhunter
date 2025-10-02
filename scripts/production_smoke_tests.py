#!/usr/bin/env python3
"""Production smoke test suite for the Headhunter Cloud Run services."""
import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
import yaml

DEFAULT_TIMEOUT = 15
LOGGER = logging.getLogger("production_smoke_tests")


@dataclass
class EndpointCheck:
  service: str
  name: str
  method: str
  path: str
  payload: Optional[Dict[str, Any]] = None
  expect_status: Iterable[int] = (200, 201, 202)
  require_json: bool = True
  headers: Optional[Dict[str, str]] = None


SMOKE_ENDPOINTS: List[EndpointCheck] = [
  EndpointCheck(
    service="embeddings",
    name="generate",
    method="POST",
    path="/v1/embeddings/generate",
    payload={"tenant_id": "{tenant}", "text": "Candidate has 8 years of Go experience."},
  ),
  EndpointCheck(
    service="embeddings",
    name="upsert",
    method="POST",
    path="/v1/embeddings/upsert",
    payload={
      "tenant_id": "{tenant}",
      "vectors": [
        {"id": "profile-001", "values": [0.12, 0.08, 0.95], "metadata": {"source": "smoke"}}
      ],
    },
  ),
  EndpointCheck(
    service="embeddings",
    name="query",
    method="POST",
    path="/v1/embeddings/query",
    payload={"tenant_id": "{tenant}", "vector": [0.11, 0.07, 0.94], "top_k": 3},
  ),
  EndpointCheck(
    service="search",
    name="hybrid",
    method="POST",
    path="/v1/search/hybrid",
    payload={
      "tenant_id": "{tenant}",
      "query": "Senior backend engineer",
      "filters": {"locations": ["Remote"]},
      "page_size": 5,
    },
  ),
  EndpointCheck(
    service="rerank",
    name="rerank",
    method="POST",
    path="/v1/search/rerank",
    payload={
      "tenant_id": "{tenant}",
      "query": "Staff machine learning engineer",
      "documents": [
        {"id": "cand-001", "text": "10 years ML ops experience."},
        {"id": "cand-002", "text": "7 years recommendation systems."},
      ],
      "top_n": 2,
    },
  ),
  EndpointCheck(
    service="evidence",
    name="candidate_evidence",
    method="GET",
    path="/v1/evidence/{candidate_id}",
    payload=None,
    expect_status=(200,),
    require_json=False,
  ),
  EndpointCheck(
    service="eco",
    name="occupations_search",
    method="GET",
    path="/v1/occupations/search?query=software",
    payload=None,
  ),
  EndpointCheck(
    service="eco",
    name="occupations_get",
    method="GET",
    path="/v1/occupations/{eco_id}",
    payload=None,
  ),
  EndpointCheck(
    service="enrichment",
    name="profile_enrich",
    method="POST",
    path="/v1/enrich/profile",
    payload={
      "tenant_id": "{tenant}",
      "profile_id": "profile-001",
      "attributes": {"skills": ["python", "orchestration"]},
    },
  ),
  EndpointCheck(
    service="enrichment",
    name="enrich_status",
    method="GET",
    path="/v1/enrich/status/{job_id}",
    payload=None,
    require_json=False,
  ),
  EndpointCheck(
    service="admin",
    name="health",
    method="GET",
    path="/v1/admin/health",
    payload=None,
    require_json=False,
  ),
  EndpointCheck(
    service="admin",
    name="snapshots",
    method="GET",
    path="/v1/admin/snapshots",
    payload=None,
  ),
  EndpointCheck(
    service="msgs",
    name="skills_expand",
    method="POST",
    path="/v1/skills/expand",
    payload={"tenant_id": "{tenant}", "skill": "python"},
  ),
  EndpointCheck(
    service="msgs",
    name="roles_template",
    method="POST",
    path="/v1/roles/template",
    payload={"tenant_id": "{tenant}", "role": "DevOps Engineer"},
  ),
  EndpointCheck(
    service="msgs",
    name="market_demand",
    method="GET",
    path="/v1/market/demand?role=backend",
    payload=None,
  ),
]


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
  result: Dict[str, str] = {}
  for item in raw:
    if "=" not in item:
      raise ValueError(f"Invalid service mapping '{item}', expected service=url")
    service, url = item.split("=", 1)
    result[service.strip()] = url.strip().rstrip("/")
  return result


class OAuthClient:
  def __init__(self, token_url: str, client_id: str, client_secret: str, audience: Optional[str] = None):
    self.token_url = token_url
    self.client_id = client_id
    self.client_secret = client_secret
    self.audience = audience
    self._cached_token: Optional[Tuple[str, float]] = None

  def get_token(self) -> str:
    now = time.time()
    if self._cached_token and self._cached_token[1] - now > 60:
      return self._cached_token[0]
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
    expires_in = data.get("expires_in", 3600)
    if not token:
      raise RuntimeError("Token endpoint did not return an access_token")
    self._cached_token = (token, now + expires_in)
    return token


class SmokeTestRunner:
  def __init__(
    self,
    config: Dict[str, Any],
    service_map: Dict[str, str],
    tenant_id: str,
    oauth_client: OAuthClient,
    candidate_id: str,
    eco_id: str,
    job_id: str,
    report_path: Optional[Path] = None,
  ) -> None:
    self.config = config
    self.service_map = service_map
    self.tenant_id = tenant_id
    self.oauth_client = oauth_client
    self.candidate_id = candidate_id
    self.eco_id = eco_id
    self.job_id = job_id
    self.report_path = report_path

  def run(self) -> Dict[str, Any]:
    summary: Dict[str, Any] = {"tests": []}
    for check in SMOKE_ENDPOINTS:
      base_url = self.service_map.get(check.service)
      if not base_url:
        summary["tests"].append(
          {
            "service": check.service,
            "name": check.name,
            "status": "skip",
            "reason": "service url missing",
          }
        )
        continue
      success, details = self._execute(base_url, check)
      summary["tests"].append(details)
      if not success:
        summary.setdefault("failures", 0)
        summary["failures"] += 1
    self._validate_header_enforcement(summary)
    self._persist(summary)
    return summary

  def _execute(self, base_url: str, check: EndpointCheck) -> Tuple[bool, Dict[str, Any]]:
    path = check.path.replace("{tenant}", self.tenant_id)
    path = path.replace("{candidate_id}", self.candidate_id)
    path = path.replace("{eco_id}", self.eco_id)
    path = path.replace("{job_id}", self.job_id)
    url = f"{base_url}{path}"
    payload = None
    headers = {
      "Authorization": f"Bearer {self.oauth_client.get_token()}",
      "X-Tenant-ID": self.tenant_id,
      "X-Request-ID": f"smoke-{int(time.time()*1000)}",
    }
    if check.payload is not None:
      payload = json.loads(json.dumps(check.payload).replace("{tenant}", self.tenant_id))
      headers["Content-Type"] = "application/json"
    if check.headers:
      headers.update(check.headers)
    start = time.perf_counter()
    response = requests.request(
      check.method,
      url,
      headers=headers,
      json=payload if headers.get("Content-Type") == "application/json" else None,
      params=None if payload is None or headers.get("Content-Type") == "application/json" else payload,
      timeout=DEFAULT_TIMEOUT,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    ok = response.status_code in check.expect_status
    result: Dict[str, Any] = {
      "service": check.service,
      "name": check.name,
      "url": url,
      "status_code": response.status_code,
      "latency_ms": round(elapsed_ms, 2),
      "status": "pass" if ok else "fail",
    }
    if ok and check.require_json:
      try:
        result["response_sample"] = response.json()
      except ValueError:
        result["status"] = "fail"
        result["status_code"] = response.status_code
        result["reason"] = "expected JSON response"
    elif not ok:
      result["reason"] = response.text[:500]
    return result["status"] == "pass", result

  def _validate_header_enforcement(self, summary: Dict[str, Any]) -> None:
    enforced = []
    for check in SMOKE_ENDPOINTS:
      base_url = self.service_map.get(check.service)
      if not base_url:
        continue
      url = f"{base_url}{check.path.replace('{candidate_id}', self.candidate_id).replace('{eco_id}', self.eco_id).replace('{job_id}', self.job_id)}"
      try:
        response = requests.request(
          check.method,
          url,
          timeout=DEFAULT_TIMEOUT,
        )
      except requests.RequestException as err:
        enforced.append({"service": check.service, "name": check.name, "status": "error", "reason": str(err)})
        continue
      if response.status_code >= 400:
        enforced.append({"service": check.service, "name": check.name, "status": "pass"})
      else:
        enforced.append({
          "service": check.service,
          "name": check.name,
          "status": "fail",
          "reason": f"Accepted request without tenant header (status {response.status_code})",
        })
    summary["tenant_header_validation"] = enforced

  def _persist(self, summary: Dict[str, Any]) -> None:
    if not self.report_path:
      return
    self.report_path.parent.mkdir(parents=True, exist_ok=True)
    with self.report_path.open("w", encoding="utf-8") as fh:
      json.dump(summary, fh, indent=2)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Production smoke tests")
  parser.add_argument("--config", default="config/testing/production-test-config.yaml", help="Config path")
  parser.add_argument("--environment", default="production", help="Environment key")
  parser.add_argument("--service", action="append", dest="services", help="Service mapping service=url", required=True)
  parser.add_argument("--tenant", default="tenant-alpha", help="Tenant ID for validation")
  parser.add_argument("--candidate-id", default="candidate-001", help="Candidate id for evidence checks")
  parser.add_argument("--eco-id", default="15-1132", help="ECO id for reference")
  parser.add_argument("--job-id", default="job-001", help="Enrichment job id for status check")
  parser.add_argument("--token-url", default="https://oauth2.googleapis.com/token", help="OAuth token URL")
  parser.add_argument("--client-id", required=True, help="OAuth client id")
  parser.add_argument("--client-secret", required=True, help="OAuth client secret")
  parser.add_argument("--audience", default=None, help="OAuth token audience")
  parser.add_argument("--report", default=None, help="Write JSON report to path")
  parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
  return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
  args = parse_args(argv)
  logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")
  config = load_config(Path(args.config), args.environment)
  service_map = resolve_service_map(args.services)
  oauth_client = OAuthClient(
    token_url=args.token_url,
    client_id=args.client_id,
    client_secret=args.client_secret,
    audience=args.audience or config.get("securityValidation", {}).get("oauth", {}).get("tokenAudience"),
  )
  runner = SmokeTestRunner(
    config=config,
    service_map=service_map,
    tenant_id=args.tenant,
    oauth_client=oauth_client,
    candidate_id=args.candidate_id,
    eco_id=args.eco_id,
    job_id=args.job_id,
    report_path=Path(args.report) if args.report else None,
  )
  summary = runner.run()
  failures = summary.get("failures", 0)
  if failures:
    LOGGER.error("Smoke tests detected %s failures", failures)
  print(json.dumps(summary, indent=2))
  return 1 if failures else 0


if __name__ == "__main__":
  sys.exit(main())
