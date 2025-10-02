"""Detects Brazilian tech career progression chains from clustered titles."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

import importlib

try:
    from scripts import clustering_dao
except ModuleNotFoundError:  # pragma: no cover - optional during certain tests
    clustering_dao = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


CAREER_LEVELS = [
    "estagiario",
    "junior",
    "junior pleno",
    "pleno",
    "senior",
    "senior tecnico",
    "tech lead",
    "principal",
    "coordenador",
    "gerente",
]

LEVEL_PATTERNS = {
    "estagiario": [r"est[aá]gio", r"trainee"],
    "junior": [r"j[úu]nior", r"junior", r"jr\b"],
    "junior pleno": [r"jr[\s/-]*pl", r"junior[\s/-]*pleno"],
    "pleno": [r"pleno", r"pl\b"],
    "senior": [r"s[êe]nior", r"sr\b"],
    "senior tecnico": [r"s[êe]nior[\s-]*t[eé]cnico"],
    "tech lead": [r"tech\s*lead", r"lider\s*t[eé]cnico"],
    "principal": [r"principal", r"staff", r"especialista"],
    "coordenador": [r"coordenador", r"coordenadora"],
    "gerente": [r"gerente", r"head"],
}

TRACK_KEYWORDS = {
    "frontend": [r"front[-\s]?end", r"ui"],
    "backend": [r"back[-\s]?end", r"server"],
    "mobile": [r"mobile", r"android", r"ios"],
    "dados": [r"dados", r"data", r"bi", r"analytics"],
    "devops": [r"devops", r"sre", r"infra"],
    "qa": [r"qa", r"qualidade", r"teste"],
}

EXPECTED_LADDERS = [
    ("estagiario", "junior", "pleno", "senior"),
    ("junior", "pleno", "senior", "tech lead", "principal"),
    ("pleno", "senior", "tech lead", "gerente"),
    ("analista", "especialista", "coordenador", "gerente"),
]


@dataclass
class ProgressionConfig:
    cluster_results_path: Path
    min_confidence: float = 0.2


class CareerProgressionDetector:
    """Builds career progression chains from cluster data."""

    def __init__(self, config: ProgressionConfig) -> None:
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
        self.config = config
        self.normalizer = self._load_normalizer()
        self.patterns = self._compile_patterns()

    def _load_normalizer(self) -> Any:
        module = importlib.import_module("scripts.eco_title_normalizer")
        if hasattr(module, "EcoTitleNormalizer"):
            return module.EcoTitleNormalizer()
        if hasattr(module, "BrazilianPortugueseNormalizer"):
            return module.BrazilianPortugueseNormalizer()
        return None

    def _compile_patterns(self) -> Dict[str, List[re.Pattern[str]]]:
        return {level: [re.compile(pattern, re.IGNORECASE) for pattern in patterns] for level, patterns in LEVEL_PATTERNS.items()}

    def run(self) -> Dict[str, Any]:
        logger.info("Loading clustering results from %s", self.config.cluster_results_path)
        with self.config.cluster_results_path.open("r", encoding="utf-8") as handle:
            clusters = json.load(handle)
        clusters_data = clusters.get("clusters") or {}
        level_counts: Dict[str, int] = defaultdict(int)
        track_counts: Dict[str, int] = defaultdict(int)
        edges: MutableMapping[Tuple[str, str], Dict[str, Any]] = defaultdict(lambda: {"count": 0, "examples": []})
        edges_by_track: Dict[str, MutableMapping[Tuple[str, str], Dict[str, Any]]] = defaultdict(lambda: defaultdict(lambda: {"count": 0, "examples": []}))
        for cluster_info in clusters_data.values():
            titles = cluster_info.get("titles", [])
            ordered_levels = sorted(
                {self._detect_level(title.get("text") or "") for title in titles if title.get("text")},
                key=self._level_priority,
            )
            ordered_levels = [level for level in ordered_levels if level]
            if len(ordered_levels) < 2:
                continue
            for level in ordered_levels:
                level_counts[level] += 1
            track = self._detect_track(cluster_info) or "general"
            track_counts[track] += 1
            for frm, to in zip(ordered_levels, ordered_levels[1:]):
                if not frm or not to:
                    continue
                key = (frm, to)
                edges[key]["count"] += 1
                if len(edges[key]["examples"]) < 5:
                    edges[key]["examples"].append(cluster_info.get("representative"))
                track_edge = edges_by_track[track][key]
                track_edge["count"] += 1
                if len(track_edge["examples"]) < 5:
                    track_edge["examples"].append(cluster_info.get("representative"))
        total_transitions = sum(info["count"] for info in edges.values())
        progressions = self._build_progressions(edges, total_transitions)
        track_progressions = {
            track: self._build_progressions(track_edges, sum(item["count"] for item in track_edges.values()))
            for track, track_edges in edges_by_track.items()
        }
        statistics = {
            "total_clusters": len(clusters_data),
            "total_transitions": total_transitions,
            "level_counts": dict(level_counts),
            "track_counts": dict(track_counts),
            "transition_probabilities": self._compute_transition_probabilities(edges, total_transitions),
        }
        validation = self._validate_progressions(progressions)
        payload = {
            "levels": dict(level_counts),
            "tracks": dict(track_counts),
            "progressions": progressions,
            "track_progressions": track_progressions,
            "statistics": statistics,
            "validation": validation,
        }
        self._persist_progressions(progressions)
        logger.info("Detected %d career progression edges", len(edges))
        return payload

    def _normalize(self, text: str) -> str:
        if not self.normalizer:
            return text.lower()
        if hasattr(self.normalizer, "normalize"):
            return self.normalizer.normalize(text)
        if hasattr(self.normalizer, "normalize_title"):
            return self.normalizer.normalize_title(text)
        return text.lower()

    def _detect_level(self, title: str) -> Optional[str]:
        normalized = self._normalize(title)
        for level, patterns in self.patterns.items():
            if any(pattern.search(normalized) for pattern in patterns):
                return level
        return None

    def _level_priority(self, level: Optional[str]) -> int:
        if level is None:
            return len(CAREER_LEVELS) + 1
        try:
            return CAREER_LEVELS.index(level)
        except ValueError:
            return len(CAREER_LEVELS) + 1

    def _detect_track(self, cluster_info: Mapping[str, Any]) -> Optional[str]:
        texts = [title.get("text", "") for title in cluster_info.get("titles", [])]
        for track, patterns in TRACK_KEYWORDS.items():
            if any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns for text in texts):
                return track
        return None

    def _build_progressions(self, edges: Mapping[Tuple[str, str], Mapping[str, Any]], total_edges: int) -> List[Dict[str, Any]]:
        progressions: List[Dict[str, Any]] = []
        for (frm, to), info in edges.items():
            confidence = min(1.0, info["count"] / 10.0)
            if confidence < self.config.min_confidence:
                continue
            probability = info["count"] / total_edges if total_edges else 0.0
            progressions.append(
                {
                    "from_level": frm,
                    "to_level": to,
                    "confidence": round(confidence, 3),
                    "evidence_count": info["count"],
                    "examples": info["examples"],
                    "probability": round(probability, 3),
                }
            )
        progressions.sort(key=lambda item: (-item["confidence"], -item["evidence_count"]))
        return progressions

    def _persist_progressions(self, progressions: Sequence[Mapping[str, Any]]) -> None:
        if clustering_dao is None or not hasattr(clustering_dao, "upsert_career_progression"):
            return
        for entry in progressions:
            frm = entry.get("from_level")
            to = entry.get("to_level")
            if not frm or not to:
                continue
            metadata = {
                "examples": entry.get("examples"),
                "probability": entry.get("probability"),
            }
            try:
                self._run_async(
                    lambda frm=frm, to=to, conf=entry.get("confidence", 0.0),
                    count=entry.get("evidence_count", 0), meta=metadata:
                    clustering_dao.upsert_career_progression(
                        from_level=str(frm),
                        to_level=str(to),
                        confidence=float(conf),
                        evidence_count=int(count),
                        metadata=meta,
                    )
                )
            except Exception as exc:  # pragma: no cover - database optional in tests
                logger.warning("Failed to persist career progression %s->%s: %s", entry.get("from_level"), entry.get("to_level"), exc)
                break

    @staticmethod
    def _run_async(factory: Callable[[], Awaitable[Any]]) -> Any:
        try:
            return asyncio.run(factory())
        except RuntimeError as exc:
            if "event loop is running" not in str(exc):
                raise
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(factory())
            finally:
                loop.close()

    def _compute_transition_probabilities(
        self,
        edges: Mapping[Tuple[str, str], Mapping[str, Any]],
        total_edges: int,
    ) -> Dict[str, float]:
        if total_edges == 0:
            return {}
        return {
            f"{frm}->{to}": round(info["count"] / total_edges, 4)
            for (frm, to), info in edges.items()
        }

    def _validate_progressions(self, progressions: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        expected_edges = {
            (frm, to)
            for ladder in EXPECTED_LADDERS
            for frm, to in zip(ladder, ladder[1:])
        }
        observed_edges = {(item["from_level"], item["to_level"]) for item in progressions}
        missing = sorted(expected_edges - observed_edges)
        unexpected = sorted(observed_edges - expected_edges)
        coverage = 1.0 if not expected_edges else (len(expected_edges) - len(missing)) / len(expected_edges)
        low_confidence = [
            (item["from_level"], item["to_level"])
            for item in progressions
            if item.get("confidence", 0) < max(self.config.min_confidence, 0.3)
        ]
        return {
            "expected_edge_count": len(expected_edges),
            "observed_edge_count": len(observed_edges),
            "coverage_ratio": round(coverage, 3),
            "missing_expected_edges": missing,
            "unexpected_edges": unexpected,
            "low_confidence_edges": low_confidence,
        }


def _parse_args(argv: Optional[Sequence[str]] = None) -> Any:
    import argparse

    parser = argparse.ArgumentParser(description="Detect Brazilian career progressions from clustering results")
    parser.add_argument("clusters", help="Path to clustering output JSON")
    parser.add_argument("--min-confidence", type=float, default=0.2)
    parser.add_argument("--output", type=str)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = _parse_args(argv)
    config = ProgressionConfig(cluster_results_path=Path(args.clusters), min_confidence=args.min_confidence)
    detector = CareerProgressionDetector(config)
    payload = detector.run()
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        logger.info("Wrote career progression output to %s", path)


if __name__ == "__main__":
    main()
