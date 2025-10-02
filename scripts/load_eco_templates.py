"""Load generated ECO templates into PostgreSQL."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

import asyncpg  # type: ignore


@dataclass
class TemplateRow:
    eco_id: str
    required_skills: List[Dict[str, Any]]
    preferred_skills: List[Dict[str, Any]]
    min_years_experience: Optional[int]
    max_years_experience: Optional[int]
    prevalence_by_region: Optional[Dict[str, Any]]
    experience_distribution: Optional[Dict[str, Any]]
    confidence: Optional[float]
    metadata: Dict[str, Any]


async def _fetch_template_columns(connection: asyncpg.Connection) -> List[str]:
    rows = await connection.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'eco_template'
        """
    )
    return [row["column_name"] for row in rows]


async def _ensure_unique_constraint(connection: asyncpg.Connection) -> None:
    await connection.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'eco_template_eco_id_key'
            ) THEN
                ALTER TABLE eco_template ADD CONSTRAINT eco_template_eco_id_key UNIQUE (eco_id);
            END IF;
        END
        $$;
        """
    )


def _load_templates(path: str) -> Iterable[TemplateRow]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        records = payload.values()
    elif isinstance(payload, list):
        records = payload
    else:
        raise ValueError("Unexpected template format")
    for entry in records:
        eco_id = entry.get("occupation") or entry.get("eco_id")
        if not eco_id:
            continue
        metadata = entry.get("metadata", {}).copy()
        metadata["experience_distribution"] = entry.get("experience_distribution")
        metadata["prevalence_by_region"] = entry.get("prevalence_by_region")
        metadata["confidence"] = entry.get("confidence")
        metadata["version"] = entry.get("version")
        yield TemplateRow(
            eco_id=str(eco_id),
            required_skills=entry.get("required_skills", []),
            preferred_skills=entry.get("preferred_skills", []),
            min_years_experience=_safe_int(entry.get("min_years_experience")),
            max_years_experience=_safe_int(entry.get("max_years_experience")),
            prevalence_by_region=entry.get("prevalence_by_region"),
            experience_distribution=entry.get("experience_distribution"),
            confidence=entry.get("confidence"),
            metadata=metadata,
        )


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


async def load_templates(path: str, batch_size: int = 100, dry_run: bool = False) -> int:
    conn_args = {
        "user": os.getenv("PGVECTOR_USER", os.getenv("PGUSER", "postgres")),
        "password": os.getenv("PGVECTOR_PASSWORD", os.getenv("PGPASSWORD", "")),
        "database": os.getenv("PGVECTOR_DATABASE", os.getenv("PGDATABASE", "headhunter")),
        "port": int(os.getenv("PGVECTOR_PORT", os.getenv("PGPORT", "5432"))),
        "host": os.getenv("PGVECTOR_HOST", os.getenv("PGHOST", "localhost")),
    }
    pool = await asyncpg.create_pool(**conn_args, min_size=1, max_size=int(os.getenv("PGVECTOR_MAX_CONNECTIONS", "10")))
    total = 0
    try:
        async with pool.acquire() as connection:
            await _ensure_unique_constraint(connection)
            columns = await _fetch_template_columns(connection)
        batch: List[TemplateRow] = []
        async with pool.acquire() as connection:
            async with connection.transaction():
                for row in _load_templates(path):
                    batch.append(row)
                    if len(batch) >= batch_size:
                        if not dry_run:
                            total += await _upsert_batch(connection, batch, columns)
                        batch.clear()
                if batch:
                    if not dry_run:
                        total += await _upsert_batch(connection, batch, columns)
        return total
    finally:
        await pool.close()


async def _upsert_batch(connection: asyncpg.Connection, rows: Sequence[TemplateRow], columns: Sequence[str]) -> int:
    count = 0
    for row in rows:
        payload = {
            "eco_id": row.eco_id,
            "required_skills": json.dumps(row.required_skills),
            "preferred_skills": json.dumps(row.preferred_skills),
            "min_years_experience": row.min_years_experience,
            "max_years_experience": row.max_years_experience,
            "notes": json.dumps(row.metadata, ensure_ascii=False),
        }
        if "prevalence_by_region" in columns:
            payload["prevalence_by_region"] = json.dumps(row.prevalence_by_region or {})
        if "experience_distribution" in columns and row.experience_distribution is not None:
            payload["experience_distribution"] = json.dumps(row.experience_distribution)
        if "confidence" in columns and row.confidence is not None:
            payload["confidence"] = row.confidence
        insert_cols = ", ".join(payload.keys())
        placeholders = ", ".join(f"${idx}" for idx in range(1, len(payload) + 1))
        updates = ", ".join(f"{col}=EXCLUDED.{col}" for col in payload.keys() if col != "eco_id")
        values = list(payload.values())
        await connection.execute(
            f"""
            INSERT INTO eco_template ({insert_cols})
            VALUES ({placeholders})
            ON CONFLICT (eco_id) DO UPDATE SET {updates}, updated_at = NOW()
            """,
            *values,
        )
        count += 1
    return count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Load ECO templates into PostgreSQL")
    parser.add_argument("path", help="Path to ECO template JSON")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    records = asyncio.run(load_templates(args.path, batch_size=args.batch_size, dry_run=args.dry_run))
    print(f"Loaded {records} templates from {args.path}")
