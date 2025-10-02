#!/usr/bin/env python3
"""
Validate and (if needed) deploy the ECO database schema.

Responsibilities:
1) Connect to PostgreSQL using same parameters as pgvector infra
2) Check if core ECO tables exist
3) If missing, deploy scripts/eco_schema.sql
4) Validate structure, indexes, and seed data
5) Exercise trigram/similarity functions where applicable
6) Run health checks and generate a comprehensive report

Safe to run multiple times (idempotent). Emits detailed logs and a final
JSON-like summary for downstream orchestration.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# Optional imports guarded to avoid hard failures if unavailable
try:
    import psycopg2  # type: ignore
    from psycopg2 import sql  # type: ignore
except Exception:  # pragma: no cover - handled at runtime
    psycopg2 = None
    sql = None


LOGGER = logging.getLogger("validate_and_deploy_eco_schema")


CORE_TABLES = [
    "eco_occupation",
    "eco_alias",
    "occupation_crosswalk",
    "eco_template",
]


@dataclass
class SectionResult:
    name: str
    status: str  # pass | fail | warn | skip
    details: List[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    ok: bool
    sections: List[SectionResult] = field(default_factory=list)

    def add(self, name: str, status: str, *details: str) -> None:
        self.sections.append(SectionResult(name=name, status=status, details=list(details)))

    def to_dict(self) -> Dict:
        return {
            "ok": self.ok,
            "sections": [
                {"name": s.name, "status": s.status, "details": s.details} for s in self.sections
            ],
        }


def _load_db_env_from_pgvector() -> Dict[str, str]:
    """Attempt to import connection hints from scripts/pgvector_store.py if present.

    Falls back to environment variables. No hard dependency.

    Extended to handle pgvector-style envs and Unix sockets with precedence:
    1) If PG_UNIX_SOCKET is set, use it as host and disable SSL.
    2) Else prefer PGVECTOR_* over PG*.
    3) Fall back to defaults or hints from pgvector_store.py.
    """
    params: Dict[str, str] = {}
    params["RESOLVED_SOURCE"] = "defaults"
    params["USE_UNIX_SOCKET"] = "0"
    try:
        # Dynamically import without assuming install
        import importlib.util

        module_path = Path(__file__).parent / "pgvector_store.py"
        if module_path.exists():
            spec = importlib.util.spec_from_file_location("pgvector_store", str(module_path))
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)  # type: ignore
                # Heuristic attribute checks commonly used
                for key in ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD"):
                    if hasattr(mod, key):
                        params[key] = getattr(mod, key)
                # Also support dictionary-ish config
                if hasattr(mod, "DB_CONFIG") and isinstance(getattr(mod, "DB_CONFIG"), dict):
                    params.update({k.upper(): str(v) for k, v in getattr(mod, "DB_CONFIG").items()})
                params["RESOLVED_SOURCE"] = "module_pgvector_store"
    except Exception as e:  # pragma: no cover - fallback expected
        LOGGER.debug("Could not import pgvector_store hints: %s", e)

    # Highest precedence: Unix socket
    unix_socket = os.getenv("PG_UNIX_SOCKET")
    if unix_socket:
        params["PGHOST"] = unix_socket
        # Port is ignored for Unix sockets, but keep a sane default
        params["PGPORT"] = os.getenv("PGPORT", params.get("PGPORT", "5432"))
        params["PGDATABASE"] = os.getenv("PGVECTOR_DATABASE") or os.getenv("PGDATABASE") or params.get("PGDATABASE", "postgres")
        params["PGUSER"] = os.getenv("PGVECTOR_USER") or os.getenv("PGUSER") or params.get("PGUSER", os.getenv("USER", "postgres"))
        params["PGPASSWORD"] = os.getenv("PGVECTOR_PASSWORD") or os.getenv("PGPASSWORD") or params.get("PGPASSWORD", "")
        params["RESOLVED_SOURCE"] = "unix_socket"
        params["USE_UNIX_SOCKET"] = "1"
    else:
        # Next precedence: PGVECTOR_*
        vector_env = {
            "PGHOST": os.getenv("PGVECTOR_HOST"),
            "PGPORT": os.getenv("PGVECTOR_PORT"),
            "PGDATABASE": os.getenv("PGVECTOR_DATABASE"),
            "PGUSER": os.getenv("PGVECTOR_USER"),
            "PGPASSWORD": os.getenv("PGVECTOR_PASSWORD"),
        }
        if any(vector_env.values()):
            params.update({k: v for k, v in vector_env.items() if v is not None})
            params["RESOLVED_SOURCE"] = "pgvector_env"

        # Finally, fall back to PG* envs if not already set
        for k in ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD"):
            if k not in params or not params[k]:
                if os.getenv(k):
                    params[k] = os.getenv(k, "")

    # Minimal defaults if nothing found (prefer pgvector-style envs for parity with EcoClient)
    params.setdefault("PGHOST", os.getenv("PGVECTOR_HOST", "localhost"))
    params.setdefault("PGPORT", os.getenv("PGVECTOR_PORT", "5432"))
    params.setdefault("PGDATABASE", os.getenv("PGVECTOR_DATABASE", "headhunter"))
    params.setdefault("PGUSER", os.getenv("PGVECTOR_USER", os.getenv("USER", "postgres")))
    params.setdefault("PGPASSWORD", os.getenv("PGVECTOR_PASSWORD", ""))

    LOGGER.info(
        "Validator targeting database '%s' (source=%s)",
        params.get("PGDATABASE"),
        params.get("RESOLVED_SOURCE"),
    )
    return params


def _connect() -> Optional["psycopg2.extensions.connection"]:
    if psycopg2 is None:
        LOGGER.error("psycopg2 not available. Install it to validate the schema.")
        return None
    cfg = _load_db_env_from_pgvector()
    try:
        connect_args = dict(
            host=cfg.get("PGHOST"),
            port=int(cfg.get("PGPORT", "5432")),
            dbname=cfg.get("PGDATABASE"),
            user=cfg.get("PGUSER"),
            password=cfg.get("PGPASSWORD"),
        )
        # When using Unix sockets, disable SSL as it is not applicable
        if cfg.get("USE_UNIX_SOCKET") == "1":
            connect_args["sslmode"] = "disable"  # type: ignore
        LOGGER.info(
            "Connecting to PostgreSQL (source=%s host=%s port=%s db=%s user=%s sslmode=%s)",
            cfg.get("RESOLVED_SOURCE"),
            connect_args.get("host"),
            connect_args.get("port"),
            connect_args.get("dbname"),
            connect_args.get("user"),
            "disable" if cfg.get("USE_UNIX_SOCKET") == "1" else os.getenv("PGVECTOR_SSL_MODE", "prefer"),
        )
        conn = psycopg2.connect(**connect_args)
        conn.autocommit = False
        return conn
    except Exception as e:
        LOGGER.error("Failed to connect to PostgreSQL: %s", e)
        return None


def _table_exists(cur, table: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
          SELECT 1
          FROM information_schema.tables
          WHERE table_schema = 'public' AND table_name = %s
        );
        """,
        (table,),
    )
    return bool(cur.fetchone()[0])


def _deploy_schema(conn) -> Tuple[bool, List[str]]:
    messages: List[str] = []
    schema_path = Path(__file__).parent / "eco_schema.sql"
    if not schema_path.exists():
        return False, [f"Schema file not found at {schema_path}"]
    try:
        # Try to ensure pg_trgm exists; warn but do not fail if not permitted
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='pg_trgm')")
                has = bool(cur.fetchone()[0])
                if not has:
                    try:
                        cur.execute("CREATE EXTENSION pg_trgm")
                        messages.append("pg_trgm extension created.")
                    except Exception as e:
                        messages.append(f"WARN: pg_trgm not created: {e}")
        except Exception as e:
            messages.append(f"WARN: pg_trgm pre-check failed: {e}")

        with open(schema_path, "r", encoding="utf-8") as f:
            sql_text = f.read()
        # NOTE: We intentionally rely on Python-managed transactions to avoid
        # nesting BEGIN/COMMIT in SQL and driver-level transactions.
        with conn.cursor() as cur:
            cur.execute(sql_text)
        conn.commit()
        messages.append("Schema deployed successfully.")
        return True, messages
    except Exception as e:
        conn.rollback()
        return False, [f"Schema deployment failed: {e}"]


def _validate_structure(conn) -> Tuple[bool, List[str]]:
    msgs: List[str] = []
    ok = True
    try:
        with conn.cursor() as cur:
            for tbl in CORE_TABLES:
                exists = _table_exists(cur, tbl)
                if not exists:
                    ok = False
                    msgs.append(f"Missing table: {tbl}")
                else:
                    msgs.append(f"Found table: {tbl}")
            # Column/type checks per PRD
            # eco_occupation.normalized_title TEXT
            try:
                cur.execute(
                    """
                    SELECT data_type
                    FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='eco_occupation' AND column_name='normalized_title'
                    """
                )
                row = cur.fetchone()
                if not row or (row[0] or '').lower() != 'text':
                    ok = False
                    msgs.append("Expected eco_occupation.normalized_title TEXT")
                else:
                    msgs.append("eco_occupation.normalized_title is TEXT")
            except Exception as e:
                ok = False
                msgs.append(f"Error checking eco_occupation.normalized_title: {e}")

            # eco_alias.confidence NUMERIC(5,4)
            try:
                cur.execute(
                    """
                    SELECT data_type, numeric_precision, numeric_scale
                    FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='eco_alias' AND column_name='confidence'
                    """
                )
                row = cur.fetchone()
                if not row or (row[0] or '').lower() != 'numeric' or int(row[1] or 0) != 5 or int(row[2] or 0) != 4:
                    ok = False
                    msgs.append("Expected eco_alias.confidence NUMERIC(5,4)")
                else:
                    msgs.append("eco_alias.confidence is NUMERIC(5,4)")
            except Exception as e:
                ok = False
                msgs.append(f"Error checking eco_alias.confidence: {e}")

            # Unique constraints
            # eco_occupation(eco_id)
            try:
                cur.execute(
                    """
                    SELECT array_agg(att.attname ORDER BY att.attnum) AS cols
                    FROM pg_constraint con
                    JOIN pg_class rel ON rel.oid = con.conrelid
                    JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
                    JOIN unnest(con.conkey) AS k(attnum) ON TRUE
                    JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = k.attnum
                    WHERE con.contype='u' AND nsp.nspname='public' AND rel.relname='eco_occupation'
                    GROUP BY con.conname
                    """
                )
                uniques = [set(r[0]) for r in cur.fetchall()]
                if {"eco_id"} not in uniques:
                    ok = False
                    msgs.append("Missing UNIQUE constraint on eco_occupation(eco_id)")
                else:
                    msgs.append("Unique constraint on eco_occupation(eco_id) present")
            except Exception as e:
                ok = False
                msgs.append(f"Error checking unique constraints on eco_occupation: {e}")

            # eco_alias(eco_id, normalized_alias)
            try:
                cur.execute(
                    """
                    SELECT array_agg(att.attname ORDER BY att.attnum) AS cols
                    FROM pg_constraint con
                    JOIN pg_class rel ON rel.oid = con.conrelid
                    JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
                    JOIN unnest(con.conkey) AS k(attnum) ON TRUE
                    JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = k.attnum
                    WHERE con.contype='u' AND nsp.nspname='public' AND rel.relname='eco_alias'
                    GROUP BY con.conname
                    """
                )
                uniques_alias = [tuple(r[0]) for r in cur.fetchall()]
                if ("eco_id", "normalized_alias") not in uniques_alias:
                    ok = False
                    msgs.append("Missing UNIQUE constraint on eco_alias(eco_id, normalized_alias)")
                else:
                    msgs.append("Unique constraint on eco_alias(eco_id, normalized_alias) present")
            except Exception as e:
                ok = False
                msgs.append(f"Error checking unique constraints on eco_alias: {e}")
            # Basic index health checks (trigram / vector if present)
            cur.execute(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                """
            )
            indexes = cur.fetchall()
            trigram_ok = False
            for name, definition in indexes:
                if definition and "gin_trgm_ops" in definition:
                    trigram_ok = True
                    break
            if trigram_ok:
                msgs.append("Trigram index detected.")
            else:
                msgs.append("No trigram index detected (warn if expected).")

            # Triggers existence
            try:
                cur.execute(
                    """
                    SELECT tgname FROM pg_trigger t
                    JOIN pg_class c ON c.oid = t.tgrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname='public'
                    """
                )
                trig_names = {r[0] for r in cur.fetchall()}
                expected = {
                    "tr_eco_occupation_updated_at",
                    "tr_eco_alias_updated_at",
                    "tr_eco_template_updated_at",
                }
                missing = [t for t in expected if t not in trig_names]
                if missing:
                    ok = False
                    msgs.append(f"Missing triggers: {', '.join(missing)}")
                else:
                    msgs.append("All expected updated_at triggers present")
            except Exception as e:
                ok = False
                msgs.append(f"Error checking triggers: {e}")
    except Exception as e:
        return False, [f"Structure validation error: {e}"]
    return ok, msgs


def _validate_seed_data(conn) -> Tuple[bool, List[str]]:
    msgs: List[str] = []
    ok = True
    try:
        with conn.cursor() as cur:
            if _table_exists(cur, "eco_occupation"):
                cur.execute("SELECT COUNT(1) FROM eco_occupation;")
                cnt = cur.fetchone()[0]
                msgs.append(f"eco_occupation row count: {cnt}")
                required_ids = ["ECO.BR.SE.FRONTEND", "ECO.BR.SE.DATAENG"]
                cur.execute(
                    """
                    SELECT eco_id, COUNT(*)
                    FROM eco_occupation
                    WHERE eco_id = ANY(%s)
                    GROUP BY eco_id
                    """,
                    (required_ids,),
                )
                found = {row[0]: int(row[1]) for row in cur.fetchall()}
                for eco_id in required_ids:
                    count = found.get(eco_id, 0)
                    if count:
                        msgs.append(f"Seed {eco_id} present ({count} rows)")
                    else:
                        msgs.append(f"Seed {eco_id} missing")
                        ok = False
            if _table_exists(cur, "eco_alias"):
                cur.execute("SELECT COUNT(1) FROM eco_alias;")
                cnt2 = cur.fetchone()[0]
                msgs.append(f"eco_alias row count: {cnt2}")
    except Exception as e:
        return False, [f"Seed validation error: {e}"]
    return ok, msgs


def _exercise_similarity(conn) -> Tuple[bool, List[str]]:
    msgs: List[str] = []
    try:
        with conn.cursor() as cur:
            # If pg_trgm is installed, show_version should work
            cur.execute("SELECT extname FROM pg_extension;")
            exts = [row[0] for row in cur.fetchall()]
            if "pg_trgm" in exts:
                msgs.append("pg_trgm extension present.")
            else:
                msgs.append("pg_trgm extension not present (skip similarity test).")
                return True, msgs

            # Try a light similarity check if eco_alias has data
            if _table_exists(cur, "eco_alias"):
                cur.execute(
                    """
                    SELECT a1.alias, a2.alias
                    FROM eco_alias a1
                    JOIN eco_alias a2 ON a1.id <> a2.id
                    WHERE similarity(a1.alias, a2.alias) > 0.7
                    LIMIT 1;
                    """
                )
                _ = cur.fetchall()  # No assertion on content; just exercising
                msgs.append("Similarity function exercised.")
            else:
                msgs.append("eco_alias table missing; skipping similarity exercise.")
    except Exception as e:
        return False, [f"Similarity exercise failed: {e}"]
    return True, msgs


def run_validation(deploy_if_missing: bool = True) -> ValidationReport:
    report = ValidationReport(ok=True)

    conn = _connect()
    if conn is None:
        report.ok = False
        report.add("database_connection", "fail", "Unable to connect to PostgreSQL.")
        return report

    try:
        with conn.cursor() as cur:
            missing = [t for t in CORE_TABLES if not _table_exists(cur, t)]
        if missing:
            if deploy_if_missing:
                success, msgs = _deploy_schema(conn)
                report.add("deploy_schema", "pass" if success else "fail", *msgs)
                if not success:
                    report.ok = False
            else:
                report.add(
                    "schema_presence",
                    "fail",
                    f"Missing tables: {', '.join(missing)}",
                )
                report.ok = False
        else:
            report.add("schema_presence", "pass", "All core ECO tables present.")

        ok_struct, msgs_struct = _validate_structure(conn)
        report.add("structure_checks", "pass" if ok_struct else "fail", *msgs_struct)
        if not ok_struct:
            report.ok = False

        ok_seed, msgs_seed = _validate_seed_data(conn)
        report.add("seed_data", "pass" if ok_seed else "fail", *msgs_seed)
        if not ok_seed:
            report.ok = False

        ok_sim, msgs_sim = _exercise_similarity(conn)
        report.add("similarity_functions", "pass" if ok_sim else "fail", *msgs_sim)
        if not ok_sim:
            report.ok = False

    finally:
        try:
            conn.close()
        except Exception:
            pass

    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and deploy ECO schema")
    parser.add_argument(
        "--no-deploy",
        action="store_true",
        help="Do not deploy schema if missing; only report",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON report to stdout")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    report = run_validation(deploy_if_missing=not args.no_deploy)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        for s in report.sections:
            LOGGER.info("[%s] %s", s.status.upper(), s.name)
            for d in s.details:
                LOGGER.info("  - %s", d)
        LOGGER.info("Overall OK: %s", report.ok)
    return 0 if report.ok else 2


if __name__ == "__main__":
    sys.exit(main())
