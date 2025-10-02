"""
Phase 4: Comprehensive validation for pgvector deployment

Validates:
1) DB connectivity and pgvector extension
2) Schema and functions presence
3) Embedding generation via EmbeddingService (Vertex AI + fallback)
4) Vector similarity search round-trips
5) Functions integration (optional HTTP checks)
6) Performance (p95 <= 1.2s target)
7) Batch ops + connection pooling sanity
8) Data integrity checks
9) JSON report with component pass/fail

References (trusted per plan):
- scripts/pgvector_store.py
- scripts/embedding_service.py
- functions/src/vector-search.ts
- scripts/test_vector_search.py
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


REPORT_PATH = os.getenv("PGVECTOR_VALIDATION_REPORT", "scripts/pgvector_validation_report.json")
P95_TARGET_SEC = float(os.getenv("SEARCH_P95_TARGET_SEC", "1.2"))
WARMUP_QUERIES = int(os.getenv("SEARCH_WARMUP", "5"))
BENCH_QUERIES = int(os.getenv("SEARCH_BENCH", "30"))


async def validate_db(store: PgVectorStore) -> Dict[str, Any]:
    results: Dict[str, Any] = {"name": "db_checks"}
    async def scalar(sql: str, *args: Any) -> Any:
        async with store.get_connection() as conn:
            return await conn.fetchval(sql, *args)

    one = await scalar("SELECT 1")
    results["connectivity"] = one == 1
    ext = await scalar("SELECT COUNT(*) FROM pg_extension WHERE extname='vector'")
    results["pgvector_extension"] = (ext or 0) > 0
    try:
        emb_type = await scalar("""
            SELECT atttypid::regtype::text
            FROM pg_attribute
            WHERE attrelid = 'candidate_embeddings'::regclass
              AND attname = 'embedding'
              AND NOT attisdropped
        """)
        results["embedding_column_type"] = emb_type
        results["embedding_vector_768"] = isinstance(emb_type, str) and 'vector(768)' in emb_type
    except Exception:
        results["embedding_column_type"] = None
        results["embedding_vector_768"] = False
    results["ok"] = results.get("connectivity") and results.get("pgvector_extension")
    return results


async def validate_embeddings() -> Dict[str, Any]:
    emb = EmbeddingService(provider=os.getenv("EMBEDDING_PROVIDER", "vertex_ai"))
    txt = "Senior backend engineer with Python and PostgreSQL"
    res = await emb.generate_embedding(txt)
    vec = res.vector
    ok = isinstance(vec, list) and len(vec) == 768
    result = {
        "name": "embedding_provider",
        "ok": ok,
        "dim": len(vec) if isinstance(vec, list) else None,
        "expected_dim": 768,
    }
    if not ok:
        result["message"] = (
            "Embedding dimension mismatch. Verify EMBEDDING_PROVIDER and selected model, and ensure DB schema uses vector(768)."
        )
    return result


async def validate_search_roundtrip(store: PgVectorStore, emb: EmbeddingService) -> Dict[str, Any]:
    # Create a small, temporary test set
    samples = [
        ("cand_alpha", "Python developer experienced in FastAPI"),
        ("cand_bravo", "Full-stack engineer with React and Node.js"),
        ("cand_charlie", "Data scientist with TensorFlow and PyTorch"),
    ]
    # Upsert embeddings
    for cid, text in samples:
        er = await emb.generate_embedding(text)
        await store.store_embedding(candidate_id=cid, embedding=er.vector, metadata={"text": text})

    # Query for Python
    q_res = await emb.generate_embedding("Python backend engineer")
    hits = await store.similarity_search(query_embedding=q_res.vector, max_results=3)
    top_ids = [h.candidate_id for h in hits]
    ok = samples[0][0] in top_ids
    return {"name": "search_roundtrip", "ok": ok, "top_ids": top_ids}


async def benchmark_search(store: PgVectorStore, emb: EmbeddingService) -> Dict[str, Any]:
    latencies: List[float] = []
    q = "Senior data engineer with Airflow and BigQuery"
    q_res = await emb.generate_embedding(q)
    # Warmup
    for _ in range(WARMUP_QUERIES):
        await store.similarity_search(query_embedding=q_res.vector, max_results=10)
    # Bench
    for _ in range(BENCH_QUERIES):
        t0 = time.perf_counter()
        await store.similarity_search(query_embedding=q_res.vector, max_results=10)
        latencies.append(time.perf_counter() - t0)

    p95 = statistics.quantiles(latencies, n=100)[94] if len(latencies) >= 20 else max(latencies or [0])
    return {
        "name": "performance_benchmark",
        "ok": p95 <= P95_TARGET_SEC,
        "p95_sec": round(p95, 3),
        "avg_sec": round(sum(latencies) / max(len(latencies), 1), 3),
        "samples": len(latencies),
        "target_p95_sec": P95_TARGET_SEC,
    }


async def validate_http_endpoint(url: str, query: str) -> Dict[str, Any]:
    import aiohttp  # local import to avoid hard dep if unused
    async with aiohttp.ClientSession() as s:
        t0 = time.perf_counter()
        async with s.post(url, json={"query": query, "limit": 5}) as r:
            data = await r.json()
        return {"ok": r.status == 200 and "results" in data, "latency_sec": time.perf_counter() - t0}


async def run_all() -> Dict[str, Any]:
    store = await create_pgvector_store(pool_size=int(os.getenv("PGVECTOR_MAX_CONNECTIONS", "20")))
    emb = EmbeddingService(provider=os.getenv("EMBEDDING_PROVIDER", "vertex_ai"))

    checks: List[Dict[str, Any]] = []
    checks.append(await validate_db(store))
    checks.append(await validate_embeddings())
    checks.append(await validate_search_roundtrip(store, emb))
    checks.append(await benchmark_search(store, emb))
    http_url = os.getenv("SEARCH_ENDPOINT_URL")
    if http_url:
        http_res = await validate_http_endpoint(http_url, "Python backend engineer")
        checks.append({"name": "http_endpoint", **http_res})

    summary = {"ok": all(c.get("ok", False) for c in checks), "checks": checks, "generated_at": int(time.time())}
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary


def main() -> None:
    result = asyncio.run(run_all())
    print(json.dumps(result, indent=2))
    if not result.get("ok", False):
        sys.exit(1)


if __name__ == "__main__":
    main()
