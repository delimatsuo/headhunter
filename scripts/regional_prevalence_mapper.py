"""Regional prevalence mapper for Brazilian ECO template generation."""

from __future__ import annotations

import json
import logging
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

REGION_BY_STATE = {
    "AC": "Norte",
    "AL": "Nordeste",
    "AM": "Norte",
    "AP": "Norte",
    "BA": "Nordeste",
    "CE": "Nordeste",
    "DF": "Centro-Oeste",
    "ES": "Sudeste",
    "GO": "Centro-Oeste",
    "MA": "Nordeste",
    "MG": "Sudeste",
    "MS": "Centro-Oeste",
    "MT": "Centro-Oeste",
    "PA": "Norte",
    "PB": "Nordeste",
    "PE": "Nordeste",
    "PI": "Nordeste",
    "PR": "Sul",
    "RJ": "Sudeste",
    "RN": "Nordeste",
    "RO": "Norte",
    "RR": "Norte",
    "RS": "Sul",
    "SC": "Sul",
    "SE": "Nordeste",
    "SP": "Sudeste",
    "TO": "Norte",
}

CITY_TO_STATE = {
    "são paulo": "SP",
    "campinas": "SP",
    "santos": "SP",
    "rio de janeiro": "RJ",
    "niterói": "RJ",
    "belo horizonte": "MG",
    "uberlandia": "MG",
    "curitiba": "PR",
    "porto alegre": "RS",
    "florianópolis": "SC",
    "recife": "PE",
    "salvador": "BA",
    "fortaleza": "CE",
    "manaus": "AM",
    "brasília": "DF",
    "goiânia": "GO",
}


@dataclass
class RegionalMapperConfig:
    input_paths: Sequence[Path]
    output_path: Path
    occupation_field: str = "eco_occupation"
    location_field: str = "location"
    salary_field: str = "salary"
    skills_field: str = "skills"
    limit: Optional[int] = None


@dataclass
class RegionAggregate:
    occurrences: int = 0
    salary_samples: List[float] = field(default_factory=list)
    skill_counter: Dict[str, int] = field(default_factory=dict)
    demand_score: float = 0.0
    postings: List[str] = field(default_factory=list)

    sources: Dict[str, int] = field(default_factory=dict)

    def register(
        self,
        posting_id: Optional[str],
        salary: Optional[float],
        skills: Sequence[str],
        source: Optional[str] = None,
    ) -> None:
        self.occurrences += 1
        if salary is not None:
            self.salary_samples.append(salary)
        for skill in skills:
            norm = skill.strip().lower()
            if not norm:
                continue
            self.skill_counter[norm] = self.skill_counter.get(norm, 0) + 1
        if posting_id:
            if len(self.postings) < 50:
                self.postings.append(posting_id)
        if source:
            key = str(source).upper()
            self.sources[key] = self.sources.get(key, 0) + 1

    def summary(self) -> Dict[str, Any]:
        salary_stats = None
        if self.salary_samples:
            trimmed = _trim_outliers(self.salary_samples)
            if trimmed:
                salary_stats = {
                    "mean": round(statistics.mean(trimmed), 2),
                    "median": round(statistics.median(trimmed), 2),
                    "p90": round(_percentile(trimmed, 90), 2),
                }
        top_skills = sorted(self.skill_counter.items(), key=lambda item: item[1], reverse=True)[:10]
        return {
            "occurrences": self.occurrences,
            "salary": salary_stats,
            "top_skills": [{"skill": skill, "count": count} for skill, count in top_skills],
            "postings": self.postings,
            "sources": dict(self.sources),
        }


@dataclass
class OccupationRegionalProfile:
    occupation: str
    regions: Dict[str, RegionAggregate] = field(default_factory=lambda: defaultdict(RegionAggregate))
    total_postings: int = 0

    def register(
        self,
        region_key: str,
        posting_id: Optional[str],
        salary: Optional[float],
        skills: Sequence[str],
        source: Optional[str],
    ) -> None:
        self.total_postings += 1
        aggregate = self.regions.setdefault(region_key, RegionAggregate())
        aggregate.register(posting_id, salary, skills, source)

    def serialize(self) -> Dict[str, Any]:
        payload = {region: data.summary() for region, data in self.regions.items() if data.occurrences > 0}
        coverage = {region: info["occurrences"] for region, info in payload.items()}
        demand = _compute_demand_levels(coverage, self.total_postings)
        for region, info in payload.items():
            info["demand_level"] = demand.get(region, "moderado")
            info["confidence"] = _confidence_from_samples(info["occurrences"], self.total_postings)
        return {
            "occupation": self.occupation,
            "prevalence_by_region": payload,
            "total_postings": self.total_postings,
        }


class RegionalPrevalenceMapper:
    def __init__(self, config: RegionalMapperConfig) -> None:
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
        self.config = config
        self.profiles: Dict[str, OccupationRegionalProfile] = {}

    def run(self) -> Dict[str, Any]:
        logger = logging.getLogger(__name__)
        logger.info("Starting regional prevalence mapping")
        count = 0
        for posting in self._iter_postings():
            region_key = self._region_for_posting(posting)
            if not region_key:
                continue
            occupation = self._occupation(posting)
            if not occupation:
                continue
            profile = self.profiles.setdefault(occupation, OccupationRegionalProfile(occupation))
            posting_id = str(posting.get("posting_id") or posting.get("id") or "") or None
            salary = _parse_salary(posting.get(self.config.salary_field))
            skills = posting.get(self.config.skills_field) or []
            source = posting.get("source") or posting.get("origin")
            profile.register(region_key, posting_id, salary, skills, source)
            count += 1
            if self.config.limit and count >= self.config.limit:
                break
        payload = {occupation: profile.serialize() for occupation, profile in self.profiles.items() if profile.total_postings > 0}
        self.config.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config.output_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        logger.info("Regional prevalence mapping complete | occupations=%d", len(payload))
        return payload

    def _iter_postings(self) -> Iterable[Mapping[str, Any]]:
        for path in self.config.input_paths:
            if not path.exists():
                logging.getLogger(__name__).warning("Regional dataset missing: %s", path)
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

    def _occupation(self, posting: Mapping[str, Any]) -> Optional[str]:
        raw = posting.get(self.config.occupation_field)
        if not raw:
            return None
        return str(raw).lower().replace(" ", "_")

    def _region_for_posting(self, posting: Mapping[str, Any]) -> Optional[str]:
        raw_location = posting.get(self.config.location_field) or posting.get("city")
        if not raw_location:
            return None
        location = str(raw_location).strip().lower()
        # Extract state abbreviation if present
        for state_match in _STATE_PATTERN.finditer(location):
            state = state_match.group(1).upper()
            region = REGION_BY_STATE.get(state)
            if region:
                return region
        # Try city mapping
        for city, state in CITY_TO_STATE.items():
            if city in location:
                return REGION_BY_STATE.get(state)
        return None


def _compute_demand_levels(coverage: Mapping[str, int], total_postings: int) -> Dict[str, str]:
    demand: Dict[str, str] = {}
    if total_postings == 0:
        return demand
    sorted_regions = sorted(coverage.items(), key=lambda item: item[1], reverse=True)
    for idx, (region, count) in enumerate(sorted_regions):
        share = count / total_postings
        if share > 0.35 or idx == 0:
            demand[region] = "altíssimo"
        elif share > 0.2:
            demand[region] = "alto"
        elif share > 0.1:
            demand[region] = "moderado"
        else:
            demand[region] = "emergente"
    return demand


def _confidence_from_samples(region_postings: int, total_postings: int) -> float:
    if total_postings == 0:
        return 0.0
    bayes = (region_postings + 1) / (total_postings + 4)
    return round(min(1.0, bayes), 3)


def _parse_salary(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).lower()
    numbers = [float(value.replace(".", "").replace(",", ".")) for value in _NUMBER_PATTERN.findall(text)]
    if not numbers:
        return None
    if "a" in text or "-" in text:
        return sum(numbers) / len(numbers)
    return numbers[0]


def _trim_outliers(values: Sequence[float]) -> List[float]:
    if len(values) < 4:
        return list(values)
    sorted_values = sorted(values)
    q1 = statistics.quantiles(sorted_values, n=4)[0]
    q3 = statistics.quantiles(sorted_values, n=4)[2]
    iqr = q3 - q1
    lower = max(0.0, q1 - 1.5 * iqr)
    upper = q3 + 1.5 * iqr
    return [value for value in sorted_values if lower <= value <= upper]


def _percentile(values: Sequence[float], percent: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    k = (len(sorted_values) - 1) * percent / 100
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    d0 = sorted_values[f] * (c - k)
    d1 = sorted_values[c] * (k - f)
    return d0 + d1


_NUMBER_PATTERN = __import__("re").compile(r"\d+[.,]?\d*")
_STATE_PATTERN = __import__("re").compile(r"(?:\b|\()([A-Z]{2})(?:\b|\))", __import__("re").IGNORECASE)


def map_regional_prevalence(input_paths: Sequence[str], output_path: str) -> Dict[str, Any]:
    config = RegionalMapperConfig(
        input_paths=[Path(path) for path in input_paths],
        output_path=Path(output_path),
    )
    mapper = RegionalPrevalenceMapper(config)
    return mapper.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Map regional prevalence for ECO occupations")
    parser.add_argument("inputs", nargs="+", help="Paths to job posting datasets")
    parser.add_argument("--output", required=True, help="Output JSON file")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    cfg = RegionalMapperConfig(
        input_paths=[Path(path) for path in args.inputs],
        output_path=Path(args.output),
        limit=args.limit,
    )
    RegionalPrevalenceMapper(cfg).run()
