"""Synchronous compatibility layer for the asynchronous PgVectorStore client."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Mapping, Optional

from scripts.pgvector_store import EmbeddingRecord, create_pgvector_store

logger = logging.getLogger(__name__)


class PgVectorStoreAdapter:
    """Expose synchronous helper methods expected by legacy scripts."""

    def __init__(self, connection_string: Optional[str] = None, pool_size: int = 10) -> None:
        self.connection_string = connection_string
        self.pool_size = pool_size

    def upsert_chunks(self, payload: Iterable[Mapping[str, Any]]) -> None:
        """Synchronously persist embedding payloads via the async store."""
        payload_list = list(payload)
        if not payload_list:
            return

        def _coro() -> Awaitable[Any]:
            return self._upsert_chunks_async(payload_list)

        self._run(_coro)

    def list_embeddings(self, chunk_type: str = "job_title") -> List[Dict[str, Any]]:
        """Synchronously load embeddings for the requested chunk type."""

        def _coro() -> Awaitable[List[Dict[str, Any]]]:
            return self._list_embeddings_async(chunk_type)

        return self._run(_coro)

    def list_chunk_ids(self, chunk_type: str = "job_title") -> List[str]:
        """Synchronously fetch chunk identifiers for the requested type."""

        def _coro() -> Awaitable[List[str]]:
            return self._list_chunk_ids_async(chunk_type)

        return self._run(_coro)

    def _run(self, factory: Callable[[], Awaitable[Any]]) -> Any:
        try:
            return asyncio.run(factory())
        except RuntimeError as exc:
            if "event loop is running" not in str(exc):
                raise
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(factory())
            finally:
                loop.close()

    async def _upsert_chunks_async(self, payload: List[Mapping[str, Any]]) -> None:
        store = await create_pgvector_store(self.connection_string, self.pool_size)
        try:
            for entry in payload:
                chunk_id = str(entry.get("chunk_id"))
                embedding = entry.get("embedding")
                if embedding is None:
                    logger.warning("Skipping chunk %s with missing embedding", chunk_id)
                    continue
                vector = list(embedding)
                record_metadata = dict(entry.get("metadata") or {})
                text_value = entry.get("text")
                if text_value:
                    record_metadata.setdefault("text", text_value)
                record_metadata.setdefault("chunk_id", chunk_id)
                chunk_type = entry.get("chunk_type", "job_title")
                model_version = entry.get("model_version", "vertex-ai-textembedding-gecko")
                record = EmbeddingRecord(
                    candidate_id=chunk_id,
                    embedding=vector,
                    model_version=model_version,
                    chunk_type=chunk_type,
                    metadata=record_metadata,
                )
                await store.store_embedding(
                    candidate_id=record.candidate_id,
                    embedding=record.embedding,
                    model_version=record.model_version,
                    chunk_type=record.chunk_type,
                    metadata=record.metadata,
                )
        finally:
            await store.close()

    async def _list_embeddings_async(self, chunk_type: str) -> List[Dict[str, Any]]:
        store = await create_pgvector_store(self.connection_string, self.pool_size)
        try:
            async with store.get_connection() as conn:
                rows = await conn.fetch(
                    """
                    SELECT candidate_id, embedding, metadata, model_version, chunk_type
                    FROM candidate_embeddings
                    WHERE chunk_type = $1
                    ORDER BY candidate_id
                    """,
                    chunk_type,
                )
            results: List[Dict[str, Any]] = []
            for row in rows:
                metadata = dict(row.get("metadata") or {})
                text_value = metadata.get("text") or metadata.get("canonical_title")
                results.append(
                    {
                        "chunk_id": row["candidate_id"],
                        "chunk_type": row["chunk_type"],
                        "text": text_value,
                        "embedding": list(row["embedding"]),
                        "metadata": metadata,
                        "model_version": row["model_version"],
                    }
                )
            return results
        finally:
            await store.close()

    async def _list_chunk_ids_async(self, chunk_type: str) -> List[str]:
        store = await create_pgvector_store(self.connection_string, self.pool_size)
        try:
            async with store.get_connection() as conn:
                rows = await conn.fetch(
                    """
                    SELECT candidate_id
                    FROM candidate_embeddings
                    WHERE chunk_type = $1
                    ORDER BY candidate_id
                    """,
                    chunk_type,
                )
            return [row["candidate_id"] for row in rows]
        finally:
            await store.close()


def get_store(connection_string: Optional[str] = None, pool_size: int = 10) -> PgVectorStoreAdapter:
    """Factory for compatibility with previous loader expectations."""

    return PgVectorStoreAdapter(connection_string=connection_string, pool_size=pool_size)


__all__ = ["PgVectorStoreAdapter", "get_store"]
