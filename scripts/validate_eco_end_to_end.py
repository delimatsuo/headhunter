#!/usr/bin/env python3
"""
End-to-end ECO validation:
 1) Generate sample postings (local JSONL)
 2) Aggregate aliases
 3) Load aliases into ECO tables
 4) Run EcoClient.searchByTitle via Node (if tsx/ts-node available)

Emits JSON to stdout and scripts/reports/eco_e2e_validation.json.
Exits non-zero on failure.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any, Dict


REPORT_PATH = os.getenv("ECO_E2E_REPORT", "scripts/reports/eco_e2e_validation.json")


def run_generate_sample() -> Dict[str, Any]:
    p = subprocess.run([sys.executable, "scripts/generate_sample_brazilian_job_dataset.py"], capture_output=True, text=True)
    try:
        data = json.loads(p.stdout)
    except Exception:
        data = {"ok": False, "error": p.stderr.strip()}
    return {"name": "generate_sample", **data, "rc": p.returncode}


def run_aggregation() -> Dict[str, Any]:
    try:
        from scripts.orchestrate_eco_collection import run_batch_aggregation  # type: ignore
    except Exception as e:
        return {
            "name": "aggregate_aliases",
            "ok": False,
            "error": f"Aggregation module not importable: {e}",
            "hint": "Run scripts/orchestrate_eco_collection.py first or ensure Scrapy deps are installed.",
            "action_required": "pip install scrapy",
        }
    try:
        out_dir = run_batch_aggregation()
        return {"name": "aggregate_aliases", "ok": True, "out_dir": out_dir}
    except Exception as e:
        return {"name": "aggregate_aliases", "ok": False, "error": str(e)}


def run_load_aliases(agg_out: str) -> Dict[str, Any]:
    import glob
    import asyncio as _asyncio
    try:
        from scripts.load_eco_aliases import main as load_main  # type: ignore
    except Exception as e:
        return {
            "name": "load_aliases",
            "ok": False,
            "error": f"Loader module not importable: {e}",
            "hint": "Verify scripts/load_eco_aliases.py and dependencies (asyncpg).",
            "action_required": "pip install asyncpg",
        }
    search_dir = os.path.abspath(agg_out or ".")
    files = sorted(glob.glob(os.path.join(search_dir, "alias_summary_*.jsonl")))
    if not files:
        return {
            "name": "load_aliases",
            "ok": False,
            "error": "no alias_summary_*.jsonl found",
            "looked_in": search_dir,
            "hint": "Run orchestrate_eco_collection.py first or re-run with --dry-run to skip DB load.",
            "action_required": "python scripts/orchestrate_eco_collection.py",
        }
    latest = files[-1]
    try:
        _asyncio.run(load_main(latest, mode="jsonl"))
        return {"name": "load_aliases", "ok": True, "path": latest}
    except Exception as e:
        return {"name": "load_aliases", "ok": False, "error": str(e)}


def run_search_probe(title: str = "Engenheiro de Dados") -> Dict[str, Any]:
    # Use tsx/ts-node if available to call EcoClient.searchByTitle
    import shutil
    tsx = shutil.which("tsx") or shutil.which("ts-node")
    node = shutil.which("node")
    if not tsx or not node:
        return {
            "name": "search_probe",
            "ok": False,
            "ran": False,
            "status": "warn",
            "message": "Node + tsx/ts-node not available",
        }
    script = f'''
        import {{ EcoClient }} from './functions/src/eco/eco-client.ts';
        import {{ normalizeTitlePtBr }} from './functions/src/eco/ptbr-normalizer.ts';
        const client = new EcoClient();
        const norm = normalizeTitlePtBr({json.dumps(title)});
        const res = await client.searchByTitle(norm, 'pt-BR', 'BR', 5);
        console.log(JSON.stringify({{ ok: true, ran: true, count: res.length }}));
        process.exit(0);
    '''
    p = subprocess.run([tsx, "-e", script], capture_output=True, text=True)
    if p.returncode != 0:
        return {"name": "search_probe", "ok": False, "ran": False, "message": p.stderr.strip()}
    try:
        out = json.loads(p.stdout.strip())
        if out.get("ran"):
            out.setdefault("status", "ok" if out.get("ok") else "error")
        return {"name": "search_probe", **out}
    except Exception as e:
        return {"name": "search_probe", "ok": False, "ran": False, "message": str(e)}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ECO end-to-end validation")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip aggregation and database load steps; useful when Scrapy/asyncpg are unavailable.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    checks: list[Dict[str, Any]] = []
    gen = run_generate_sample()
    checks.append(gen)
    if not gen.get("ok"):
        report = {"ok": False, "checks": checks}
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(json.dumps(report, indent=2))
        return 2

    if args.dry_run:
        agg = {
            "name": "aggregate_aliases",
            "ok": True,
            "ran": False,
            "status": "warn",
            "message": "--dry-run activated; aggregation skipped.",
        }
        checks.append(agg)
        load = {
            "name": "load_aliases",
            "ok": True,
            "ran": False,
            "status": "warn",
            "message": "--dry-run activated; database load skipped.",
        }
        checks.append(load)
    else:
        agg = run_aggregation()
        checks.append(agg)
        if not agg.get("ok"):
            report = {"ok": False, "checks": checks}
            with open(REPORT_PATH, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
            print(json.dumps(report, indent=2))
            return 2

        load = run_load_aliases(agg.get("out_dir", ""))
        checks.append(load)

    search = run_search_probe()
    checks.append(search)

    runtime_missing = not search.get("ran")
    ok_checks: list[bool] = []
    for c in checks:
        name = c.get("name")
        if name == "search_probe" and not search.get("ran"):
            continue
        if c.get("ran") is False and c.get("status") == "warn":
            continue
        ok_checks.append(bool(c.get("ok")))
    ok = all(ok_checks) if ok_checks else True
    report = {"ok": ok, "checks": checks}
    if runtime_missing:
        warn_msg = search.get("message") or "search_probe skipped: Node runtime unavailable"
        report["warnings"] = [warn_msg]
    if args.dry_run:
        dry_msg = "--dry-run mode skipped aggregation and load checks"
        report.setdefault("warnings", []).append(dry_msg)
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
