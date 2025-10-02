"""
Phase 4: Embedding pipeline setup and batch backfill

References:
- scripts/embedding_service.py (EmbeddingService)
- scripts/vertex_embeddings_generator.py (Vertex/Google provider)
- scripts/pgvector_store.py (PgVectorStore)

This script initializes the embedding service with Vertex AI provider
and fallback, batches through candidate profiles, performs idempotent
embedding generation (skipping existing), upserts embeddings into the
pgvector store, and produces progress and error reports.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Iterable, List, Optional, Tuple


# Trusting references per plan; do not re-verify.
try:
    from scripts.embedding_service import EmbeddingService  # type: ignore
except Exception:  # pragma: no cover
    # Fallback import path if executed from repo root
    from embedding_service import EmbeddingService  # type: ignore

try:
    from scripts.pgvector_store import PgVectorStore, create_pgvector_store  # type: ignore
except Exception:  # pragma: no cover
    from pgvector_store import PgVectorStore, create_pgvector_store  # type: ignore


DEFAULT_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "64"))
RATE_LIMIT_QPS = float(os.getenv("EMBED_RATE_LIMIT_QPS", "5"))
CONCURRENCY = int(os.getenv("EMBED_CONCURRENCY", "8"))
REPORT_PATH = os.getenv("EMBED_REPORT_PATH", "scripts/embedding_backfill_report.json")


@dataclass
class Candidate:
    id: str
    text: str
    # Optional extra fields
    metadata: Dict[str, Any]


class GracefulExit(Exception):
    pass


def _configure_embedding_service() -> EmbeddingService:
    provider = os.getenv("EMBEDDING_PROVIDER", "vertex_ai")
    # Use new EmbeddingService API (no model/fallback ctor args)
    return EmbeddingService(provider=provider)


async def _configure_store() -> PgVectorStore:
    # Use factory to create initialized store
    return await create_pgvector_store(
        pool_size=int(os.getenv("PGVECTOR_MAX_CONNECTIONS", "20"))
    )


async def _iter_missing_candidates(store: PgVectorStore, batch_size: int) -> AsyncIterator[List[Candidate]]:
    """SQL-driven iteration of candidates missing embeddings."""
    offset = 0
    while True:
        async with store.get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT candidate_id, coalesce(metadata->>'text','') as text
                FROM embedding_metadata
                WHERE processing_status != 'completed' OR total_embeddings = 0
                ORDER BY last_processed NULLS FIRST
                LIMIT $1 OFFSET $2
                """,
                batch_size,
                offset,
            )
        if not rows:
            break
        yield [Candidate(id=r['candidate_id'], text=r['text'], metadata={}) for r in rows]
        offset += len(rows)


async def _embed_and_upsert_batch(
    store: PgVectorStore,
    emb: EmbeddingService,
    batch: List[Candidate],
    rate_limit_qps: float,
) -> Tuple[int, int, List[str]]:
    """Embeds and upserts one batch concurrently. Returns (processed, skipped, failures)."""
    processed = 0
    skipped = 0
    failures: List[str] = []

    sem = asyncio.Semaphore(CONCURRENCY)

    async def process_one(c: Candidate) -> None:
        nonlocal processed
        try:
            res = await emb.generate_embedding(c.text)
            await store.store_embedding(candidate_id=c.id, embedding=res.vector, metadata=c.metadata)
            processed += 1
        except Exception as e:  # noqa: BLE001
            failures.append(f"{c.id}: {e}")

    async def guarded(c: Candidate) -> None:
        async with sem:
            await process_one(c)

    # Execute concurrently
    await asyncio.gather(*(guarded(c) for c in batch))

    # Throttle QPS between batches
    if rate_limit_qps > 0:
        await asyncio.sleep(max(len(batch) / rate_limit_qps, 0))

    return processed, skipped, failures


async def run_pipeline() -> Dict[str, Any]:
    start_ts = time.time()
    emb = _configure_embedding_service()
    store = await _configure_store()

    total_processed = 0
    total_skipped = 0
    all_failures: List[str] = []

    try:
        async for batch in _iter_missing_candidates(store, DEFAULT_BATCH_SIZE):
            p, s, f = await _embed_and_upsert_batch(store, emb, batch, RATE_LIMIT_QPS)
            total_processed += p
            total_skipped += s
            all_failures.extend(f)
    finally:
        try:
            await store.close()
        except Exception:
            pass

    duration = time.time() - start_ts
    report = {
        "processed": total_processed,
        "skipped": total_skipped,
        "failures": all_failures,
        "duration_sec": round(duration, 2),
        "batch_size": DEFAULT_BATCH_SIZE,
        "rate_limit_qps": RATE_LIMIT_QPS,
        "concurrency": CONCURRENCY,
        "timestamp": int(start_ts),
    }

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return report


def _install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    def _raise_graceful(*_: Any) -> None:
        raise GracefulExit()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _raise_graceful)
        except NotImplementedError:
            pass


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _install_signal_handlers(loop)
    try:
        report = loop.run_until_complete(run_pipeline())
        print(json.dumps(report, indent=2))
    except GracefulExit:
        print(json.dumps({"status": "cancelled"}))
        sys.exit(130)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"status": "error", "error": str(e)}))
        sys.exit(1)
    finally:
        try:
            loop.close()
        except Exception:  # pragma: no cover
            pass


if __name__ == "__main__":
    main()
