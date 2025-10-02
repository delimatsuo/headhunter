#!/usr/bin/env python3
"""
Validate pgvector/ECO compatibility:
 - Ensure pg_trgm and ECO tables exist alongside pgvector tables
 - Enforce 768-dim embedding vectors
 - Optionally run a simple similarity_search cross-check

Emits JSON to stdout and writes scripts/reports/pgvector_eco_compatibility.json.
Exits non-zero on failure.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any, Dict


REPORT_PATH = os.getenv(
    "PGVECTOR_ECO_COMPAT_REPORT",
    "scripts/reports/pgvector_eco_compatibility.json",
)


async def main_async() -> Dict[str, Any]:
    # Reuse existing validators when possible
    try:
        from scripts.pgvector_store import create_pgvector_store  # type: ignore
    except Exception:
        from pgvector_store import create_pgvector_store  # type: ignore
    try:
        from scripts.validate_pgvector_deployment import validate_embeddings  # type: ignore
    except Exception:
        async def validate_embeddings():  # type: ignore
            return {"name": "embedding_provider", "ok": False, "dim": None, "expected_dim": 768, "message": "validator not available"}

    store = await create_pgvector_store(pool_size=int(os.getenv("PGVECTOR_MAX_CONNECTIONS", "10")))
    checks: list[Dict[str, Any]] = []

    # Check extensions and tables
    async with store.get_connection() as conn:
        trgm = await conn.fetchval("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='pg_trgm')")
        eco_tables = await conn.fetchval(
            """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema='public'
              AND table_name IN ('eco_occupation','eco_alias','occupation_crosswalk','eco_template')
            """
        )
        checks.append({"name": "trgm_extension", "ok": bool(trgm)})
        checks.append({"name": "eco_tables", "ok": int(eco_tables or 0) == 4, "count": int(eco_tables or 0)})

    # 768-dim enforcement via embedding generator
    emb_check = await validate_embeddings()
    checks.append(emb_check)

    # Optional similarity_search: ensure function exists
    try:
        async with store.get_connection() as conn:
            has_fn = await conn.fetchval(
                """
                SELECT EXISTS (
                  SELECT 1 FROM pg_proc p
                  JOIN pg_namespace n ON p.pronamespace = n.oid
                  WHERE n.nspname='public' AND p.proname='similarity_search'
                )
                """
            )
        checks.append({"name": "similarity_search_fn", "ok": bool(has_fn)})
    except Exception as e:
        checks.append({"name": "similarity_search_fn", "ok": False, "error": str(e)})

    vector_function_name = "array_to_vector"
    # Ensure array_to_vector is available (pgvector >= 0.5) or define a compatibility wrapper
    try:
        async with store.get_connection() as conn:
            exists = await conn.fetchval(
                """
                SELECT EXISTS (
                  SELECT 1 FROM pg_proc p
                  JOIN pg_namespace n ON p.pronamespace = n.oid
                  WHERE p.proname='array_to_vector'
                    AND pg_catalog.pg_get_function_identity_arguments(p.oid) = 'double precision[]'
                )
                """
            )
            created = False
            if not exists:
                vector_function_name = "array_to_vector_768"
                fallback_exists = await conn.fetchval(
                    """
                    SELECT EXISTS (
                      SELECT 1 FROM pg_proc p
                      JOIN pg_namespace n ON p.pronamespace = n.oid
                      WHERE n.nspname='public'
                        AND p.proname='array_to_vector_768'
                        AND pg_catalog.pg_get_function_identity_arguments(p.oid) = 'double precision[]'
                    )
                    """
                )
                if not fallback_exists:
                    await conn.execute(
                        """
                        DO $$
                        BEGIN
                          IF NOT EXISTS (
                            SELECT 1 FROM pg_proc p
                            JOIN pg_namespace n ON p.pronamespace = n.oid
                            WHERE n.nspname='public'
                              AND p.proname='array_to_vector_768'
                              AND pg_catalog.pg_get_function_identity_arguments(p.oid) = 'double precision[]'
                          ) THEN
                            CREATE FUNCTION public.array_to_vector_768(float8[]) RETURNS vector(768)
                            LANGUAGE plpgsql AS $$
                            BEGIN
                              IF array_length($1,1) <> 768 THEN
                                RAISE EXCEPTION 'Expected 768-dim array, got %', array_length($1,1);
                              END IF;
                              RETURN $1::vector;
                            END;
                            $$;
                          END IF;
                        END
                        $$;
                        """
                    )
                    created = True
            else:
                vector_function_name = "array_to_vector"
        checks.append({
            "name": "array_to_vector_fn",
            "ok": True,
            "created": created,
            "function": vector_function_name,
        })
    except Exception as e:
        vector_function_name = None  # type: ignore
        checks.append({"name": "array_to_vector_fn", "ok": False, "error": str(e)})

    # Exercise similarity_search execution with a minimal call if available
    try:
        async with store.get_connection() as conn:
            vec = [0.0] * 768
            try:
                fn = vector_function_name or "array_to_vector"
                await conn.fetch(
                    f"SELECT * FROM similarity_search({fn}($1::float8[]), 0.0, 1, NULL, 'full_profile')",
                    vec,
                )
                checks.append({"name": "similarity_search_exec", "ok": True})
            except Exception as e:
                checks.append({"name": "similarity_search_exec", "ok": False, "error": str(e)})
    except Exception as e:
        checks.append({"name": "similarity_search_exec", "ok": False, "error": str(e)})

    ok = all(c.get("ok") for c in checks)
    report = {"ok": ok, "checks": checks}
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return report


def main() -> int:
    result = asyncio.run(main_async())
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
