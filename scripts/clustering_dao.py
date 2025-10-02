"""Async helpers for persisting clustering artefacts into PostgreSQL."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

import asyncpg

logger = logging.getLogger(__name__)


def _build_connection_dsn() -> str:
    connection_string = os.getenv("PGVECTOR_CONNECTION_STRING")
    if connection_string:
        return connection_string
    unix_socket = os.getenv("PG_UNIX_SOCKET")
    database = os.getenv("PGVECTOR_DATABASE") or os.getenv("PGDATABASE", "headhunter")
    user = os.getenv("PGVECTOR_USER") or os.getenv("PGUSER", "postgres")
    password = os.getenv("PGVECTOR_PASSWORD") or os.getenv("PGPASSWORD", "")
    if unix_socket:
        return f"postgresql://{user}:{password}@/{database}?host={unix_socket}"
    host = os.getenv("PGVECTOR_HOST") or os.getenv("PGHOST", "localhost")
    port = os.getenv("PGVECTOR_PORT") or os.getenv("PGPORT", "5432")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


async def _connect() -> asyncpg.Connection:
    return await asyncpg.connect(
        _build_connection_dsn(),
        timeout=60,
        server_settings={
            "application_name": "headhunter-clustering-dao",
            "search_path": "public,clustering",
        },
    )


async def upsert_title_embedding(
    normalized_title: str,
    canonical_title: str,
    embedding: Sequence[float],
    chunk_type: str,
    frequency: int,
    metadata: Optional[Mapping[str, Any]] = None,
) -> None:
    conn = await _connect()
    try:
        await conn.execute(
            """
            INSERT INTO clustering.title_embeddings (
                normalized_title,
                canonical_title,
                embedding,
                chunk_type,
                frequency,
                metadata
            ) VALUES ($1, $2, $3, $4, $5, COALESCE($6::jsonb, '{}'::jsonb))
            ON CONFLICT (normalized_title, chunk_type)
            DO UPDATE SET
                canonical_title = EXCLUDED.canonical_title,
                embedding = EXCLUDED.embedding,
                frequency = EXCLUDED.frequency,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            """,
            normalized_title,
            canonical_title,
            list(embedding),
            chunk_type,
            frequency,
            dict(metadata or {}),
        )
    finally:
        await conn.close()


async def bulk_upsert_title_clusters(entries: Iterable[Mapping[str, Any]]) -> None:
    rows = [
        (
            entry.get("normalized_title"),
            int(entry.get("cluster_id")),
            entry.get("method"),
            entry.get("quality_score"),
            dict(entry.get("metadata") or {}),
        )
        for entry in entries
    ]
    rows = [row for row in rows if row[0] and row[2]]
    if not rows:
        return
    conn = await _connect()
    try:
        async with conn.transaction():
            grouped: Dict[str, set[str]] = {}
            for normalized, cluster_id, method, _, _ in rows:
                grouped.setdefault(method, set()).add(normalized)  # type: ignore[arg-type]
            for method, titles in grouped.items():
                await conn.execute(
                    """
                    DELETE FROM clustering.title_clusters
                    WHERE cluster_method = $1 AND normalized_title = ANY($2::text[])
                    """,
                    method,
                    list(titles),
                )
            await conn.executemany(
                """
                INSERT INTO clustering.title_clusters (
                    normalized_title,
                    cluster_id,
                    cluster_method,
                    quality_score,
                    metadata
                ) VALUES ($1, $2, $3, $4, COALESCE($5::jsonb, '{}'::jsonb))
                """,
                rows,
            )
    finally:
        await conn.close()


async def upsert_career_progression(
    from_level: str,
    to_level: str,
    confidence: float,
    evidence_count: int,
    metadata: Optional[Mapping[str, Any]] = None,
) -> None:
    conn = await _connect()
    try:
        await conn.execute(
            """
            INSERT INTO clustering.career_progressions (
                from_level,
                to_level,
                confidence,
                evidence_count,
                metadata
            ) VALUES ($1, $2, $3, $4, COALESCE($5::jsonb, '{}'::jsonb))
            ON CONFLICT (from_level, to_level)
            DO UPDATE SET
                confidence = EXCLUDED.confidence,
                evidence_count = EXCLUDED.evidence_count,
                metadata = EXCLUDED.metadata,
                created_at = clustering.career_progressions.created_at
            """,
            from_level,
            to_level,
            float(confidence),
            int(evidence_count),
            dict(metadata or {}),
        )
    finally:
        await conn.close()


__all__ = [
    "upsert_title_embedding",
    "bulk_upsert_title_clusters",
    "upsert_career_progression",
]
