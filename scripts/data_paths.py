"""Utilities for resolving local dataset paths used by batch-processing scripts."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple


def repo_root() -> Path:
    """Return the repository root based on this file's location."""
    return Path(__file__).resolve().parents[1]


def _from_env(var_name: str) -> Path | None:
    value = os.getenv(var_name)
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.exists() else None


def dataset_root() -> Path:
    """Resolve the preferred dataset root directory.

    Priority order:
    1. `HEADHUNTER_DATASET_DIR` environment variable
    2. `datasets/` inside the repo (added in this change)
    3. Legacy `CSV files/` directory shipped with the original dataset dump
    """
    env_root = _from_env("HEADHUNTER_DATASET_DIR")
    if env_root is not None:
        return env_root

    root = repo_root()
    default = root / "datasets"
    if default.exists():
        return default

    legacy = root / "CSV files"
    return legacy if legacy.exists() else default


def csv_dir() -> Path:
    """Resolve where candidate CSV files live inside the dataset root."""
    env_csv = _from_env("HEADHUNTER_CSV_DIR")
    if env_csv is not None:
        return env_csv

    root = dataset_root()
    candidates = [
        root / "csv",
        root / "CSV",
        root / "candidates",
        root / "505039_Ella_Executive_Search_CSVs_1",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    # Fallback to repo legacy structure
    legacy = repo_root() / "CSV files" / "505039_Ella_Executive_Search_CSVs_1"
    return legacy if legacy.exists() else candidates[0]


def resumes_dir() -> Path:
    """Resolve the directory that holds resume assets."""
    env_resumes = _from_env("HEADHUNTER_RESUME_DIR")
    if env_resumes is not None:
        return env_resumes

    root = dataset_root()
    candidates = [
        root / "resumes",
        root / "resume_files",
        root / "505039_Ella_Executive_Search_files_1" / "resumes",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    legacy = repo_root() / "CSV files" / "505039_Ella_Executive_Search_files_1" / "resumes"
    return legacy if legacy.exists() else candidates[0]


def dataset_paths() -> Tuple[Path, Path, Path]:
    """Convenience helper returning `(root, csv_dir, resumes_dir)` in one call."""
    root = dataset_root()
    return root, csv_dir(), resumes_dir()
