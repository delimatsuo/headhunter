import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from scrapy.exceptions import DropItem  # type: ignore


class TitleNormalizationPipeline:
    def open_spider(self, spider):  # noqa: D401
        try:
            from scripts.eco_title_normalizer import normalize_title_ptbr  # type: ignore
            self._normalize = normalize_title_ptbr
        except Exception:
            # Fallback to simple normalization defined in BaseEcoSpider
            self._normalize = None

    def process_item(self, item: Dict[str, Any], spider):  # noqa: D401
        if self._normalize and item.get("job_title"):
            item["normalized_title"] = self._normalize(item["job_title"])  # type: ignore
        return item


class JsonlWriterPipeline:
    def open_spider(self, spider):  # noqa: D401
        date = datetime.utcnow().strftime("%Y%m%d")
        out_dir = os.environ.get("ECO_OUTPUT_DIR", f"eco_raw/{date}")
        os.makedirs(out_dir, exist_ok=True)
        self.file_path = os.path.join(out_dir, f"{spider.name}.jsonl")
        self.f = open(self.file_path, "a", encoding="utf-8")
        # expose path to other pipelines (e.g., GCS uploader)
        setattr(spider, "crawled_file_path", self.file_path)

    def close_spider(self, spider):  # noqa: D401
        if getattr(self, "f", None):
            self.f.close()

    def process_item(self, item: Dict[str, Any], spider):  # noqa: D401
        line = json.dumps(item, ensure_ascii=False)
        self.f.write(line + "\n")
        # increment stats
        try:
            spider.crawler.stats.inc_value("eco/items_written")
        except Exception:
            pass
        return item


class DedupPipeline:
    """Deduplicate items by source_url (or full JSON) within a crawl run."""

    def __init__(self) -> None:
        self._seen: Set[str] = set()

    def process_item(self, item: Dict[str, Any], spider):  # noqa: D401
        key = item.get("source_url") or json.dumps(item, sort_keys=True)
        if key in self._seen:
            try:
                spider.crawler.stats.inc_value("eco/duplicates")
            except Exception:
                pass
            raise DropItem("Duplicate item detected")
        self._seen.add(key)
        return item


class GcsWriterPipeline:
    """Upload resulting JSONL to GCS path gs://{PROJECT_ID}-eco-raw/job_postings/YYYYMMDD/"""

    def close_spider(self, spider):  # noqa: D401
        file_path = getattr(spider, "crawled_file_path", None)
        if not file_path:
            return
        project_id = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            spider.logger.warning("GCS upload skipped: PROJECT_ID/GOOGLE_CLOUD_PROJECT not set")
            return
        try:
            from google.cloud import storage  # type: ignore
        except Exception:
            spider.logger.warning("GCS upload skipped: google-cloud-storage not installed")
            return

        client = storage.Client(project=project_id)
        bucket_name = f"{project_id}-eco-raw"
        bucket = client.bucket(bucket_name)
        if not bucket.exists():
            spider.logger.warning("GCS bucket %s does not exist; skipping upload", bucket_name)
            return
        date = datetime.utcnow().strftime("%Y%m%d")
        blob_path = f"job_postings/{date}/{os.path.basename(file_path)}"
        blob = bucket.blob(blob_path)
        blob.upload_from_filename(file_path, content_type="application/x-ndjson")
        try:
            spider.crawler.stats.inc_value("eco/gcs_uploaded_files")
        except Exception:
            pass


class ValidationPipeline:
    """Basic validation and cleaning for scraped items."""

    REQUIRED_FIELDS = ["job_title", "normalized_title", "source_url"]

    def process_item(self, item: Dict[str, Any], spider):  # noqa: D401
        for f in self.REQUIRED_FIELDS:
            if not item.get(f):
                raise DropItem(f"Missing required field: {f}")
        # Length checks
        if len(item["normalized_title"]) < 2:
            raise DropItem("Normalized title too short")
        # Trim fields
        for k in ["job_title", "normalized_title", "company", "location"]:
            if item.get(k) and isinstance(item[k], str):
                item[k] = item[k].strip()
        return item


class AliasDedupPipeline:
    """Deduplicate by (normalized_title, company)."""

    def __init__(self) -> None:
        self._pairs: Set[str] = set()

    def process_item(self, item: Dict[str, Any], spider):  # noqa: D401
        norm = item.get("normalized_title")
        comp = item.get("company") or ""
        key = f"{norm}||{comp}"
        if key in self._pairs:
            try:
                spider.crawler.stats.inc_value("eco/alias_dupes")
            except Exception:
                pass
            raise DropItem("Duplicate normalized/company pair")
        self._pairs.add(key)
        return item


class CloudStoragePipeline:
    """
    Batch writer that rotates local JSONL files and uploads them to a fixed
    GCS path: gs://headhunter-ai-0088-eco-raw/job_postings/YYYYMMDD/{spider}/{batch_N}.jsonl
    """

    def __init__(self, batch_size: int = 1000, max_batch_bytes: int = 5_000_000):
        self.batch_size = batch_size
        self.max_batch_bytes = max_batch_bytes
        self._buffer: List[str] = []
        self._buffer_bytes = 0
        self._batch_index = 0
        self._out_dir: Optional[str] = None

    @classmethod
    def from_crawler(cls, crawler):  # noqa: D401
        return cls(
            batch_size=int(crawler.settings.getint("ECO_BATCH_SIZE", 1000)),
            max_batch_bytes=int(crawler.settings.getint("ECO_MAX_BATCH_BYTES", 5_000_000)),
        )

    def open_spider(self, spider):  # noqa: D401
        date = datetime.utcnow().strftime("%Y%m%d")
        self._out_dir = os.environ.get("ECO_OUTPUT_DIR", f"eco_raw/{date}/{spider.name}")
        os.makedirs(self._out_dir, exist_ok=True)
        self._buffer.clear()
        self._buffer_bytes = 0
        self._batch_index = 0

    def _flush_batch(self, spider):
        if not self._buffer or not self._out_dir:
            return
        file_path = os.path.join(self._out_dir, f"batch_{self._batch_index}.jsonl")
        with open(file_path, "w", encoding="utf-8") as f:
            for line in self._buffer:
                f.write(line + "\n")

        self._buffer.clear()
        self._buffer_bytes = 0
        self._batch_index += 1

        # Upload to fixed bucket name per plan
        try:
            from google.cloud import storage  # type: ignore
        except Exception:
            spider.logger.warning("Cloud upload skipped (google-cloud-storage not installed)")
            return

        bucket_name = "headhunter-ai-0088-eco-raw"
        client = storage.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT"))
        bucket = client.bucket(bucket_name)
        blob_path = f"job_postings/{os.path.basename(os.path.dirname(self._out_dir))}/{spider.name}/{os.path.basename(file_path)}"
        blob = bucket.blob(blob_path)

        # Retry upload
        for attempt in range(3):
            try:
                blob.upload_from_filename(file_path, content_type="application/x-ndjson")
                try:
                    spider.crawler.stats.inc_value("eco/cloud_batches_uploaded")
                except Exception:
                    pass
                break
            except Exception as e:
                spider.logger.warning("Upload failed (%s), attempt %s/3", e, attempt + 1)
                time.sleep(2 * (attempt + 1))

    def close_spider(self, spider):  # noqa: D401
        self._flush_batch(spider)

    def process_item(self, item: Dict[str, Any], spider):  # noqa: D401
        line = json.dumps(item, ensure_ascii=False)
        self._buffer.append(line)
        self._buffer_bytes += len(line) + 1
        if len(self._buffer) >= self.batch_size or self._buffer_bytes >= self.max_batch_bytes:
            self._flush_batch(spider)
        return item
