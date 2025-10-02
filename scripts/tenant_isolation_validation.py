#!/usr/bin/env python3
"""Tenant isolation and security controls validation for Headhunter services."""
import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml

LOGGER = logging.getLogger("tenant_isolation_validation")
DEFAULT_TIMEOUT = 15


@dataclass
class TenantCredentials:
  tenant_id: str
  client_id: str
  client_secret: str


@dataclass
class TenantContext:
  credentials: TenantCredentials
  token: str


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


def parse_tenants(raw: List[str]) -> List[TenantCredentials]:
  tenants: List[TenantCredentials] = []
  for entry in raw:
    parts = entry.split(",")
    if len(parts) != 3:
      raise ValueError("Tenant entry must be tenant_id,client_id,client_secret")
    tenant_id, client_id, client_secret = [part.strip() for part in parts]
    tenants.append(TenantCredentials(tenant_id, client_id, client_secret))
  return tenants


class OAuthClient:
  def __init__(self, token_url: str, audience: Optional[str]) -> None:
    self.token_url = token_url
    self.audience = audience

  def get_token(self, client_id: str, client_secret: str) -> str:
    payload = {
      "grant_type": "client_credentials",
      "client_id": client_id,
      "client_secret": client_secret,
    }
    if self.audience:
      payload["audience"] = self.audience
    resp = requests.post(self.token_url, data=payload, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
      raise RuntimeError("OAuth response missing access_token")
    return token


class TenantIsolationValidator:
  def __init__(
    self,
    config: Dict[str, Any],
    service_map: Dict[str, str],
    tenants: List[TenantCredentials],
    oauth: OAuthClient,
    report_path: Optional[Path] = None,
  ) -> None:
    self.config = config
    self.service_map = service_map
    self.tenants = tenants
    self.oauth = oauth
    self.report_path = report_path
    self.contexts: Dict[str, TenantContext] = {}

  def run(self) -> Dict[str, Any]:
    results = {
      "auth": [],
      "cross_tenant_checks": [],
      "cache_isolation": [],
      "malicious_input": [],
    }
    self._authenticate_all()
    for tenant, context in self.contexts.items():
      results["auth"].append(self._validate_positive_access(context))
      results["auth"].append(self._validate_missing_header(context))
      results["auth"].append(self._validate_expired_token(context))
    results["cross_tenant_checks"].extend(self._validate_cross_tenant_access())
    results["cache_isolation"].extend(self._validate_cache_isolation())
    results["malicious_input"].extend(self._validate_malicious_inputs())
    self._persist(results)
    return results

  def _authenticate_all(self) -> None:
    for creds in self.tenants:
      token = self.oauth.get_token(creds.client_id, creds.client_secret)
      self.contexts[creds.tenant_id] = TenantContext(credentials=creds, token=token)

  def _request(self, method: str, base: str, path: str, tenant_id: str, token: str, body: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> requests.Response:
    url = f"{base}{path}"
    req_headers = {
      "Authorization": f"Bearer {token}",
      "X-Tenant-ID": tenant_id,
      "X-Request-ID": f"tenantisolation-{int(time.time()*1000)}",
    }
    if headers:
      req_headers.update(headers)
    return requests.request(method, url, json=body, headers=req_headers, timeout=DEFAULT_TIMEOUT)

  def _validate_positive_access(self, context: TenantContext) -> Dict[str, Any]:
    base = self.service_map["search"]
    body = {
      "tenant_id": context.credentials.tenant_id,
      "query": "DevOps engineer",
      "page_size": 2,
    }
    resp = self._request("POST", base, "/v1/search/hybrid", context.credentials.tenant_id, context.token, body)
    ok = resp.status_code < 400
    return {
      "tenant": context.credentials.tenant_id,
      "test": "valid_access",
      "status": "pass" if ok else "fail",
      "status_code": resp.status_code,
      "reason": None if ok else resp.text[:200],
    }

  def _validate_missing_header(self, context: TenantContext) -> Dict[str, Any]:
    base = self.service_map["search"]
    body = {
      "tenant_id": context.credentials.tenant_id,
      "query": "DevOps engineer",
    }
    url = f"{base}/v1/search/hybrid"
    resp = requests.post(
      url,
      json=body,
      headers={"Authorization": f"Bearer {context.token}"},
      timeout=DEFAULT_TIMEOUT,
    )
    ok = resp.status_code >= 400
    return {
      "tenant": context.credentials.tenant_id,
      "test": "missing_header",
      "status": "pass" if ok else "fail",
      "status_code": resp.status_code,
      "reason": None if ok else "Request succeeded without tenant header",
    }

  def _validate_expired_token(self, context: TenantContext) -> Dict[str, Any]:
    base = self.service_map["search"]
    headers = {
      "Authorization": "Bearer invalid-token",
      "X-Tenant-ID": context.credentials.tenant_id,
    }
    resp = requests.post(f"{base}/v1/search/hybrid", json={"query": "test"}, headers=headers, timeout=DEFAULT_TIMEOUT)
    ok = resp.status_code in (401, 403)
    return {
      "tenant": context.credentials.tenant_id,
      "test": "expired_token",
      "status": "pass" if ok else "fail",
      "status_code": resp.status_code,
      "reason": None if ok else "Service accepted invalid token",
    }

  def _validate_cross_tenant_access(self) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    tenant_ids = list(self.contexts.keys())
    if len(tenant_ids) < 2:
      return checks
    first = self.contexts[tenant_ids[0]]
    second = self.contexts[tenant_ids[1]]
    base = self.service_map["evidence"]
    path = f"/v1/evidence/{second.credentials.tenant_id}-candidate"
    resp = self._request("GET", base, path, first.credentials.tenant_id, first.token)
    ok = resp.status_code in (401, 403, 404)
    checks.append(
      {
        "test": "cross_tenant_evidence",
        "requesting_tenant": first.credentials.tenant_id,
        "target_tenant": second.credentials.tenant_id,
        "status": "pass" if ok else "fail",
        "status_code": resp.status_code,
        "reason": None if ok else "Cross-tenant evidence fetch succeeded",
      }
    )
    base_search = self.service_map["search"]
    body = {
      "tenant_id": second.credentials.tenant_id,
      "query": "Site Reliability Engineer",
    }
    resp = self._request("POST", base_search, "/v1/search/hybrid", first.credentials.tenant_id, first.token, body)
    ok = resp.status_code in (401, 403)
    checks.append(
      {
        "test": "cross_tenant_search",
        "requesting_tenant": first.credentials.tenant_id,
        "target_tenant": second.credentials.tenant_id,
        "status": "pass" if ok else "fail",
        "status_code": resp.status_code,
        "reason": None if ok else "Allowed cross-tenant search",
      }
    )
    return checks

  def _validate_cache_isolation(self) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    if len(self.contexts) < 2:
      return results
    tenants = list(self.contexts.values())
    primary = tenants[0]
    secondary = tenants[1]
    base = self.service_map["evidence"]
    path = "/v1/evidence/demo-candidate"
    resp1 = self._request("GET", base, path, primary.credentials.tenant_id, primary.token)
    cache_after_primary = resp1.headers.get("X-Cache")
    resp2 = self._request("GET", base, path, secondary.credentials.tenant_id, secondary.token)
    cache_after_secondary = resp2.headers.get("X-Cache")
    isolated = cache_after_primary and cache_after_primary.lower() == "hit" and cache_after_secondary and cache_after_secondary.lower() in {"miss", "bypass"}
    results.append(
      {
        "test": "cache_namespace_isolation",
        "status": "pass" if isolated else "fail",
        "primary_cache": cache_after_primary,
        "secondary_cache": cache_after_secondary,
        "reason": None if isolated else "Secondary tenant observed cached copy",
      }
    )
    return results

  def _validate_malicious_inputs(self) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    malicious_inputs = self.config.get("tenantIsolation", {}).get("maliciousInputs", [])
    if not malicious_inputs:
      return checks
    base = self.service_map["search"]
    for tenant_id, context in self.contexts.items():
      for payload in malicious_inputs:
        resp = self._request(
          "POST",
          base,
          "/v1/search/hybrid",
          tenant_id,
          context.token,
          {"tenant_id": tenant_id, "query": payload},
        )
        ok = resp.status_code >= 400
        checks.append(
          {
            "tenant": tenant_id,
            "payload": payload,
            "status": "pass" if ok else "fail",
            "status_code": resp.status_code,
            "reason": None if ok else "Malicious input accepted",
          }
        )
    return checks

  def _persist(self, results: Dict[str, Any]) -> None:
    if not self.report_path:
      return
    self.report_path.parent.mkdir(parents=True, exist_ok=True)
    with self.report_path.open("w", encoding="utf-8") as fh:
      json.dump(results, fh, indent=2)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Validate tenant isolation controls")
  parser.add_argument("--config", default="config/testing/production-test-config.yaml")
  parser.add_argument("--environment", default="production")
  parser.add_argument("--service", action="append", dest="services", required=True, help="service=url mapping")
  parser.add_argument("--tenant", action="append", dest="tenants", required=True, help="tenant_id,client_id,client_secret")
  parser.add_argument("--token-url", default="https://oauth2.googleapis.com/token")
  parser.add_argument("--audience", default=None)
  parser.add_argument("--report", default=None)
  parser.add_argument("--verbose", action="store_true")
  return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
  args = parse_args(argv)
  logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")
  config = load_config(Path(args.config), args.environment)
  service_map = resolve_service_map(args.services)
  tenants = parse_tenants(args.tenants)
  audience = args.audience or config.get("securityValidation", {}).get("oauth", {}).get("tokenAudience")
  oauth = OAuthClient(args.token_url, audience)
  validator = TenantIsolationValidator(
    config=config,
    service_map=service_map,
    tenants=tenants,
    oauth=oauth,
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
