"""
Load ECO aliases and occupation data into PostgreSQL.
References: scripts/pgvector_store.py patterns for asyncpg connection and batching.

Supports multiple sources:
 - CSV with columns eco_id,alias,normalized_alias,confidence,source
 - JSONL from batch_alias_processor (fields: alias, normalized_alias, canonical_normalized, confidence, top_source)
 - CBO crosswalk CSV (columns eco_id, system, code, label, confidence)
"""
import asyncio
import csv
import os
from dataclasses import dataclass
from typing import List, Optional, Iterable, Dict

import asyncpg  # type: ignore
import json

try:
    # Use the shared normalizer so alias fallback matches ECO normalizer behavior
    from scripts.eco_title_normalizer import normalize_title_ptbr  # type: ignore
except Exception:  # pragma: no cover
    def normalize_title_ptbr(s: str) -> str:  # type: ignore
        return (s or "").lower()


@dataclass
class AliasRow:
    eco_id: str
    alias: str
    normalized_alias: str
    confidence: float
    source: Optional[str]


async def load_aliases(pool: asyncpg.Pool, rows: List[AliasRow]) -> int:
    async with pool.acquire() as con:
        async with con.transaction():
            count = 0
            for r in rows:
                await con.execute(
                    """
                    INSERT INTO eco_alias (eco_id, alias, normalized_alias, confidence, source)
                    VALUES ($1,$2,$3,$4,$5)
                    ON CONFLICT (eco_id, normalized_alias) DO UPDATE SET
                      alias=EXCLUDED.alias,
                      confidence=EXCLUDED.confidence,
                      source=EXCLUDED.source,
                      updated_at=NOW()
                    """,
                    r.eco_id,
                    r.alias,
                    r.normalized_alias,
                    r.confidence,
                    r.source,
                )
                count += 1
            return count


def read_csv_aliases(csv_path: str) -> Iterable[AliasRow]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield AliasRow(
                eco_id=row["eco_id"],
                alias=row["alias"],
                normalized_alias=row.get("normalized_alias") or normalize_title_ptbr(row["alias"]),
                confidence=(
                    (lambda val: float(val) if (val is not None and str(val).strip() != "") else 0.75)(
                        row.get("confidence")
                    )
                ),
                source=row.get("source") or None,
            )


def read_jsonl_batch(jsonl_path: str, eco_id_map: Optional[Dict[str, str]] = None) -> Iterable[AliasRow]:
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            eco_id = None
            if eco_id_map:
                eco_id = eco_id_map.get(r.get("canonical_normalized", ""))
            if not eco_id:
                continue
            yield AliasRow(
                eco_id=eco_id,
                alias=r.get("alias", ""),
                normalized_alias=r.get("normalized_alias") or normalize_title_ptbr(r.get("alias", "")),
                confidence=float(r.get("confidence", 0.7)),
                source=r.get("top_source") or None,
            )


async def build_norm_to_eco_map(pool: asyncpg.Pool) -> Dict[str, str]:
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT eco_id, normalized_title FROM eco_occupation WHERE locale='pt-BR' AND country='BR'")
        return {r["normalized_title"]: r["eco_id"] for r in rows}


async def main(path: str, batch_size: int = 500, dry_run: bool = False, mode: str = "csv") -> None:
    conn_args = {
        "user": os.getenv("PGVECTOR_USER", "postgres"),
        "password": os.getenv("PGVECTOR_PASSWORD", ""),
        "database": os.getenv("PGVECTOR_DATABASE", "headhunter"),
        "port": int(os.getenv("PGVECTOR_PORT", "5432")),
    }
    socket = os.getenv("PG_UNIX_SOCKET")
    host = os.getenv("PGVECTOR_HOST", "localhost")
    if socket:
        conn_args["host"] = socket
    else:
        conn_args["host"] = host

    pool = await asyncpg.create_pool(**conn_args, min_size=1, max_size=int(os.getenv("PGVECTOR_MAX_CONNECTIONS", "10")))
    try:
        batch: List[AliasRow] = []
        total = 0
        if mode == "csv":
            iterator = read_csv_aliases(path)
        elif mode == "jsonl":
            eco_map = await build_norm_to_eco_map(pool)
            iterator = read_jsonl_batch(path, eco_id_map=eco_map)
        elif mode == "cbo":
            # CBO crosswalk: we only insert aliases when eco_id exists and label present
            def _iter():
                with open(path, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        eco_id = r.get("eco_id")
                        label = r.get("label")
                        if not eco_id or not label:
                            continue
                        yield AliasRow(
                            eco_id=eco_id,
                            alias=label,
                            normalized_alias=normalize_title_ptbr(label),
                            confidence=float(r.get("confidence", 0.6)),
                            source="CBO",
                        )

            iterator = _iter()
        else:
            raise ValueError("Unsupported mode. Use csv|jsonl|cbo")

        for alias in iterator:
            batch.append(alias)
            if len(batch) >= batch_size:
                if not dry_run:
                    total += await load_aliases(pool, batch)
                batch.clear()
        if batch:
            if not dry_run:
                total += await load_aliases(pool, batch)
        print(f"Loaded {total} aliases from {path} (mode={mode})")
    finally:
        await pool.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Load ECO aliases into PostgreSQL")
    parser.add_argument("path", help="Path to input (CSV/JSONL)")
    parser.add_argument("--mode", choices=["csv", "jsonl", "cbo"], default="csv")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    asyncio.run(main(args.path, batch_size=args.batch_size, dry_run=args.dry_run, mode=args.mode))
