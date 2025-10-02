#!/usr/bin/env python3
"""Chaos engineering validation for Headhunter production deployment."""
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

LOGGER = logging.getLogger("production_chaos_testing")
DEFAULT_TIMEOUT = 10


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


@dataclass
class ChaosScenario:
  name: str
  description: str
  max_recovery_seconds: int
  resilience_target: str


class ChaosTester:
  def __init__(
    self,
    service_map: Dict[str, str],
    tenant_id: str,
    token: str,
    scenarios: List[ChaosScenario],
    chaos_endpoint: Optional[str],
    report_path: Optional[Path],
  ) -> None:
    self.service_map = service_map
    self.tenant_id = tenant_id
    self.token = token
    self.scenarios = scenarios
    self.chaos_endpoint = chaos_endpoint or f"{service_map.get('admin', '')}/v1/admin/chaos"
    self.report_path = report_path
    self._unauthorized = False
    self._unauthorized_reason: Optional[str] = None

  def run(self) -> Dict[str, Any]:
    results: Dict[str, Any] = {"scenarios": []}
    for scenario in self.scenarios:
      if self._unauthorized:
        results["scenarios"].append({
          "name": scenario.name,
          "description": scenario.description,
          "resilience_target": scenario.resilience_target,
          "status": "skip",
          "reason": self._unauthorized_reason or "chaos token lacks permissions",
        })
        continue
      LOGGER.info("Running chaos scenario %s", scenario.name)
      outcome = self._execute_scenario(scenario)
      results["scenarios"].append(outcome)
    if self._unauthorized:
      results["status"] = "skip"
      if self._unauthorized_reason:
        results["reason"] = self._unauthorized_reason
    self._persist(results)
    return results

  def _execute_scenario(self, scenario: ChaosScenario) -> Dict[str, Any]:
    baseline = self._probe_services()
    injection_status = self._inject(scenario)
    if self._unauthorized:
      return {
        "name": scenario.name,
        "description": scenario.description,
        "resilience_target": scenario.resilience_target,
        "status": "skip",
        "reason": self._unauthorized_reason,
        "baseline": baseline,
        "injection": injection_status,
      }
    during = self._probe_services()
    recovered = self._await_recovery(scenario)
    final_probe = self._probe_services()
    status = "pass" if recovered and final_probe.get("unhealthy") == [] else "fail"
    return {
      "name": scenario.name,
      "description": scenario.description,
      "resilience_target": scenario.resilience_target,
      "status": status,
      "baseline": baseline,
      "during": during,
      "recovered": recovered,
      "final_probe": final_probe,
    }

  def _headers(self) -> Dict[str, str]:
    return {
      "Authorization": f"Bearer {self.token}",
      "X-Tenant-ID": self.tenant_id,
    }

  def _inject(self, scenario: ChaosScenario) -> Dict[str, Any]:
    try:
      resp = requests.post(
        self.chaos_endpoint,
        json={"scenario": scenario.name},
        headers=self._headers(),
        timeout=DEFAULT_TIMEOUT,
      )
      if resp.status_code in (401, 403):
        self._unauthorized = True
        self._unauthorized_reason = f"chaos injection unauthorized (status {resp.status_code})"
      return {"status_code": resp.status_code, "body": resp.text[:200]}
    except requests.RequestException as exc:
      return {"error": str(exc)}

  def _await_recovery(self, scenario: ChaosScenario) -> bool:
    deadline = time.time() + scenario.max_recovery_seconds
    while time.time() < deadline:
      probe = self._probe_services()
      if not probe.get("unhealthy"):
        return True
      time.sleep(5)
    return False

  def _probe_services(self) -> Dict[str, Any]:
    services = {
      "search": ("POST", "/v1/search/hybrid", {"query": "Chaos validation", "tenant_id": self.tenant_id}),
      "rerank": ("POST", "/v1/search/rerank", {
        "tenant_id": self.tenant_id,
        "query": "Chaos validation",
        "documents": [{"id": "cand-1", "text": "Experience with chaos"}],
        "top_n": 1,
      }),
      "evidence": ("GET", f"/v1/evidence/{self.tenant_id}-chaos", None),
    }
    unhealthy: List[str] = []
    details: Dict[str, Any] = {}
    for service, (method, path, payload) in services.items():
      base = self.service_map.get(service)
      if not base:
        continue
      try:
        resp = requests.request(
          method,
          f"{base}{path}",
          json=payload if method != "GET" else None,
          headers=self._headers(),
          timeout=DEFAULT_TIMEOUT,
        )
      except requests.RequestException as exc:
        unhealthy.append(service)
        details[service] = {"error": str(exc)}
        continue
      if resp.status_code >= 500:
        unhealthy.append(service)
      details[service] = {"status_code": resp.status_code, "body": resp.text[:200]}
    return {"unhealthy": unhealthy, "details": details}

  def _persist(self, results: Dict[str, Any]) -> None:
    if not self.report_path:
      return
    self.report_path.parent.mkdir(parents=True, exist_ok=True)
    with self.report_path.open("w", encoding="utf-8") as fh:
      json.dump(results, fh, indent=2)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Chaos testing orchestration")
  parser.add_argument("--config", default="config/testing/production-test-config.yaml")
  parser.add_argument("--environment", default="production")
  parser.add_argument("--service", action="append", dest="services", required=True, help="service=url mapping")
  parser.add_argument("--tenant", required=True)
  parser.add_argument("--token", required=True, help="Pre-issued bearer token with admin rights")
  parser.add_argument("--chaos-endpoint", default=None)
  parser.add_argument("--report", default=None)
  parser.add_argument("--verbose", action="store_true")
  return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
  args = parse_args(argv)
  logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")
  config = load_config(Path(args.config), args.environment)
  service_map = resolve_service_map(args.services)
  scenario_configs = config.get("chaosTesting", {}).get("failureScenarios", [])
  scenarios = [
    ChaosScenario(
      name=item.get("name"),
      description=item.get("description", ""),
      max_recovery_seconds=int(item.get("maxRecoverySeconds", 120)),
      resilience_target=item.get("resilienceTarget", ""),
    )
    for item in scenario_configs
  ]
  tester = ChaosTester(
    service_map=service_map,
    tenant_id=args.tenant,
    token=args.token,
    scenarios=scenarios,
    chaos_endpoint=args.chaos_endpoint,
    report_path=Path(args.report) if args.report else None,
  )
  report = tester.run()
  print(json.dumps(report, indent=2))
  failures = [scenario for scenario in report.get("scenarios", []) if scenario.get("status") == "fail"]
  return 1 if failures else 0


if __name__ == "__main__":
  sys.exit(main())
