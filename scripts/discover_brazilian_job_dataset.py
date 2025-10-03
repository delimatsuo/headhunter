#!/usr/bin/env python3
"""
Discover Brazilian job postings dataset in GCS and validate sample records.

Checks the following prefixes, based on PROJECT_ID/GOOGLE_CLOUD_PROJECT and the
fixed "operations" bucket used by CloudStoragePipeline:
 - gs://{PROJECT_ID}-eco-raw/job_postings/
 - gs://headhunter-ai-0088-eco-raw/job_postings/

Outputs a machine-readable JSON report to stdout and writes to
 `scripts/reports/discover_brazilian_job_dataset.json`.

Required fields validated in sample: job_title, normalized_title, source_url

If google-cloud-storage is unavailable, emits a report with ok=false for the
GCS section but continues to probe other sources (Firestore, local files) and
returns a combined status. Missing SDKs are recorded with ok=false + error per
source; behavior remains idempotent.
"""
from __future__ import annotations

import json
import os
import random
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


REPORT_PATH = os.getenv(
    "ECO_DATASET_DISCOVERY_REPORT",
    "scripts/reports/discover_brazilian_job_dataset.json",
)

REMEDIATION_COMMANDS = [
    "pip install google-cloud-storage",
    "gsutil mb gs://$PROJECT_ID-eco-raw",
    "python scripts/generate_sample_brazilian_job_dataset.py",
    "python scripts/orchestrate_eco_collection.py",
]


@dataclass
class BucketSummary:
    bucket: str
    prefix: str
    ok: bool
    total_objects: int
    date_prefixes: List[str]
    spiders: List[str]
    date_range: Optional[List[str]]
    samples_checked: int
    sample_errors: List[str]


def _client():
    try:
        from google.cloud import storage  # type: ignore
    except Exception as e:  # pragma: no cover
        return None, e
    return storage.Client(project=os.getenv("PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")), None


def _list_prefixes_and_spiders(client, bucket_name: str) -> Dict[str, Any]:
    bucket = client.bucket(bucket_name)
    if not bucket.exists():
        return {"ok": False, "error": f"Bucket {bucket_name} does not exist"}
    # List top-level date prefixes under job_postings/
    iterator = client.list_blobs(bucket_name, prefix="job_postings/", delimiter="/")
    dates: List[str] = []
    spiders: set[str] = set()
    total_objects = 0
    for page in iterator.pages:
        for p in (page.prefixes or []):
            # Expect job_postings/YYYYMMDD/
            parts = p.strip("/").split("/")
            if len(parts) == 2 and parts[1].isdigit():
                dates.append(parts[1])
        # Accumulate total object count
        total_objects += sum(1 for _ in page)
    dates = sorted(set(dates))

    # Derive spiders from a small sample of blobs
    sample_dates = random.sample(dates, k=min(3, len(dates))) if dates else []
    for d in sample_dates:
        for blob in client.list_blobs(bucket_name, prefix=f"job_postings/{d}/", delimiter="/"):
            name = getattr(blob, "name", "")
            if name.endswith(".jsonl"):
                # job_postings/YYYYMMDD/<spider>/file.jsonl or job_postings/YYYYMMDD/<file>.jsonl
                parts = name.split("/")
                if len(parts) >= 4:
                    spiders.add(parts[2])
    date_range = [dates[0], dates[-1]] if dates else None
    return {
        "ok": True,
        "dates": dates,
        "spiders": sorted(list(spiders)),
        "total_objects": total_objects,
        "date_range": date_range,
    }


def _validate_samples(client, bucket_name: str, max_lines: int = 20) -> Dict[str, Any]:
    # Pull a few small JSONL files and validate required fields
    required = ["job_title", "normalized_title", "source_url"]
    errors: List[str] = []
    checked = 0
    for blob in client.list_blobs(bucket_name, prefix="job_postings/"):
        if not blob.name.endswith(".jsonl"):
            continue
        try:
            data = blob.download_as_text(encoding="utf-8")
        except Exception as e:
            errors.append(f"Failed to download {blob.name}: {e}")
            continue
        lines = [ln for ln in data.splitlines() if ln.strip()][:max_lines]
        for ln in lines:
            try:
                obj = json.loads(ln)
            except Exception:
                errors.append(f"Invalid JSON in {blob.name}")
                continue
            for f in required:
                if not obj.get(f):
                    errors.append(f"Missing required field {f} in {blob.name}")
            checked += 1
        if checked >= max_lines:
            break
    return {"checked": checked, "errors": errors}


def main() -> int:
    client, err = _client()

    proj = os.getenv("PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    dynamic_bucket = f"{proj}-eco-raw" if proj else None
    buckets = []
    if dynamic_bucket:
        buckets.append(dynamic_bucket)
    buckets.append("headhunter-ai-0088-eco-raw")

    summaries: List[Dict[str, Any]] = []
    warnings: List[str] = []
    overall_ok = True
    if client is None:
        warnings.append(f"google-cloud-storage not available: {err}")
        summaries.append({
            "bucket": buckets[0] if buckets else None,
            "prefix": "job_postings/",
            "ok": False,
            "total_objects": 0,
            "date_prefixes": [],
            "spiders": [],
            "date_range": None,
            "samples_checked": 0,
            "sample_errors": [f"google-cloud-storage not available: {err}"],
        })
        overall_ok = False
    else:
        for b in buckets:
            info = _list_prefixes_and_spiders(client, b)
            if not info.get("ok"):
                summaries.append(
                    {
                        "bucket": b,
                        "prefix": "job_postings/",
                        "ok": False,
                        "total_objects": 0,
                        "date_prefixes": [],
                        "spiders": [],
                        "date_range": None,
                        "samples_checked": 0,
                        "sample_errors": [info.get("error", "unknown error")],
                    }
                )
                overall_ok = False
                continue
            sample = _validate_samples(client, b)
            if sample["errors"]:
                overall_ok = False
            summaries.append(
                {
                    "bucket": b,
                    "prefix": "job_postings/",
                    "ok": not sample["errors"],
                    "total_objects": info.get("total_objects", 0),
                    "date_prefixes": info.get("dates", []),
                    "spiders": info.get("spiders", []),
                    "date_range": info.get("date_range"),
                    "samples_checked": sample["checked"],
                    "sample_errors": sample["errors"],
                }
            )

    # Firestore source (optional)
    firestore_section: Dict[str, Any]
    try:
        from google.cloud import firestore  # type: ignore
        fs_project = os.getenv("PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
        if fs_project:
            fs_client = firestore.Client(project=fs_project)
        else:
            fs_client = firestore.Client()
        coll = fs_client.collection("job_postings")
        # Count and sample
        # Firestore aggregation count API may not be available in all envs; fallback to limited fetch
        docs = list(coll.limit(50).stream())
        count_approx = len(docs)
        # Timestamps and field validation
        required = ["job_title", "normalized_title", "source_url"]
        errors: List[str] = []
        recent_ts: List[str] = []
        for d in docs[:10]:
            data = d.to_dict() or {}
            for f in required:
                if not data.get(f):
                    errors.append(f"Missing {f} in doc {d.id}")
            ts = data.get("created_at") or data.get("timestamp") or data.get("updated_at")
            if ts:
                try:
                    # Support both datetime and string
                    if hasattr(ts, "isoformat"):
                        recent_ts.append(ts.isoformat())
                    else:
                        recent_ts.append(str(ts))
                except Exception:
                    recent_ts.append(str(ts))
        firestore_section = {
            "ok": len(errors) == 0 and count_approx >= 0,
            "project": fs_project,
            "collection": "job_postings",
            "docs_sampled": len(docs),
            "approx_count": count_approx,
            "recent_timestamps": recent_ts[:5],
            "errors": errors,
        }
        overall_ok = overall_ok and firestore_section["ok"]
    except Exception as e:
        message = f"firestore not available: {e}"
        warnings.append(message)
        firestore_section = {"ok": False, "error": message, "collection": "job_postings"}
        overall_ok = False

    # Local files source (always check)
    import glob
    required = ["job_title", "normalized_title", "source_url"]
    local_patterns = [
        os.path.join("eco_raw", "*", "*.jsonl"),          # eco_raw/YYYYMMDD/*.jsonl
        os.path.join("eco_raw", "*", "*", "*.jsonl"),     # eco_raw/YYYYMMDD/spider/*.jsonl
    ]
    local_files = []
    for pat in local_patterns:
        local_files.extend(glob.glob(pat))
    local_errors: List[str] = []
    checked = 0
    for path in sorted(local_files)[:5]:
        try:
            with open(path, encoding="utf-8") as f:
                for i, ln in enumerate(f):
                    if i >= 10:
                        break
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        obj = json.loads(ln)
                    except Exception:
                        local_errors.append(f"Invalid JSON in {path}")
                        continue
                    for fkey in required:
                        if not obj.get(fkey):
                            local_errors.append(f"Missing {fkey} in {path}")
                    checked += 1
        except Exception as e:
            local_errors.append(f"Failed to read {path}: {e}")
    local_section = {
        "ok": len(local_errors) == 0 and checked >= 0,
        "checked_lines": checked,
        "files_considered": len(local_files),
        "errors": local_errors,
    }
    overall_ok = overall_ok and local_section["ok"]

    valid_samples = any(
        summary.get("samples_checked", 0) > 0 and not summary.get("sample_errors")
        for summary in summaries
    )

    report = {
        "ok": overall_ok,
        "generated_at": int(datetime.utcnow().timestamp()),
        "buckets": summaries,
        "firestore": firestore_section,
        "local_files": local_section,
        "warnings": warnings,
    }
    if client is None or not valid_samples:
        report["action_required"] = REMEDIATION_COMMANDS.copy()
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if overall_ok else 2


if __name__ == "__main__":
    sys.exit(main())
