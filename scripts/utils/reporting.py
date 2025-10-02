#!/usr/bin/env python3
"""
Shared reporting and logging utilities for scripts.

Functions:
- ensure_reports_dir(path)
- _log(name, msg)
- save_json_report(path, data)
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict


def ensure_reports_dir(path: str = "reports") -> str:
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
    return path


def _log(name: str, msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    print(f"[{name}] {ts} | {msg}")


def save_json_report(path: str, data: Dict[str, Any]) -> str:
    ensure_reports_dir(os.path.dirname(path) or ".")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path

