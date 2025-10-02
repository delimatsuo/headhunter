#!/usr/bin/env python3
"""End-to-end pipeline validation for the Headhunter production stack."""
import argparse
import concurrent.futures
import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml

LOGGER = logging.getLogger("pipeline_validation")
DEFAULT_TIMEOUT = 20


@dataclass
class PipelineResult:
  enrich_ms: float
  embed_ms: float
  search_ms: float
  rerank_ms: float
  evidence_ms: float
  cache_hit: bool
  errors: List[str]


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
    self._cached: Optional[str] = None
    self._expires_at: Optional[float] = None

  def token(self) -> str:
    now = time.time()
    if self._cached and self._expires_at and self._expires_at - now > 60:
      return self._cached
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
      raise RuntimeError("Token endpoint missing access_token")
    self._cached = token
    self._expires_at = now + data.get("expires_in", 3600)
    return token


class PipelineValidator:
  def __init__(
    self,
    service_map: Dict[str, str],
    tenant_id: str,
    oauth: OAuthClient,
    sla: Dict[str, Any],
    report_path: Optional[Path] = None,
  ) -> None:
    self.service_map = service_map
    self.tenant_id = tenant_id
    self.oauth = oauth
    self.sla = sla
    self.report_path = report_path

  def run(self, iterations: int, concurrency: int) -> Dict[str, Any]:
    LOGGER.info("Executing %s pipeline iterations with concurrency %s", iterations, concurrency)
    results: List[PipelineResult] = []
    errors: List[str] = []

    def task(iteration: int) -> PipelineResult:
      return self._run_iteration(iteration)

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
      futures = [executor.submit(task, idx) for idx in range(iterations)]
      for future in concurrent.futures.as_completed(futures):
        try:
          results.append(future.result())
        except Exception as exc:  # pragma: no cover - capturing runtime failures
          LOGGER.exception("Iteration failed")
          errors.append(str(exc))

    summary = self._summarize(results, errors)
    self._persist(summary)
    return summary

  def _run_iteration(self, iteration: int) -> PipelineResult:
    token = self.oauth.token()
    headers = {
      "Authorization": f"Bearer {token}",
      "X-Tenant-ID": self.tenant_id,
      "X-Request-ID": f"pipeline-{iteration}-{int(time.time()*1000)}",
    }
    errors: List[str] = []

    enrich_start = time.perf_counter()
    enrich_resp = requests.post(
      f"{self.service_map['enrichment']}/v1/enrich/profile",
      json={
        "tenant_id": self.tenant_id,
        "profile_id": f"pipeline-profile-{iteration}",
        "attributes": {
          "skills": ["python", "asyncio"],
          "experience_years": 6,
        },
      },
      headers=headers,
      timeout=DEFAULT_TIMEOUT,
    )
    enrich_latency = (time.perf_counter() - enrich_start) * 1000
    if enrich_resp.status_code >= 400:
      errors.append(f"enrich failed: {enrich_resp.status_code} {enrich_resp.text[:200]}")
    job_id = enrich_resp.json().get("job_id") if enrich_resp.ok else None

    if job_id:
      status_latency = self._wait_for_enrichment_status(job_id, headers)
    else:
      status_latency = 0

    embed_start = time.perf_counter()
    embed_resp = requests.post(
      f"{self.service_map['embeddings']}/v1/embeddings/generate",
      json={
        "tenant_id": self.tenant_id,
        "text": "Senior data engineer specializing in batch and streaming pipelines.",
      },
      headers=headers,
      timeout=DEFAULT_TIMEOUT,
    )
    embed_latency = (time.perf_counter() - embed_start) * 1000
    if embed_resp.status_code >= 400:
      errors.append(f"embed failed: {embed_resp.status_code} {embed_resp.text[:200]}")

    search_start = time.perf_counter()
    search_resp = requests.post(
      f"{self.service_map['search']}/v1/search/hybrid",
      json={
        "tenant_id": self.tenant_id,
        "query": "Senior data engineer",
        "page_size": 10,
      },
      headers=headers,
      timeout=DEFAULT_TIMEOUT,
    )
    search_latency = (time.perf_counter() - search_start) * 1000
    if search_resp.status_code >= 400:
      errors.append(f"search failed: {search_resp.status_code} {search_resp.text[:200]}")
    documents = [
      {"id": item.get("id", f"cand-{idx}"), "text": item.get("snippet", "")}
      for idx, item in enumerate(search_resp.json().get("results", [])[:10])
    ] if search_resp.ok else []

    rerank_start = time.perf_counter()
    rerank_resp = requests.post(
      f"{self.service_map['rerank']}/v1/search/rerank",
      json={
        "tenant_id": self.tenant_id,
        "query": "Senior data engineer",
        "documents": documents or [
          {"id": "cand-001", "text": "Fallback candidate with analytics background."},
          {"id": "cand-002", "text": "Fallback candidate with ETL background."},
        ],
        "top_n": 5,
      },
      headers=headers,
      timeout=DEFAULT_TIMEOUT,
    )
    rerank_latency = (time.perf_counter() - rerank_start) * 1000
    if rerank_resp.status_code >= 400:
      errors.append(f"rerank failed: {rerank_resp.status_code} {rerank_resp.text[:200]}")

    evidence_start = time.perf_counter()
    candidate_id = documents[0]["id"] if documents else "cand-001"
    evidence_resp = requests.get(
      f"{self.service_map['evidence']}/v1/evidence/{candidate_id}",
      headers=headers,
      timeout=DEFAULT_TIMEOUT,
    )
    evidence_latency = (time.perf_counter() - evidence_start) * 1000
    if evidence_resp.status_code >= 400:
      errors.append(f"evidence failed: {evidence_resp.status_code} {evidence_resp.text[:200]}")

    cache_hit = evidence_resp.headers.get("X-Cache", "").lower() == "hit"

    return PipelineResult(
      enrich_ms=enrich_latency + status_latency,
      embed_ms=embed_latency,
      search_ms=search_latency,
      rerank_ms=rerank_latency,
      evidence_ms=evidence_latency,
      cache_hit=cache_hit,
      errors=errors,
    )

  def _wait_for_enrichment_status(self, job_id: str, headers: Dict[str, str]) -> float:
    status_url = f"{self.service_map['enrichment']}/v1/enrich/status/{job_id}"
    start = time.perf_counter()
    deadline = start + 120
    while time.perf_counter() < deadline:
      resp = requests.get(status_url, headers=headers, timeout=DEFAULT_TIMEOUT)
      if resp.status_code >= 400:
        return (time.perf_counter() - start) * 1000
      body = resp.json()
      if body.get("status") in {"succeeded", "failed"}:
        return (time.perf_counter() - start) * 1000
      time.sleep(2)
    return (time.perf_counter() - start) * 1000

  def _summarize(self, results: List[PipelineResult], errors: List[str]) -> Dict[str, Any]:
    if not results:
      return {"errors": errors or ["no results"]}
    enrich = [r.enrich_ms for r in results]
    embed = [r.embed_ms for r in results]
    search = [r.search_ms for r in results]
    rerank = [r.rerank_ms for r in results]
    evidence = [r.evidence_ms for r in results]
    total = [r.enrich_ms + r.embed_ms + r.search_ms + r.rerank_ms + r.evidence_ms for r in results]
    cache_hits = sum(1 for r in results if r.cache_hit)
    summary = {
      "iterations": len(results),
      "sla": self.sla,
      "latency_ms": {
        "enrich": {
          "avg": _avg(enrich),
          "p95": _percentile(enrich, 95),
        },
        "embed": {
          "avg": _avg(embed),
          "p95": _percentile(embed, 95),
        },
        "hybrid_search": {
          "avg": _avg(search),
          "p95": _percentile(search, 95),
        },
        "rerank": {
          "avg": _avg(rerank),
          "p95": _percentile(rerank, 95),
        },
        "evidence": {
          "avg": _avg(evidence),
          "p95": _percentile(evidence, 95),
        },
        "end_to_end": {
          "avg": _avg(total),
          "p95": _percentile(total, 95),
        },
      },
      "cache": {
        "hit_rate": cache_hits / len(results),
      },
      "errors": errors + [err for result in results for err in result.errors],
    }
    sla = self.sla
    summary["sla_pass"] = {
      "end_to_end": summary["latency_ms"]["end_to_end"]["p95"] <= sla.get("endToEndP95Ms", float("inf")),
      "rerank": summary["latency_ms"]["rerank"]["p95"] <= sla.get("rerankP95Ms", float("inf")),
      "cached_reads": summary["latency_ms"]["evidence"]["p95"] <= sla.get("cachedReadP95Ms", float("inf")),
      "cache_hit_rate": summary["cache"]["hit_rate"] >= sla.get("cacheHitRateTarget", 0),
    }
    return summary

  def _persist(self, summary: Dict[str, Any]) -> None:
    if not self.report_path:
      return
    self.report_path.parent.mkdir(parents=True, exist_ok=True)
    with self.report_path.open("w", encoding="utf-8") as fh:
      json.dump(summary, fh, indent=2)


def _avg(values: List[float]) -> float:
  return sum(values) / len(values) if values else 0.0


def _percentile(values: List[float], percentile: float) -> float:
  if not values:
    return 0.0
  ordered = sorted(values)
  k = (len(ordered) - 1) * (percentile / 100)
  f = int(k)
  c = min(f + 1, len(ordered) - 1)
  if f == c:
    return ordered[f]
  return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Validate the full search pipeline")
  parser.add_argument("--config", default="config/testing/production-test-config.yaml")
  parser.add_argument("--environment", default="production")
  parser.add_argument("--service", action="append", dest="services", required=True, help="service=url mapping")
  parser.add_argument("--tenant", required=True)
  parser.add_argument("--client-id", required=True)
  parser.add_argument("--client-secret", required=True)
  parser.add_argument("--token-url", default="https://oauth2.googleapis.com/token")
  parser.add_argument("--audience", default=None)
  parser.add_argument("--iterations", type=int, default=20)
  parser.add_argument("--concurrency", type=int, default=5)
  parser.add_argument("--report", default=None)
  parser.add_argument("--verbose", action="store_true")
  return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
  args = parse_args(argv)
  logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")
  config = load_config(Path(args.config), args.environment)
  service_map = resolve_service_map(args.services)
  oauth = OAuthClient(
    token_url=args.token_url,
    client_id=args.client_id,
    client_secret=args.client_secret,
    audience=args.audience or config.get("securityValidation", {}).get("oauth", {}).get("tokenAudience"),
  )
  validator = PipelineValidator(
    service_map=service_map,
    tenant_id=args.tenant,
    oauth=oauth,
    sla=config.get("slaTargets", {}),
    report_path=Path(args.report) if args.report else None,
  )
  summary = validator.run(iterations=args.iterations, concurrency=args.concurrency)
  print(json.dumps(summary, indent=2))
  failures = [key for key, passed in summary.get("sla_pass", {}).items() if not passed]
  return 1 if failures or summary.get("errors") else 0


if __name__ == "__main__":
  sys.exit(main())
