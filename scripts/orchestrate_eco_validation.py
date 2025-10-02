#!/usr/bin/env python3
"""
Run the ECO validation suite and produce a unified JSON report.

Runs, in order:
 - discover_brazilian_job_dataset.py
 - validate_eco_apis.py
 - validate_pgvector_eco_compatibility.py
 - validate_eco_end_to_end.py
 - validate_data_collection_infrastructure.py

Each step emits JSON; this orchestrator aggregates pass/fail and exits non-zero on failure.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Dict, List


def _collect_actions(res: Dict[str, Any]) -> List[str]:
    actions: List[str] = []
    if not isinstance(res, dict):
        return actions
    top_level_action = res.get("action_required")
    if isinstance(top_level_action, str):
        if top_level_action:
            actions.append(top_level_action)
    elif isinstance(top_level_action, list):
        actions.extend([a for a in top_level_action if a])

    checks = res.get("checks")
    if isinstance(checks, list):
        for check in checks:
            if isinstance(check, dict):
                action = check.get("action_required")
                if not action:
                    continue
                if isinstance(action, list):
                    actions.extend([a for a in action if a])
                else:
                    actions.append(action)
    return actions


def _needs_sample_generation(res: Dict[str, Any]) -> bool:
    if not isinstance(res, dict) or res.get("ok", True):
        return False
    actions = _collect_actions(res)
    for action in actions:
        if "generate_sample_brazilian_job_dataset.py" in action:
            return True
    buckets = res.get("buckets")
    if isinstance(buckets, list) and buckets:
        all_empty = True
        for bucket in buckets:
            if not isinstance(bucket, dict):
                continue
            if bucket.get("samples_checked", 0) > 0 and not bucket.get("sample_errors"):
                all_empty = False
                break
        if all_empty:
            return True
    return False


def run(cmd: List[str]) -> Dict[str, Any]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    try:
        data = json.loads(p.stdout or "{}")
    except Exception:
        data = {"ok": False, "error": (p.stderr or "invalid json").strip()}
    data["rc"] = p.returncode
    data["cmd"] = " ".join(cmd)
    return data


def main() -> int:
    steps = [
        [sys.executable, "scripts/validate_and_deploy_eco_schema.py", "--json"],
        [sys.executable, "scripts/discover_brazilian_job_dataset.py"],
        [sys.executable, "scripts/validate_eco_apis.py"],
        [sys.executable, "scripts/validate_pgvector_eco_compatibility.py"],
        [sys.executable, "scripts/validate_eco_end_to_end.py"],
        [sys.executable, "scripts/validate_data_collection_infrastructure.py"],
    ]
    results: List[Dict[str, Any]] = []
    overall_ok = True
    for s in steps:
        res = run(s)
        entry: Dict[str, Any] = {"name": os.path.basename(s[1]), **res}
        actions = _collect_actions(res)
        if actions:
            entry["action_required"] = actions
        results.append(entry)
        if res.get("rc", 1) != 0 or not res.get("ok", False):
            overall_ok = False

        if os.path.basename(s[1]) == "discover_brazilian_job_dataset.py" and _needs_sample_generation(res):
            generate_cmd = [sys.executable, "scripts/generate_sample_brazilian_job_dataset.py"]
            gen_res = run(generate_cmd)
            gen_entry: Dict[str, Any] = {"name": os.path.basename(generate_cmd[1]), **gen_res}
            gen_actions = _collect_actions(gen_res)
            if gen_actions:
                gen_entry["action_required"] = gen_actions
            results.append(gen_entry)
            if gen_res.get("rc", 1) != 0 or not gen_res.get("ok", False):
                overall_ok = False

    report = {"ok": overall_ok, "steps": results}
    out_path = os.getenv("ECO_VALIDATION_SUITE_REPORT", "scripts/reports/eco_validation_suite.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    for step in results:
        actions = step.get("action_required")
        if not actions:
            continue
        print(f"[action_required] {step.get('name', 'unknown')}")
        for action in actions:
            print(f"  - {action}")
    return 0 if overall_ok else 2


if __name__ == "__main__":
    sys.exit(main())
