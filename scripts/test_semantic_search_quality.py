"""
Phase 4: Semantic search quality validation

Goals:
- Use existing test profiles and generate additional variants
- Evaluate relevance for job-description queries
- Exercise skill synonyms, partial matches, experience variance
- Measure precision/recall and latency
- A/B test different embedding models/providers

References:
- scripts/test_vector_search.py
- functions/src/vector-search.ts
- scripts/embedding_service.py
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import statistics
import time
import sys
from typing import Any, Dict, List, Tuple

try:
    from scripts.pgvector_store import PgVectorStore, create_pgvector_store  # type: ignore
except Exception:
    from pgvector_store import PgVectorStore, create_pgvector_store  # type: ignore

try:
    from scripts.embedding_service import EmbeddingService  # type: ignore
except Exception:
    from embedding_service import EmbeddingService  # type: ignore


REPORT = os.getenv("SEMANTIC_QUALITY_REPORT", "scripts/semantic_quality_report.json")
TARGET_P95 = float(os.getenv("SEARCH_P95_TARGET_SEC", "1.2"))


def _ground_truth() -> Dict[str, List[str]]:
    # Mapping of query -> relevant candidate ids (trusted test ids)
    return {
        "Senior Python backend engineer": ["cand_python_senior", "cand_alpha"],
        "React Node full-stack developer": ["cand_fullstack_react", "cand_bravo"],
        "Data scientist deep learning": ["cand_ml_dl", "cand_charlie"],
    }


async def _prepare_index(store: PgVectorStore, emb: EmbeddingService) -> None:
    samples = [
        ("cand_python_senior", "Senior Python engineer, FastAPI, PostgreSQL, Kubernetes"),
        ("cand_fullstack_react", "Full-stack developer, React, Node.js, Express, TypeScript"),
        ("cand_ml_dl", "Data scientist, deep learning with PyTorch and TensorFlow"),
    ]
    for cid, text in samples:
        er = await emb.generate_embedding(text)
        await store.store_embedding(candidate_id=cid, embedding=er.vector, metadata={"text": text})


def _precision_recall(expected: List[str], actual: List[str], k: int = 5) -> Tuple[float, float]:
    s_expected = set(expected)
    s_actual = set(actual[:k])
    tp = len(s_expected & s_actual)
    precision = tp / max(len(s_actual), 1)
    recall = tp / max(len(s_expected), 1)
    return precision, recall


async def _evaluate_query(store: PgVectorStore, emb: EmbeddingService, q: str, expected: List[str]) -> Dict[str, Any]:
    q_res = await emb.generate_embedding(q)
    t0 = time.perf_counter()
    hits = await store.similarity_search(query_embedding=q_res.vector, max_results=10)
    latency = time.perf_counter() - t0
    ids = [h.candidate_id for h in hits]
    p, r = _precision_recall(expected, ids, k=5)
    return {"query": q, "expected": expected, "actual": ids, "precision": p, "recall": r, "latency_sec": latency}


async def run_suite() -> Dict[str, Any]:
    provider = os.getenv("EMBEDDING_PROVIDER", "vertex_ai")
    emb = EmbeddingService(provider=provider)
    store = await create_pgvector_store(pool_size=int(os.getenv("PGVECTOR_MAX_CONNECTIONS", "20")))

    await _prepare_index(store, emb)

    gt = _ground_truth()
    results: List[Dict[str, Any]] = []
    latencies: List[float] = []
    for q, expected in gt.items():
        res = await _evaluate_query(store, emb, q, expected)
        latencies.append(res["latency_sec"]) 
        results.append(res)

    p95 = statistics.quantiles(latencies, n=100)[94] if len(latencies) >= 20 else max(latencies or [0])
    # Capture model info from embedding provider
    try:
        model_name = emb.provider.model  # type: ignore[attr-defined]
    except Exception:
        model_name = "unknown"

    avg_precision = round(sum(r["precision"] for r in results) / max(len(results), 1), 3)
    avg_recall = round(sum(r["recall"] for r in results) / max(len(results), 1), 3)

    summary: Dict[str, Any] = {
        "provider": provider,
        "model": model_name,
        "p95_sec": round(p95, 3),
        "target_p95_sec": TARGET_P95,
        "ok_latency": p95 <= TARGET_P95,
        "cases": results,
        "avg_precision": avg_precision,
        "avg_recall": avg_recall,
        "generated_at": int(time.time()),
    }

    # Add overall ok based on latency and precision threshold (configurable)
    ok = (p95 <= TARGET_P95) and (
        summary["avg_precision"] >= float(os.getenv("QUALITY_MIN_PRECISION", "0.3"))
    )
    summary["ok"] = bool(ok)

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary


def main() -> None:
    out = asyncio.run(run_suite())
    print(json.dumps(out, indent=2))
    if not out.get("ok", False):
        sys.exit(1)


if __name__ == "__main__":
    main()
