"""
Process official CBO dataset and generate crosswalk mappings.

Usage:
  python scripts/process_cbo_dataset.py --cbo-csv path/to/cbo.csv --out out_dir [--lookup-db]

If --lookup-db is passed, the script connects to PostgreSQL using PGVECTOR_* env vars
and attempts to match CBO normalized titles to existing eco_occupation.normalized_title.
"""
import asyncio
import csv
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

try:
    from scripts.eco_title_normalizer import normalize_title_ptbr  # type: ignore
except Exception:  # pragma: no cover
    def normalize_title_ptbr(s: str) -> str:  # type: ignore
        return (s or "").lower()


@dataclass
class CboRow:
    code: str
    title: str
    description: Optional[str]
    normalized_title: str


async def load_eco_titles() -> Dict[str, str]:
    """Return mapping normalized_title -> eco_id from DB, if available."""
    try:
        import asyncpg  # type: ignore
    except Exception:
        return {}

    conn_args = {
        "user": os.getenv("PGVECTOR_USER", "postgres"),
        "password": os.getenv("PGVECTOR_PASSWORD", ""),
        "database": os.getenv("PGVECTOR_DATABASE", "headhunter"),
        "port": int(os.getenv("PGVECTOR_PORT", "5432")),
    }
    socket = os.getenv("PG_UNIX_SOCKET")
    host = os.getenv("PGVECTOR_HOST", "localhost")
    conn_args["host"] = socket or host

    pool = await asyncpg.create_pool(**conn_args, min_size=1, max_size=int(os.getenv("PGVECTOR_MAX_CONNECTIONS", "10")))
    try:
        async with pool.acquire() as con:
            rows = await con.fetch("SELECT eco_id, normalized_title FROM eco_occupation WHERE locale='pt-BR' AND country='BR'")
            return {r["normalized_title"]: r["eco_id"] for r in rows}
    finally:
        await pool.close()


def read_cbo_csv(path: str) -> List[CboRow]:
    rows: List[CboRow] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            code = (r.get("code") or r.get("codigo") or r.get("CBO") or r.get("Cod") or "").strip()
            title = (r.get("title") or r.get("titulo") or r.get("Titulo") or r.get("ocupacao") or "").strip()
            desc = r.get("description") or r.get("descricao") or None
            if not code or not title:
                continue
            rows.append(CboRow(code=code, title=title, description=desc, normalized_title=normalize_title_ptbr(title)))
    return rows


def score_match(norm: str, candidates: List[str]) -> List[Tuple[str, float]]:
    # Simple exact > prefix > contains scoring
    scored: List[Tuple[str, float]] = []
    for cand in candidates:
        if cand == norm:
            scored.append((cand, 1.0))
        elif cand.startswith(norm) or norm.startswith(cand):
            scored.append((cand, 0.85))
        elif norm in cand or cand in norm:
            scored.append((cand, 0.7))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


async def main(cbo_csv: str, out_dir: str, lookup_db: bool = False) -> None:
    os.makedirs(out_dir, exist_ok=True)
    cbo_rows = read_cbo_csv(cbo_csv)
    eco_map: Dict[str, str] = {}
    if lookup_db:
        eco_map = await load_eco_titles()

    date = datetime.utcnow().strftime("%Y%m%d")
    out_path = os.path.join(out_dir, f"cbo_crosswalk_{date}.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["eco_id", "system", "code", "label", "confidence", "normalized_title", "status"])
        for row in cbo_rows:
            eco_id = None
            conf = 0.0
            status = "unmatched"
            if eco_map:
                matches = score_match(row.normalized_title, list(eco_map.keys()))
                if matches:
                    best_norm, conf = matches[0]
                    if conf >= 0.70:
                        eco_id = eco_map.get(best_norm)
                        status = "matched"
                    else:
                        status = "low_confidence"
            w.writerow([eco_id or "", "CBO", row.code, row.title, f"{conf:.2f}", row.normalized_title, status])
    print(f"Wrote crosswalk CSV: {out_path} (rows={len(cbo_rows)})")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Process CBO dataset and generate crosswalk mappings")
    p.add_argument("--cbo-csv", required=True, help="Path to CBO CSV file")
    p.add_argument("--out", required=True, help="Output directory")
    p.add_argument("--lookup-db", action="store_true", help="Lookup existing ECO occupations in DB for mapping")
    args = p.parse_args()

    asyncio.run(main(args.cbo_csv, args.out, lookup_db=args.lookup_db))
