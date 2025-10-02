#!/usr/bin/env python3
"""
Validate data collection infrastructure:
 - Import Scrapy settings and pipelines
 - Dry-run pipelines with a fake item
 - Exercise GCS uploader in dry-run (requires google-cloud-storage)

Emits JSON to stdout and scripts/reports/data_collection_validation.json.
"""
from __future__ import annotations

import json
import os
import tempfile
import sys
from typing import Any, Dict


REPORT_PATH = os.getenv("ECO_DATA_COLLECTION_VALIDATION_REPORT", "scripts/reports/data_collection_validation.json")


class _FakeStats:
    def inc_value(self, *_args, **_kwargs):
        return None


class _FakeCrawler:
    def __init__(self):
        self.stats = _FakeStats()


class _FakeSpider:
    name = "test_spider"
    crawler = _FakeCrawler()

    class logger:
        @staticmethod
        def warning(*args, **kwargs):
            return None


def main() -> int:
    checks: list[Dict[str, Any]] = []
    ok = True
    try:
        from scripts.eco_scraper import pipelines  # type: ignore
        from scripts.eco_scraper import settings as _settings  # type: ignore
        checks.append({"name": "import_scrapy_modules", "ok": True})
    except Exception as e:
        checks.append({"name": "import_scrapy_modules", "ok": False, "error": str(e)})
        ok = False
        report = {"ok": ok, "checks": checks}
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(json.dumps(report, indent=2))
        return 2

    # Validate pipelines with a fake item
    spider = _FakeSpider()
    item = {
        "job_title": "Dev Sr. Backend Python",
        "normalized_title": "dev sr backend python",
        "source_url": "https://example.com/job/123",
        "company": "ACME",
        "location": "São Paulo",
    }

    try:
        v = pipelines.ValidationPipeline()
        v.process_item(dict(item), spider)
        checks.append({"name": "validation_pipeline", "ok": True})
    except Exception as e:
        checks.append({"name": "validation_pipeline", "ok": False, "error": str(e)})
        ok = False

    # Test JsonlWriterPipeline and GcsWriterPipeline close
    try:
        j = pipelines.JsonlWriterPipeline()
        with tempfile.TemporaryDirectory() as d:
            os.environ["ECO_OUTPUT_DIR"] = d
            j.open_spider(spider)
            j.process_item(dict(item), spider)
            j.close_spider(spider)
            checks.append({"name": "jsonl_writer_pipeline", "ok": True, "file_path": getattr(spider, "crawled_file_path", None)})
            g = pipelines.GcsWriterPipeline()
            g.close_spider(spider)
            checks.append({"name": "gcs_writer_pipeline", "ok": True})
    except Exception as e:
        checks.append({"name": "jsonl/gcs_pipeline", "ok": False, "error": str(e)})
        ok = False

    report = {"ok": ok, "checks": checks}
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())

