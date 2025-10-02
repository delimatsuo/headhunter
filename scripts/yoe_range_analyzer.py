"""Years of Experience analyzer for Brazilian ECO occupations."""

from __future__ import annotations

import json
import logging
import math
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

CAREER_LEVEL_KEYWORDS = {
    "estagio": (0.0, 1.0),
    "j[úu]nior": (1.0, 3.0),
    "junior": (1.0, 3.0),
    "pleno": (3.0, 6.0),
    "s[êe]nior": (6.0, 12.0),
    "tech lead": (8.0, 14.0),
    "especialista": (8.0, 14.0),
    "coordenador": (8.0, 15.0),
    "gerente": (10.0, 18.0),
}

EXPERIENCE_PATTERNS = [
    re.compile(r"(?P<min>\d+)\s*(?:a|até|-|\/)\s*(?P<max>\d+)\s*anos", re.IGNORECASE),
    re.compile(r"no\s+m[ií]nimo\s*(?P<min_only>\d+)\s*anos", re.IGNORECASE),
    re.compile(r"at[ée]\s*(?P<max_only>\d+)\s*anos", re.IGNORECASE),
    re.compile(r"(?P<exact_plus>\d+)\s*\+\s*anos?", re.IGNORECASE),
    re.compile(r"(?P<exact>\d+)\s*anos(?:\s*de\s*experi[êe]ncia)?", re.IGNORECASE),
]

LEVEL_ALIAS = {
    "estágio": "estagio",
    "estagiário": "estagio",
    "jr": "junior",
    "sr": "senior",
}


@dataclass
class YoEAnalyzerConfig:
    input_paths: Sequence[Path]
    mapping_path: Optional[Path]
    output_path: Path
    occupation_field: str = "eco_occupation"
    job_text_field: str = "description"
    level_field: str = "title"
    min_records: int = 5
    limit: Optional[int] = None


@dataclass
class ExperienceObservation:
    occupation: str
    minimum: float
    maximum: float
    inferred_level: Optional[str]
    weight: float
    source: Optional[str] = None


@dataclass
class ExperienceAggregate:
    occupation: str
    values: List[float] = field(default_factory=list)
    level_samples: Dict[str, int] = field(default_factory=dict)
    weight_sum: float = 0.0
    weighted_total: float = 0.0
    postings: int = 0
    sources: Dict[str, int] = field(default_factory=dict)

    def register(self, observation: ExperienceObservation) -> None:
        min_years = max(0.0, observation.minimum)
        max_years = max(min_years, observation.maximum)
        midpoint = (min_years + max_years) / 2
        self.values.append(midpoint)
        self.weight_sum += observation.weight
        self.weighted_total += midpoint * observation.weight
        self.postings += 1
        if observation.inferred_level:
            key = observation.inferred_level
            self.level_samples[key] = self.level_samples.get(key, 0) + 1
        if observation.source:
            self.sources[observation.source] = self.sources.get(observation.source, 0) + 1

    def has_enough_data(self, min_records: int) -> bool:
        return self.postings >= min_records

    def summary(self) -> Dict[str, Any]:
        if not self.values:
            return {
                "min_years": None,
                "max_years": None,
                "p25": None,
                "p50": None,
                "p75": None,
                "mean": None,
                "confidence": 0.0,
                "postings": self.postings,
                "level_distribution": self.level_samples,
                "sources": self.sources,
            }
        trimmed = _remove_outliers(self.values)
        percentiles = _statistics_quantiles(trimmed)
        min_years = float(min(trimmed)) if trimmed else float(min(self.values))
        max_years = float(max(trimmed)) if trimmed else float(max(self.values))
        mean_years = self.weighted_total / self.weight_sum if self.weight_sum else statistics.mean(trimmed)
        confidence = min(1.0, math.log10(self.postings + 1) / 2)
        return {
            "min_years": round(min_years, 2),
            "max_years": round(max_years, 2),
            "p25": round(percentiles[0], 2) if percentiles[0] is not None else None,
            "p50": round(percentiles[1], 2) if percentiles[1] is not None else None,
            "p75": round(percentiles[2], 2) if percentiles[2] is not None else None,
            "mean": round(mean_years, 2),
            "confidence": round(confidence, 3),
            "postings": self.postings,
            "level_distribution": self.level_samples,
            "sources": self.sources,
        }


def _remove_outliers(values: Sequence[float]) -> List[float]:
    if len(values) < 4:
        return list(values)
    q1, q3 = statistics.quantiles(values, n=4)[0], statistics.quantiles(values, n=4)[2]
    iqr = q3 - q1
    lower = max(0.0, q1 - 1.5 * iqr)
    upper = q3 + 1.5 * iqr
    return [val for val in values if lower <= val <= upper]


def _statistics_quantiles(values: Sequence[float]) -> List[Optional[float]]:
    if not values:
        return [None, None, None]
    sorted_values = sorted(values)
    q1 = statistics.median(sorted_values[: len(sorted_values) // 2])
    median = statistics.median(sorted_values)
    q3 = statistics.median(sorted_values[(len(sorted_values) + 1) // 2 :])
    return [float(q1), float(median), float(q3)]


class PortugueseExperienceParser:
    """Extracts experience requirements from Portuguese job descriptions."""

    def parse(self, text: str) -> List[tuple[float, float]]:
        if not text:
            return []
        text = text.lower()
        results: List[tuple[float, float]] = []
        seen: set[tuple[float, float]] = set()
        for pattern in EXPERIENCE_PATTERNS:
            for match in pattern.finditer(text):
                if "min" in match.groupdict():
                    min_years = float(match.group("min"))
                    max_years = float(match.group("max"))
                    pair = (min_years, max_years)
                elif "min_only" in match.groupdict():
                    value = float(match.group("min_only"))
                    pair = (value, value)
                elif "max_only" in match.groupdict():
                    value = float(match.group("max_only"))
                    pair = (0.0, value)
                elif "exact_plus" in match.groupdict():
                    value = float(match.group("exact_plus"))
                    pair = (value, value + 2.0)
                elif "exact" in match.groupdict():
                    value = float(match.group("exact"))
                    pair = (value, value)
                else:
                    continue
                if pair not in seen:
                    seen.add(pair)
                    results.append(pair)
        if not results:
            level = self.detect_level(text)
            if level and level in CAREER_LEVEL_KEYWORDS:
                results.append(CAREER_LEVEL_KEYWORDS[level])
        return results

    def detect_level(self, text: str) -> Optional[str]:
        for keyword, range_tuple in CAREER_LEVEL_KEYWORDS.items():
            if re.search(keyword, text, re.IGNORECASE):
                return keyword
        for alias, canonical in LEVEL_ALIAS.items():
            if alias in text:
                return canonical
        return None


class YoERangeAnalyzer:
    """Computes YoE ranges per ECO occupation from scraped postings."""

    def __init__(self, config: YoEAnalyzerConfig) -> None:
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
        self.config = config
        self.parser = PortugueseExperienceParser()
        self.aggregates: Dict[str, ExperienceAggregate] = {}
        self.mapping: Dict[str, str] = self._load_mapping()

    def run(self) -> Dict[str, Any]:
        logger = logging.getLogger(__name__)
        logger.info("Starting YoE range analysis")
        self._consume_postings()
        payload: Dict[str, Any] = {}
        for occupation, aggregate in self.aggregates.items():
            if not aggregate.has_enough_data(self.config.min_records):
                continue
            payload[occupation] = aggregate.summary()
            payload[occupation]["occupation"] = occupation
        self.config.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config.output_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        logger.info("YoE analysis completed | occupations=%d", len(payload))
        return payload

    def _consume_postings(self) -> None:
        count = 0
        for posting in self._iter_postings():
            occupation = self._occupation_for_posting(posting)
            if not occupation:
                continue
            text = str(posting.get(self.config.job_text_field) or "")
            ranges = self.parser.parse(text)
            if not ranges:
                continue
            level_hint = self.parser.detect_level(text)
            weight = _weight_for_posting(posting)
            source = posting.get("source") or posting.get("origin")
            for min_years, max_years in ranges:
                observation = ExperienceObservation(
                    occupation=occupation,
                    minimum=min_years,
                    maximum=max_years,
                    inferred_level=level_hint,
                    weight=weight,
                    source=source,
                )
                self._aggregate(observation)
            count += 1
            if self.config.limit and count >= self.config.limit:
                break

    def _aggregate(self, observation: ExperienceObservation) -> None:
        agg = self.aggregates.setdefault(observation.occupation, ExperienceAggregate(observation.occupation))
        agg.register(observation)

    def _iter_postings(self) -> Iterable[Mapping[str, Any]]:
        for path in self.config.input_paths:
            if not path.exists():
                logging.getLogger(__name__).warning("YoE dataset missing: %s", path)
                continue
            if path.suffix.lower() == ".jsonl":
                with path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            continue
            elif path.suffix.lower() == ".json":
                with path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                    entries = payload if isinstance(payload, list) else payload.get("postings", [])
                    for entry in entries:
                        yield entry

    def _load_mapping(self) -> Dict[str, str]:
        if not self.config.mapping_path or not self.config.mapping_path.exists():
            return {}
        with self.config.mapping_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        mapping: Dict[str, str] = {}
        occupations = payload.get("occupations", [])
        for item in occupations:
            eco_id = item.get("eco_id") or item.get("occupation_id")
            normalized = item.get("normalized") or item.get("normalized_title")
            if eco_id and normalized:
                mapping[normalized] = eco_id
        return mapping

    def _occupation_for_posting(self, posting: Mapping[str, Any]) -> Optional[str]:
        raw = posting.get(self.config.occupation_field)
        if not raw and self.mapping:
            normalized = (posting.get("normalized_title") or "").lower()
            return self.mapping.get(normalized)
        if not raw:
            return None
        return str(raw).lower().replace(" ", "_")


def _weight_for_posting(posting: Mapping[str, Any]) -> float:
    base = 1.0
    salary = posting.get("salary") or posting.get("compensation")
    if salary:
        base += 0.2
    company = posting.get("company") or posting.get("employer")
    if company:
        base += 0.1
    return base


def run_yoe_analysis(input_paths: Sequence[str], output_path: str, mapping_path: Optional[str] = None) -> Dict[str, Any]:
    config = YoEAnalyzerConfig(
        input_paths=[Path(path) for path in input_paths],
        mapping_path=Path(mapping_path) if mapping_path else None,
        output_path=Path(output_path),
    )
    analyzer = YoERangeAnalyzer(config)
    return analyzer.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compute YoE ranges per ECO occupation")
    parser.add_argument("inputs", nargs="+", help="Paths to job posting datasets")
    parser.add_argument("--output", required=True, help="Output JSON file")
    parser.add_argument("--mapping", help="Optional occupation mapping JSON file")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--min-records", type=int, default=5)
    args = parser.parse_args()

    cfg = YoEAnalyzerConfig(
        input_paths=[Path(path) for path in args.inputs],
        mapping_path=Path(args.mapping) if args.mapping else None,
        output_path=Path(args.output),
        limit=args.limit,
        min_records=args.min_records,
    )
    YoERangeAnalyzer(cfg).run()
