"""Brazilian job data loader for clustering pipeline.

This module ingests job posting datasets from multiple sources, normalizes
Brazilian Portuguese job titles, deduplicates them while preserving
frequency and metadata, and emits datasets ready for the embedding and
clustering pipeline stages.
"""

from __future__ import annotations

import csv
import json
import logging
import statistics
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional, Sequence

import importlib

logger = logging.getLogger(__name__)


def _ensure_logger_configured() -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")


def _load_normalizer() -> Any:
    module = importlib.import_module("scripts.eco_title_normalizer")
    if hasattr(module, "EcoTitleNormalizer"):
        return module.EcoTitleNormalizer()
    if hasattr(module, "BrazilianPortugueseNormalizer"):
        return module.BrazilianPortugueseNormalizer()
    if hasattr(module, "normalize_title"):
        return module
    raise AttributeError("Expected Eco title normalizer implementation not found")


@dataclass
class DataLoaderConfig:
    sources: Sequence[Path]
    output_path: Path
    incremental: bool = True
    min_frequency: int = 1
    allowed_sources: Optional[Sequence[str]] = None
    max_records: Optional[int] = None
    parallelism: int = 1


@dataclass
class TitleRecord:
    title: str
    normalized_title: str
    source: str
    company: Optional[str]
    location: Optional[str]
    posted_at: Optional[datetime]
    metadata: Dict[str, Any] = field(default_factory=dict)


class BrazilianJobDataLoader:
    """Loads and cleans Brazilian job posting titles for clustering."""

    def __init__(self, config: DataLoaderConfig) -> None:
        _ensure_logger_configured()
        self.config = config
        self.normalizer = _load_normalizer()
        self._existing_titles: MutableMapping[str, Dict[str, Any]] = {}
        self._stats: Dict[str, Any] = {
            "sources_processed": len(self.config.sources),
            "invalid_titles": 0,
            "dropped_low_frequency": 0,
            "existing_titles": 0,
        }
        if self.config.incremental:
            self._load_existing_titles()
        logger.debug("Initialized BrazilianJobDataLoader with config %s", config)

    def load(self) -> Dict[str, Any]:
        """Run the full data loading process and persist outputs."""
        logger.info("Starting Brazilian job data loading pipeline")
        aggregated_records = list(self._iter_records())
        logger.info("Loaded %d raw records", len(aggregated_records))
        deduped = self._deduplicate(aggregated_records)
        logger.info("Deduplicated down to %d unique normalized titles", len(deduped))
        merged = self._merge_with_existing(deduped)
        logger.info("Merged deduplicated titles with %d existing normalized titles", self._stats.get("existing_titles", 0))
        filtered: Dict[str, Dict[str, Any]] = {}
        for normalized, entry in merged.items():
            if entry["frequency"] < self.config.min_frequency:
                self._stats["dropped_low_frequency"] += 1
                continue
            filtered[normalized] = entry
        logger.info("Filtered to %d titles after applying min_frequency >= %d", len(filtered), self.config.min_frequency)
        metrics = self._compute_metrics(filtered)
        payload = {
            "titles": filtered,
            "metrics": metrics,
            "generated_at": datetime.utcnow().isoformat(),
            "quality": self._stats,
        }
        self._write_output(payload)
        logger.info("Brazilian job data loading pipeline finished")
        return payload

    def _iter_records(self) -> Iterator[TitleRecord]:
        count = 0
        sources = list(self.config.sources)
        if self.config.parallelism > 1 and len(sources) > 1:
            logger.info("Loading %d sources with parallelism=%d", len(sources), self.config.parallelism)
            with ThreadPoolExecutor(max_workers=self.config.parallelism) as executor:
                future_map = {executor.submit(self._consume_source, source_path): source_path for source_path in sources}
                for future in as_completed(future_map):
                    for record in future.result():
                        if self.config.max_records is not None and count >= self.config.max_records:
                            logger.info("Reached max_records=%d; stopping early", self.config.max_records)
                            return
                        count += 1
                        yield record
        else:
            for source_path in sources:
                for record in self._consume_source(source_path):
                    if self.config.max_records is not None and count >= self.config.max_records:
                        logger.info("Reached max_records=%d; stopping early", self.config.max_records)
                        return
                    count += 1
                    yield record

    def _consume_source(self, source_path: Path) -> List[TitleRecord]:
        if not source_path.exists():
            logger.warning("Data source %s does not exist; skipping", source_path)
            return []
        loader = self._loader_for_path(source_path)
        return list(loader(source_path))

    def _loader_for_path(self, path: Path):  # type: ignore[no-untyped-def]
        if path.suffix.lower() == ".jsonl":
            return self._load_jsonl
        if path.suffix.lower() == ".json":
            return self._load_json
        if path.suffix.lower() == ".csv":
            return self._load_csv
        raise ValueError(f"Unsupported file format: {path}")

    def _normalize(self, title: str) -> str:
        if hasattr(self.normalizer, "normalize"):
            return self.normalizer.normalize(title)
        if hasattr(self.normalizer, "normalize_title"):
            return self.normalizer.normalize_title(title)
        if hasattr(self.normalizer, "__call__"):
            return self.normalizer(title)
        raise AttributeError("Normalizer does not expose a callable normalization API")

    def _build_record(self, raw: Mapping[str, Any], source: str) -> Optional[TitleRecord]:
        title = (raw.get("title") or raw.get("job_title") or "").strip()
        if not title:
            self._stats["invalid_titles"] += 1
            return None
        normalized = self._normalize(title)
        company = raw.get("company") or raw.get("employer")
        location = raw.get("location") or raw.get("city")
        posted_at_raw = raw.get("posted_at") or raw.get("date")
        posted_at = None
        if posted_at_raw:
            try:
                posted_at = datetime.fromisoformat(str(posted_at_raw).replace("Z", "+00:00"))
            except ValueError:
                posted_at = None
        metadata = {
            "raw_title": title,
            "source": source,
            "extras": {
                k: v for k, v in raw.items() if k not in {"title", "job_title", "company", "employer", "location", "city", "posted_at", "date"}
            },
        }
        return TitleRecord(
            title=title,
            normalized_title=normalized,
            source=source,
            company=str(company) if company else None,
            location=str(location) if location else None,
            posted_at=posted_at,
            metadata=metadata,
        )

    def _load_jsonl(self, path: Path) -> Iterator[TitleRecord]:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug("Skipping malformed JSON line in %s", path)
                    continue
                record = self._build_record(payload, source=path.stem)
                if record:
                    yield record

    def _load_json(self, path: Path) -> Iterator[TitleRecord]:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, Mapping):
            payload_iter = payload.get("items") or payload.get("data") or []
        else:
            payload_iter = payload
        for entry in payload_iter:
            if not isinstance(entry, Mapping):
                continue
            record = self._build_record(entry, source=path.stem)
            if record:
                yield record

    def _load_csv(self, path: Path) -> Iterator[TitleRecord]:
        with path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                record = self._build_record(row, source=path.stem)
                if record:
                    yield record

    def _deduplicate(self, records: Iterable[TitleRecord]) -> Dict[str, Dict[str, Any]]:
        aggregated: Dict[str, Dict[str, Any]] = {}
        for record in records:
            if self.config.allowed_sources and record.source not in self.config.allowed_sources:
                continue
            entry = aggregated.setdefault(
                record.normalized_title,
                {
                    "normalized_title": record.normalized_title,
                    "canonical_title": record.title,
                    "sources": Counter(),
                    "frequency": 0,
                    "companies": Counter(),
                    "locations": Counter(),
                    "earliest_posting": record.posted_at,
                    "latest_posting": record.posted_at,
                    "examples": [],
                },
            )
            entry["frequency"] += 1
            entry["sources"][record.source] += 1
            if record.company:
                entry["companies"][record.company] += 1
            if record.location:
                entry["locations"][record.location] += 1
            if record.posted_at:
                entry["earliest_posting"] = min(filter(None, [entry["earliest_posting"], record.posted_at]))
                entry["latest_posting"] = max(filter(None, [entry["latest_posting"], record.posted_at]))
            if len(entry["examples"]) < 5:
                entry["examples"].append(record.metadata)
        return aggregated

    def _merge_with_existing(self, new_records: Mapping[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        if not self._existing_titles:
            return dict(new_records)
        merged: Dict[str, Dict[str, Any]] = {}
        for normalized, entry in self._existing_titles.items():
            merged[normalized] = {
                "normalized_title": normalized,
                "canonical_title": entry.get("canonical_title", normalized),
                "sources": Counter(entry.get("sources", {})),
                "frequency": entry.get("frequency", 0),
                "companies": Counter(entry.get("companies", {})),
                "locations": Counter(entry.get("locations", {})),
                "earliest_posting": self._parse_datetime(entry.get("earliest_posting")),
                "latest_posting": self._parse_datetime(entry.get("latest_posting")),
                "examples": entry.get("examples", [])[:10],
            }
        self._stats["existing_titles"] = len(merged)
        for normalized, entry in new_records.items():
            target = merged.setdefault(
                normalized,
                {
                    "normalized_title": normalized,
                    "canonical_title": entry.get("canonical_title", normalized),
                    "sources": Counter(),
                    "frequency": 0,
                    "companies": Counter(),
                    "locations": Counter(),
                    "earliest_posting": entry.get("earliest_posting"),
                    "latest_posting": entry.get("latest_posting"),
                    "examples": [],
                },
            )
            target["frequency"] += entry.get("frequency", 0)
            target["sources"].update(entry.get("sources", {}))
            target["companies"].update(entry.get("companies", {}))
            target["locations"].update(entry.get("locations", {}))
            target["earliest_posting"] = self._min_datetime(target.get("earliest_posting"), entry.get("earliest_posting"))
            target["latest_posting"] = self._max_datetime(target.get("latest_posting"), entry.get("latest_posting"))
            examples = target.setdefault("examples", [])
            for example in entry.get("examples", []):
                if example not in examples and len(examples) < 10:
                    examples.append(example)
        return merged

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    @staticmethod
    def _min_datetime(current: Optional[datetime], candidate: Optional[datetime]) -> Optional[datetime]:
        if current and candidate:
            return min(current, candidate)
        return candidate or current

    @staticmethod
    def _max_datetime(current: Optional[datetime], candidate: Optional[datetime]) -> Optional[datetime]:
        if current and candidate:
            return max(current, candidate)
        return candidate or current

    def _compute_metrics(self, data: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
        frequencies = [entry["frequency"] for entry in data.values()]
        if not frequencies:
            return {"total_titles": 0, "mean_frequency": 0, "median_frequency": 0, "p95_frequency": 0}
        return {
            "total_titles": len(frequencies),
            "mean_frequency": statistics.fmean(frequencies),
            "median_frequency": statistics.median(frequencies),
            "p95_frequency": statistics.quantiles(frequencies, n=100)[94] if len(frequencies) >= 20 else max(frequencies),
        }

    def _write_output(self, payload: Mapping[str, Any]) -> None:
        self.config.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config.output_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=self._json_default)
        logger.info("Wrote cleaned data to %s", self.config.output_path)

    @staticmethod
    def _json_default(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Counter):
            return dict(value)
        return value

    def _load_existing_titles(self) -> None:
        if not self.config.output_path.exists():
            return
        try:
            with self.config.output_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (json.JSONDecodeError, OSError):
            logger.warning("Unable to load existing dataset from %s; proceeding without incremental merge", self.config.output_path)
            return
        titles = payload.get("titles") if isinstance(payload, Mapping) else None
        if not isinstance(titles, Mapping):
            return
        for normalized, entry in titles.items():
            if isinstance(entry, Mapping):
                self._existing_titles[normalized] = dict(entry)


def load_from_sources(sources: Sequence[str], output_path: str, **kwargs: Any) -> Dict[str, Any]:
    config = DataLoaderConfig(
        sources=[Path(src) for src in sources],
        output_path=Path(output_path),
        incremental=kwargs.get("incremental", True),
        min_frequency=kwargs.get("min_frequency", 1),
        allowed_sources=kwargs.get("allowed_sources"),
        max_records=kwargs.get("max_records"),
        parallelism=kwargs.get("parallelism", 1),
    )
    loader = BrazilianJobDataLoader(config)
    return loader.load()


def _parse_args(argv: Optional[Sequence[str]] = None) -> Any:
    import argparse

    parser = argparse.ArgumentParser(description="Load Brazilian job postings into normalized title dataset")
    parser.add_argument("sources", nargs="+", help="Paths to JSONL/JSON/CSV datasets")
    parser.add_argument("--output", required=True, help="Path to write normalized dataset JSON")
    parser.add_argument("--min-frequency", type=int, default=1, help="Minimum frequency for titles to be kept")
    parser.add_argument("--max-records", type=int, help="Limit number of records processed")
    parser.add_argument("--allow-source", dest="allowed_sources", action="append", help="Whitelist of allowed source names")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = _parse_args(argv)
    load_from_sources(
        sources=args.sources,
        output_path=args.output,
        min_frequency=args.min_frequency,
        max_records=args.max_records,
        allowed_sources=args.allowed_sources,
    )


if __name__ == "__main__":
    main()
