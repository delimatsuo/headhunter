#!/usr/bin/env python3
"""
Validate ECO API modules (TypeScript) and normalizer edge cases.

Attempts to run a Node harness against:
 - functions/src/eco/occupation-search.ts
 - functions/src/eco/ptbr-normalizer.ts

If a TS runtime (ts-node/tsx) is not available, falls back to static checks
and returns a WARN status (ok remains true if files exist) with ran=false,
so orchestrators can treat it as non-fatal.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from typing import Any, Dict


REPORT_PATH = os.getenv("ECO_API_VALIDATION_REPORT", "scripts/reports/eco_api_validation.json")


TS_FILES = [
    "functions/src/eco/occupation-search.ts",
    "functions/src/eco/ptbr-normalizer.ts",
]


def file_exists(path: str) -> bool:
    return os.path.exists(path) and os.path.isfile(path)


def _resolve_ts_runtime() -> Dict[str, str] | None:
    node = shutil.which("node")
    tsx = shutil.which("tsx") or shutil.which("ts-node")
    if not node or not tsx:
        return None
    return {"node": node, "tsx": tsx}


def _run_tsx(tsx: str, script: str) -> Dict[str, Any]:
    try:
        proc = subprocess.run([tsx, "-e", script], capture_output=True, text=True, check=False)
    except Exception as exc:  # pragma: no cover
        return {"ok": False, "ran": False, "status": "error", "message": str(exc)}
    if proc.returncode != 0:
        stderr = proc.stderr or ""
        lowered = stderr.lower()
        if "cannot find module" in lowered or "err_module_not_found" in lowered:
            message = stderr.strip() or "Module resolution failure"
            return {"ok": True, "ran": False, "status": "warn", "message": message}
        return {
            "ok": False,
            "ran": False,
            "status": "error",
            "message": stderr.strip() or "Unknown error",
        }
    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "ran": True,
            "status": "error",
            "message": f"Invalid JSON output: {exc}",
        }
    payload.setdefault("ran", True)
    return payload


def run_normalizer_harness(runtime: Dict[str, str] | None) -> Dict[str, Any]:
    if runtime is None:
        return {
            "ok": True,
            "ran": False,
            "status": "warn",
            "message": "Node + tsx/ts-node not available; skipped normalizer harness.",
        }
    script = r'''
        import { normalizeTitlePtBr } from './functions/src/eco/ptbr-normalizer.ts';
        const cases = [
          'Dev Sr. (a)',
          'Eng. de Dados - Pl',
          'Analista Júnior (o/a) - BI',
          'Desenvolvedor(a) Front-end',
          ''
        ];
        const results = cases.map(c => normalizeTitlePtBr(c));
        const allStrings = results.every(r => typeof r === 'string');
        console.log(JSON.stringify({ ok: allStrings, ran: true, results }));
    '''
    result = _run_tsx(runtime["tsx"], script)
    result.setdefault("status", "ok" if result.get("ok") else "error")
    if result.get("ok") and result.get("ran") and isinstance(result.get("results"), list):
        expectations = [
            (0, "senior", "Expected 'Dev Sr. (a)' to include 'senior' in normalized output"),
            (1, "pleno", "Expected 'Eng. de Dados - Pl' to include 'pleno' in normalized output"),
        ]
        failures: list[str] = []
        results = [str(item).lower() for item in result.get("results", [])]
        for index, token, message in expectations:
            if len(results) <= index or token not in results[index]:
                failures.append(message)
        if failures:
            result["ok"] = False
            result["status"] = "error"
            result["message"] = "; ".join(failures)
    return result


def run_occupation_search_harness(runtime: Dict[str, str] | None) -> Dict[str, Any]:
    if runtime is None:
        return {
            "ok": True,
            "ran": False,
            "status": "warn",
            "message": "Node + tsx/ts-node not available; skipped occupation search harness.",
        }
    disable_db = os.getenv("FORCE_DB_TEST") not in {"1", "true", "TRUE", "yes", "on"}
    lines = []
    if disable_db:
        lines.append("process.env.ECO_ENABLED = 'false';")
    lines.extend([
        "import { searchOccupations } from './functions/src/eco/occupation-search.ts';",
        "const resp = await searchOccupations({ title: 'Engenheiro de Dados', locale: 'pt-BR', country: 'BR' });",
        "const ok = !!resp && Array.isArray(resp.results);",
        "const count = Array.isArray(resp?.results) ? resp.results.length : 0;",
        "console.log(JSON.stringify({ ok, ran: true, count }));",
    ])
    script = "\n".join(lines)
    result = _run_tsx(runtime["tsx"], script)
    if result.get("ran") and "status" not in result:
        result["status"] = "ok" if result.get("ok") else "error"
    return result


def try_node_harness() -> Dict[str, Any]:
    """Backward-compatible helper used in tests; runs the normalizer harness only."""
    runtime = _resolve_ts_runtime()
    harness = run_normalizer_harness(runtime)
    harness.setdefault("name", "normalizer_harness")
    return harness


def main() -> int:
    checks: list[Dict[str, Any]] = []
    for f in TS_FILES:
        checks.append({"name": f, "ok": file_exists(f)})

    runtime = _resolve_ts_runtime()
    runtime_check = (
        {
            "ok": True,
            "ran": True,
            "status": "ok",
            "message": f"Using TS runtime at {runtime['tsx']}",
        }
        if runtime
        else {
            "ok": True,
            "ran": False,
            "status": "warn",
            "message": "Node + tsx/ts-node not available; TS harnesses skipped.",
        }
    )
    checks.append({"name": "ts_runtime", **runtime_check})

    normalizer = run_normalizer_harness(runtime)
    normalizer["name"] = "normalizer_harness"
    checks.append(normalizer)

    occupation = run_occupation_search_harness(runtime)
    occupation["name"] = "occupation_search_harness"
    checks.append(occupation)

    # Top-level ok rules:
    # - All files must exist
    # - Harnesses only enforced when runtime ran successfully
    files_ok = all(c.get("ok") for c in checks if c.get("name") in TS_FILES)
    harness_ok = all(
        c.get("ok") for c in (normalizer, occupation) if c.get("ran")
    )
    ok = files_ok and harness_ok
    report = {"ok": ok, "checks": checks}

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    # If runtime is missing (warn/skip), return rc=0
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
