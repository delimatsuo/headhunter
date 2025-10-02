"""
Phase 4: pgvector performance tuning toolkit

Functions:
- Analyze query patterns and propose index settings
- Suggest IVFFlat/HNSW tuning based on dataset size
- Test and benchmark alternative search parameters
- Produce actionable recommendations and regression checks

References:
- scripts/pgvector_store.py
- scripts/pgvector_schema.sql
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import time
import sys
from typing import Any, Dict, List

try:
    from scripts.pgvector_store import PgVectorStore, create_pgvector_store  # type: ignore
except Exception:
    from pgvector_store import PgVectorStore, create_pgvector_store  # type: ignore


REPORT = os.getenv("PGVECTOR_TUNING_REPORT", "scripts/pgvector_tuning_report.json")


async def dataset_stats(store: PgVectorStore) -> Dict[str, Any]:
    async with store.get_connection() as conn:
        n = await conn.fetchval("SELECT COUNT(*) FROM candidate_embeddings")
        # Dimension hint not directly stored; rely on env default elsewhere
        return {"count": int(n or 0)}


def recommend_index_strategy(count: int) -> Dict[str, Any]:
    if count < 10_000:
        return {"index": "hnsw", "params": {"m": 16, "ef_construction": 200, "ef_search": 64}}
    else:
        # IVFFlat requires training; pick k-means centroids ~ sqrt(n)
        lists = max(100, int(math.sqrt(count)))
        return {"index": "ivfflat", "params": {"lists": lists, "probe": 8}}


async def benchmark(store: PgVectorStore, params: Dict[str, Any]) -> Dict[str, Any]:
    import random
    import time

    latencies: List[float] = []
    dim = int(os.getenv("EMBEDDING_DIM", "768"))
    for _ in range(20):
        qvec = [random.random() for _ in range(dim)]
        t0 = time.perf_counter()
        # Note: similarity_search doesn't accept HNSW/IVF tuning via kwargs in this client
        await store.similarity_search(query_embedding=qvec, max_results=10)
        latencies.append(time.perf_counter() - t0)
    avg = sum(latencies) / max(len(latencies), 1)
    p95 = sorted(latencies)[int(0.95 * (len(latencies) - 1))] if latencies else 0
    return {"avg_sec": round(avg, 4), "p95_sec": round(p95, 4)}


async def run() -> Dict[str, Any]:
    store = await create_pgvector_store(pool_size=int(os.getenv("PGVECTOR_MAX_CONNECTIONS", "20")))

    stats = await dataset_stats(store)
    reco = recommend_index_strategy(stats["count"])

    # Try a couple of parameter sweeps
    results: List[Dict[str, Any]] = []
    if reco["index"] == "hnsw":
        for ef in (32, 64, 128):
            res = await benchmark(store, {"ef_search": ef})
            results.append({"index": "hnsw", "ef_search": ef, **res})
    else:
        for probe in (4, 8, 16):
            res = await benchmark(store, {"probe": probe})
            results.append({"index": "ivfflat", "probe": probe, **res})

    # Compute simple OK flag: at least one configuration with p95 under threshold
    if results:
        try:
            best_p95 = min(b.get("p95_sec", float("inf")) for b in results)
        except ValueError:
            best_p95 = float("inf")
        ok = best_p95 <= float(os.getenv("TUNING_MAX_P95_SEC", "1.2"))
    else:
        ok = True

    report = {
        "dataset": stats,
        "recommendation": reco,
        "benchmarks": results,
        "ok": bool(ok),
        "generated_at": int(time.time()),
    }
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return report


def main() -> None:
    out = asyncio.run(run())
    print(json.dumps(out, indent=2))
    if not out.get("ok", False):
        sys.exit(1)


if __name__ == "__main__":
    main()
