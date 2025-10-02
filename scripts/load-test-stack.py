#!/usr/bin/env python3
"""Concurrent load testing harness for the deployed gateway stack."""

from __future__ import annotations

import argparse
import json
import math
import threading
import time
import uuid
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence


DEFAULT_DURATION_SECONDS = 300
DEFAULT_CONCURRENCY = 4
DEFAULT_RAMP_UP_SECONDS = 30
DEFAULT_TIMEOUT_SECONDS = 20.0


@dataclass
class ScenarioConfig:
    method: str
    path: str
    payload_factory: Callable[[], Optional[Dict[str, Any]]] | None = None
    capture_cache_hit: bool = False


@dataclass
class OperationResult:
    latency_ms: float
    status_code: Optional[int]
    cache_hit: Optional[bool]
    error: Optional[str]
    body: Any


@dataclass
class RunOutcome:
    latencies: List[float]
    requests: int
    errors: int
    cache_hits: int
    cache_total: int
    status_counts: Counter
    notes: List[str]

    @classmethod
    def empty(cls) -> "RunOutcome":
        return cls(latencies=[], requests=0, errors=0, cache_hits=0, cache_total=0, status_counts=Counter(), notes=[])

    def record(self, result: OperationResult) -> None:
        if result.latency_ms >= 0:
            self.latencies.append(result.latency_ms)
        self.requests += 1
        if result.status_code is not None:
            self.status_counts[result.status_code] += 1
            if result.status_code >= 400:
                self.errors += 1
        elif result.error:
            self.errors += 1
        if result.cache_hit is not None:
            self.cache_total += 1
            if result.cache_hit:
                self.cache_hits += 1
        if result.error:
            self.notes.append(result.error)

    def merge(self, other: "RunOutcome") -> None:
        self.latencies.extend(other.latencies)
        self.requests += other.requests
        self.errors += other.errors
        self.cache_hits += other.cache_hits
        self.cache_total += other.cache_total
        self.status_counts.update(other.status_counts)
        if other.notes:
            self.notes.extend(other.notes)


class ScenarioRunner:
    def __init__(
        self,
        scenario: str,
        gateway_endpoint: str,
        tenant_id: str,
        auth_token: Optional[str],
        api_key: Optional[str],
        timeout: float,
    ) -> None:
        self.scenario = scenario
        self.gateway_endpoint = gateway_endpoint.rstrip("/")
        self.tenant_id = tenant_id
        self.auth_token = auth_token
        self.api_key = api_key
        self.timeout = timeout

        if scenario not in SCENARIO_CATALOG and scenario != "end-to-end":
            raise ValueError(f"Unknown scenario '{scenario}'")

    def run_iteration(self) -> RunOutcome:
        if self.scenario == "end-to-end":
            return self._run_end_to_end()
        return self._run_simple(SCENARIO_CATALOG[self.scenario])

    def _run_simple(self, config: ScenarioConfig) -> RunOutcome:
        payload = config.payload_factory() if config.payload_factory else None
        result = self._execute_operation(config.method, config.path, payload, config.capture_cache_hit)
        outcome = RunOutcome.empty()
        outcome.record(result)
        return outcome

    def _run_end_to_end(self) -> RunOutcome:
        outcome = RunOutcome.empty()

        # Step 1: embedding generation to warm embedding service
        embed_payload = sample_embedding_payload()
        embed_result = self._execute_operation("POST", "/v1/embeddings/generate", embed_payload, False)
        outcome.record(embed_result)

        # Step 2: hybrid search to fetch candidate list
        search_payload = sample_hybrid_search_payload()
        search_result = self._execute_operation("POST", "/v1/search/hybrid", search_payload, True)
        outcome.record(search_result)

        candidate_id = "test-candidate"
        rerank_candidates = sample_rerank_candidates()
        if isinstance(search_result.body, dict):
            results = search_result.body.get("results") or []
            if isinstance(results, list) and results:
                candidate_id = str(results[0].get("candidateId") or candidate_id)
                rerank_candidates = []
                for index, item in enumerate(results[:5]):
                    candidate = {
                        "candidateId": str(item.get("candidateId") or f"candidate-{index}"),
                        "summary": item.get("headline") or item.get("title") or "Load test candidate",
                        "initialScore": float(item.get("score", 0.5)),
                        "payload": item.get("metadata") or {},
                    }
                    rerank_candidates.append(candidate)
                if not rerank_candidates:
                    rerank_candidates = sample_rerank_candidates()

        rerank_payload = sample_rerank_payload(rerank_candidates)
        rerank_result = self._execute_operation("POST", "/v1/search/rerank", rerank_payload, True)
        outcome.record(rerank_result)

        if isinstance(rerank_result.body, dict):
            results = rerank_result.body.get("results") or []
            if isinstance(results, list) and results:
                candidate_id = str(results[0].get("candidateId") or candidate_id)

        evidence_path = f"/v1/evidence/{candidate_id}"
        evidence_result = self._execute_operation("GET", evidence_path, None, False)
        outcome.record(evidence_result)

        return outcome

    def _execute_operation(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]],
        capture_cache_hit: bool,
    ) -> OperationResult:
        url = build_url(self.gateway_endpoint, path)
        request_id = f"loadtest-{uuid.uuid4().hex}"
        headers = {
            "Accept": "application/json",
            "User-Agent": "load-test-stack/1.0",
            "X-Tenant-ID": self.tenant_id,
            "X-Request-ID": request_id,
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        data: Optional[bytes] = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())

        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                latency_ms = (time.perf_counter() - start) * 1000
                body_bytes = response.read()
                text = body_bytes.decode("utf-8") if body_bytes else ""
                parsed_body = parse_json(text)
                cache_hit = extract_cache_hit(parsed_body, response.headers) if capture_cache_hit else None
                return OperationResult(
                    latency_ms=latency_ms,
                    status_code=response.getcode(),
                    cache_hit=cache_hit,
                    error=None,
                    body=parsed_body,
                )
        except urllib.error.HTTPError as error:
            latency_ms = (time.perf_counter() - start) * 1000
            raw = error.read().decode("utf-8") if error.fp else ""
            parsed_body = parse_json(raw)
            cache_hit = extract_cache_hit(parsed_body, error.headers) if capture_cache_hit else None
            message = raw.strip() or error.reason
            return OperationResult(
                latency_ms=latency_ms,
                status_code=error.code,
                cache_hit=cache_hit,
                error=f"HTTP {error.code}: {message[:400]}",
                body=parsed_body or raw,
            )
        except urllib.error.URLError as error:
            latency_ms = (time.perf_counter() - start) * 1000
            return OperationResult(
                latency_ms=latency_ms,
                status_code=None,
                cache_hit=None,
                error=f"Network error: {error.reason}",
                body=None,
            )


def build_url(base: str, path: str) -> str:
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def parse_json(raw: str) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def extract_cache_hit(body: Any, headers: Any) -> Optional[bool]:
    if isinstance(body, dict):
        if "cacheHit" in body:
            return bool(body["cacheHit"])
        for key in ("metadata", "debug", "meta"):
            nested = body.get(key)
            if isinstance(nested, dict) and "cacheHit" in nested:
                return bool(nested["cacheHit"])
    if headers:
        header_value = headers.get("X-Cache-Hit") or headers.get("X-Cache-Status")
        if isinstance(header_value, str):
            lowered = header_value.lower()
            if lowered in {"hit", "true", "1", "yes"}:
                return True
            if lowered in {"miss", "false", "0", "no"}:
                return False
    return None


def percentile(values: Sequence[float], pct: float) -> Optional[float]:
    items = list(values)
    if not items:
        return None
    items.sort()
    rank = (pct / 100) * (len(items) - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return round(items[int(rank)], 2)
    lower_val = items[lower]
    upper_val = items[upper]
    interpolation = lower_val + (upper_val - lower_val) * (rank - lower)
    return round(interpolation, 2)


def average(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def run_load_test(
    runner: ScenarioRunner,
    concurrency: int,
    duration: int,
    ramp_up: int,
    max_iterations: Optional[int],
) -> tuple[RunOutcome, float]:
    deadline = None if duration <= 0 else time.perf_counter() + duration
    outcomes: List[RunOutcome] = []

    def worker(start_delay: float) -> None:
        if start_delay > 0:
            time.sleep(start_delay)
        outcome = RunOutcome.empty()
        if max_iterations is not None:
            for _ in range(max_iterations):
                if deadline is not None and time.perf_counter() >= deadline:
                    break
                outcome.merge(runner.run_iteration())
        else:
            while deadline is None or time.perf_counter() < deadline:
                outcome.merge(runner.run_iteration())
        outcomes.append(outcome)

    start_time = time.perf_counter()
    ramp_interval = ramp_up / concurrency if concurrency > 0 else 0
    threads: List[threading.Thread] = []
    for index in range(concurrency):
        delay = ramp_interval * index if ramp_up > 0 else 0
        thread = threading.Thread(target=worker, args=(delay,), daemon=True)
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()
    total_duration = time.perf_counter() - start_time

    aggregate = RunOutcome.empty()
    for outcome in outcomes:
        aggregate.merge(outcome)

    return aggregate, total_duration


def sample_embedding_payload() -> Dict[str, Any]:
    return {
        "text": "Post-deployment load test sample paragraph describing recruiting AI systems and reliability baselines.",
        "metadata": {
            "source": "load-test",
            "purpose": "post-deploy-validation",
        },
    }


def sample_hybrid_search_payload() -> Dict[str, Any]:
    return {
        "query": "software engineer machine learning",
        "limit": 5,
        "filters": {
            "skills": ["python", "ml"],
            "locations": ["remote", "austin"],
        },
        "includeDebug": True,
    }


def sample_rerank_candidates() -> List[Dict[str, Any]]:
    return [
        {
            "candidateId": "cand-001",
            "summary": "Senior ML engineer with production search experience.",
            "initialScore": 0.82,
            "features": {"vectorScore": 0.91, "textScore": 0.76},
            "payload": {"source": "loadtest"},
        },
        {
            "candidateId": "cand-002",
            "summary": "Backend engineer skilled in Go and distributed systems.",
            "initialScore": 0.78,
            "features": {"vectorScore": 0.88, "textScore": 0.71},
            "payload": {"source": "loadtest"},
        },
        {
            "candidateId": "cand-003",
            "summary": "Data scientist focusing on talent analytics dashboards.",
            "initialScore": 0.74,
            "features": {"vectorScore": 0.85, "textScore": 0.69},
            "payload": {"source": "loadtest"},
        },
    ]


def sample_rerank_payload(candidates: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    candidate_list = list(candidates) or sample_rerank_candidates()
    return {
        "jobDescription": "We are hiring senior engineers to build AI-driven recruiting experiences and production ML workflows.",
        "query": "senior software engineer",
        "candidates": candidate_list,
        "limit": min(5, len(candidate_list)) or 5,
        "includeReasons": True,
    }


def sample_enrichment_payload() -> Dict[str, Any]:
    return {
        "candidateId": "loadtest-candidate",
        "idempotencyKey": f"loadtest-{uuid.uuid4().hex[:12]}",
        "payload": {"source": "load-test"},
        "async": True,
    }


SCENARIO_CATALOG: Dict[str, ScenarioConfig] = {
    "embedding": ScenarioConfig(
        method="POST",
        path="/v1/embeddings/generate",
        payload_factory=sample_embedding_payload,
    ),
    "hybrid-search": ScenarioConfig(
        method="POST",
        path="/v1/search/hybrid",
        payload_factory=sample_hybrid_search_payload,
        capture_cache_hit=True,
    ),
    "rerank": ScenarioConfig(
        method="POST",
        path="/v1/search/rerank",
        payload_factory=lambda: sample_rerank_payload(sample_rerank_candidates()),
        capture_cache_hit=True,
    ),
    "evidence": ScenarioConfig(
        method="GET",
        path="/v1/evidence/test-candidate",
    ),
    "eco-search": ScenarioConfig(
        method="GET",
        path="/v1/occupations/search?title=software%20engineer&locale=en-US",
    ),
    "skill-expansion": ScenarioConfig(
        method="POST",
        path="/v1/skills/expand",
        payload_factory=lambda: {
            "skillId": "python",
            "topK": 5,
            "includeRelatedRoles": True,
        },
        capture_cache_hit=True,
    ),
    "admin-snapshots": ScenarioConfig(
        method="GET",
        path="/v1/admin/snapshots",
    ),
    "profile-enrichment": ScenarioConfig(
        method="POST",
        path="/v1/enrich/profile",
        payload_factory=sample_enrichment_payload,
    ),
}


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute a gateway load test scenario")
    parser.add_argument("--gateway-endpoint", required=True, help="Fully qualified HTTPS endpoint for the gateway")
    parser.add_argument("--tenant-id", default="tenant-alpha", help="Tenant identifier used for requests")
    parser.add_argument("--scenario", required=True, help="Scenario name to execute")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION_SECONDS, help="Duration in seconds to run the scenario")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY, help="Concurrent workers to execute")
    parser.add_argument("--ramp-up", type=int, default=DEFAULT_RAMP_UP_SECONDS, help="Ramp-up period before full load (seconds)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="Per-request timeout in seconds")
    parser.add_argument("--output", type=Path, help="Path to write JSON result")
    parser.add_argument("--auth-token", dest="auth_token", help="Bearer token for Authorization header")
    parser.add_argument("--api-key", dest="api_key", help="API key forwarded via X-API-Key header")

    # Compatibility with previous interface
    parser.add_argument("--users", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--iterations", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--report", type=Path, help=argparse.SUPPRESS)

    parsed = parser.parse_args(argv)

    if parsed.users and not parsed.concurrency:
        parsed.concurrency = parsed.users
    elif parsed.users:
        parsed.concurrency = parsed.users

    if parsed.report and not parsed.output:
        parsed.output = parsed.report

    if parsed.output is None:
        parsed.output = Path("load-test-result.json")

    if parsed.concurrency <= 0:
        parser.error("--concurrency must be greater than zero")
    if parsed.duration <= 0 and not parsed.iterations:
        parser.error("--duration must be greater than zero when --iterations is not set")

    return parsed


def build_result_payload(
    scenario: str,
    outcome: RunOutcome,
    duration_seconds: float,
    output_path: Path,
) -> Dict[str, Any]:
    p95 = percentile(outcome.latencies, 95)
    p99 = percentile(outcome.latencies, 99)
    average_latency = average(outcome.latencies)
    throughput_per_min = round((outcome.requests / duration_seconds) * 60, 2) if duration_seconds > 0 else None
    cache_hit_rate = None
    if outcome.cache_total > 0:
        cache_hit_rate = round(outcome.cache_hits / outcome.cache_total, 4)

    result = {
        "scenario": scenario,
        "status": "failed" if outcome.errors > 0 else "completed",
        "requests": outcome.requests,
        "errors": outcome.errors,
        "p95LatencyMs": p95,
        "p99LatencyMs": p99,
        "avgLatencyMs": average_latency,
        "throughputPerMin": throughput_per_min,
        "cacheHitRate": cache_hit_rate,
        "durationSeconds": round(duration_seconds, 2),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "statusCounts": {str(code): count for code, count in sorted(outcome.status_counts.items())},
        "samples": outcome.latencies[: min(len(outcome.latencies), 20)],
        "notes": outcome.notes[:5],
        "outputPath": str(output_path),
        "latency": {
            "p95": p95,
            "p99": p99,
            "avg": average_latency,
        },
    }

    return result


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)

    runner = ScenarioRunner(
        scenario=args.scenario,
        gateway_endpoint=args.gateway_endpoint,
        tenant_id=args.tenant_id,
        auth_token=args.auth_token,
        api_key=args.api_key,
        timeout=args.timeout,
    )

    outcome, elapsed = run_load_test(
        runner=runner,
        concurrency=args.concurrency,
        duration=max(args.duration, 0),
        ramp_up=max(args.ramp_up, 0),
        max_iterations=args.iterations,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    result_payload = build_result_payload(args.scenario, outcome, elapsed, args.output)
    args.output.write_text(json.dumps(result_payload, indent=2), encoding="utf-8")

    print(
        (
            f"[load-test-stack] {args.scenario}: requests={outcome.requests} errors={outcome.errors} "
            f"p95={result_payload['p95LatencyMs']}ms throughput/min={result_payload['throughputPerMin']}"
        )
    )
    print(f"[load-test-stack] Result written to {args.output}")

    return 0 if outcome.errors == 0 else 1


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
