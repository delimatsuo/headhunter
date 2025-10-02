#!/usr/bin/env python3
"""
Generate a small sample of Brazilian job postings in JSONL format.

Titles are realistic pt-BR and normalized via scripts/eco_title_normalizer.py.
Output layout mirrors eco_scraper pipelines:
 - Local: eco_raw/YYYYMMDD/<spider>/batch_*.jsonl (CloudStoragePipeline-like)

Optionally uploads to GCS if GOOGLE_CLOUD_PROJECT/PROJECT_ID and
google-cloud-storage are available.

Emits JSON report to stdout and scripts/reports/sample_dataset_generated.json.
"""
from __future__ import annotations

import json
import os
import random
import sys
from datetime import datetime
from typing import Any, Dict, List

try:
    from scripts.eco_title_normalizer import normalize_title_ptbr  # type: ignore
except Exception:
    def normalize_title_ptbr(s: str) -> str:  # type: ignore
        return (s or "").strip().lower()


REPORT_PATH = os.getenv("ECO_SAMPLE_GEN_REPORT", "scripts/reports/sample_dataset_generated.json")


TITLES = [
    "Desenvolvedor(a) Front-end", "Engenheiro(a) de Dados", "Analista de BI Júnior",
    "Dev Sr. Backend Python", "Arquiteto(a) de Software", "Cientista de Dados Pleno",
]
SPIDERS = ["vagas", "infojobs", "catho", "indeed_br"]


def maybe_upload_gcs(local_path: str, spider: str, date: str) -> Dict[str, Any]:
    project_id = os.getenv("PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        return {"uploaded": False, "reason": "PROJECT_ID/GOOGLE_CLOUD_PROJECT not set"}
    try:
        from google.cloud import storage  # type: ignore
    except Exception:
        return {"uploaded": False, "reason": "google-cloud-storage not installed"}

    bucket_name = f"{project_id}-eco-raw"
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    if not bucket.exists():
        return {"uploaded": False, "reason": f"bucket {bucket_name} does not exist"}
    blob_path = f"job_postings/{date}/{spider}/{os.path.basename(local_path)}"
    blob = bucket.blob(blob_path)
    blob.upload_from_filename(local_path, content_type="application/x-ndjson")
    return {"uploaded": True, "bucket": bucket_name, "path": blob_path}


def main() -> int:
    date = datetime.utcnow().strftime("%Y%m%d")
    base_dir = os.getenv("ECO_OUTPUT_DIR", f"eco_raw/{date}")
    os.makedirs(base_dir, exist_ok=True)

    total = 0
    outputs: List[Dict[str, Any]] = []
    for sp in SPIDERS:
        out_dir = os.path.join(base_dir, sp)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "batch_0.jsonl")
        with open(out_path, "w", encoding="utf-8") as f:
            n = random.randint(5, 10)
            for _ in range(n):
                title = random.choice(TITLES)
                norm = normalize_title_ptbr(title)
                obj = {
                    "job_title": title,
                    "normalized_title": norm,
                    "company": random.choice(["ACME", "Globex", "Initech", "Umbrella"]),
                    "location": random.choice(["São Paulo", "Rio de Janeiro", "Belo Horizonte", "Curitiba"]),
                    "source_url": f"https://example.com/{sp}/{random.randint(10000,99999)}",
                    "spider": sp,
                    "date": date,
                }
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
                total += 1
        upload = maybe_upload_gcs(out_path, sp, date)
        outputs.append({"spider": sp, "local_path": out_path, **upload})

    report = {"ok": True, "generated": total, "outputs": outputs}
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

