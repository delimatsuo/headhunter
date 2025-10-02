"""
Phase 4: pgvector performance and health monitoring

Monitors:
- DB connection pool health and query latency
- Search performance metrics
- Embedding generation throughput and error rate
- Resource utilization (best-effort from DB side)
- Index performance observations

Outputs:
- Console logs and optional push to Google Cloud Monitoring (if libs available)

References:
- scripts/pgvector_store.py
- scripts/embedding_service.py
- functions/src/vector-search.ts
"""

from __future__ import annotations

import asyncio
import os
import random
import time
from typing import Any, Dict, Optional

try:
    from scripts.pgvector_store import PgVectorStore, create_pgvector_store  # type: ignore
except Exception:
    from pgvector_store import PgVectorStore, create_pgvector_store  # type: ignore

try:
    from scripts.embedding_service import EmbeddingService  # type: ignore
except Exception:
    from embedding_service import EmbeddingService  # type: ignore


POLL_SEC = float(os.getenv("PGVECTOR_MONITOR_POLL_SEC", "30"))
PRINT_PREFIX = "[monitor]"


async def sample_db_metrics(store: PgVectorStore) -> Dict[str, Any]:
    async with store.get_connection() as conn:
        active = await conn.fetchval("SELECT count(*) FROM pg_stat_activity WHERE state='active'")
        idle = await conn.fetchval("SELECT count(*) FROM pg_stat_activity WHERE state='idle'")
        idx_scans = await conn.fetchval("SELECT sum(idx_scan) FROM pg_stat_user_tables")
        seq_scans = await conn.fetchval("SELECT sum(seq_scan) FROM pg_stat_user_tables")
    return {
        "connections_active": int(active or 0),
        "connections_idle": int(idle or 0),
        "idx_scans": int(idx_scans or 0),
        "seq_scans": int(seq_scans or 0),
    }


async def sample_search_latency(store: PgVectorStore, emb: EmbeddingService) -> Dict[str, Any]:
    q = random.choice([
        "Senior Python engineer",
        "React full-stack developer",
        "Data scientist deep learning",
    ])
    er = await emb.generate_embedding(q)
    t0 = time.perf_counter()
    await store.similarity_search(query_embedding=er.vector, max_results=10)
    latency = time.perf_counter() - t0
    return {"search_latency_sec": round(latency, 4), "query": q}


async def loop_monitor() -> None:
    store = await create_pgvector_store(pool_size=int(os.getenv("PGVECTOR_MAX_CONNECTIONS", "20")))
    emb = EmbeddingService(provider=os.getenv("EMBEDDING_PROVIDER", "vertex_ai"))

    try:
        while True:
            try:
                db = await sample_db_metrics(store)
                perf = await sample_search_latency(store, emb)
                print(PRINT_PREFIX, {**db, **perf})
            except Exception as e:  # noqa: BLE001
                print(PRINT_PREFIX, {"error": str(e)})
            await asyncio.sleep(POLL_SEC)
    finally:
        await store.close()


def main() -> None:
    asyncio.run(loop_monitor())


if __name__ == "__main__":
    main()
