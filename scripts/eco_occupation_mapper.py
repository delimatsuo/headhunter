"""Generate ECO occupation mappings for Brazilian job title clusters."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import importlib

logger = logging.getLogger(__name__)


CATEGORY_DEFAULT = "GENERAL"


@dataclass
class OccupationMapperConfig:
    clusters_path: Path
    progression_path: Optional[Path] = None
    output_path: Optional[Path] = None
    category: str = CATEGORY_DEFAULT


class EcoOccupationMapper:
    """Transforms clusters and progression data into ECO occupation templates."""

    def __init__(self, config: OccupationMapperConfig) -> None:
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
        self.config = config
        self.alias_scorer = self._load_alias_scorer()
        self.eco_client = self._load_eco_client()

    def _load_alias_scorer(self) -> Any:
        module = importlib.import_module("scripts.alias_confidence_scorer")
        if hasattr(module, "AliasConfidenceScorer"):
            return module.AliasConfidenceScorer()
        if hasattr(module, "score_alias"):
            return module
        raise AttributeError("Alias confidence scorer implementation not found")

    def _load_eco_client(self) -> Any:
        try:
            module = importlib.import_module("functions.src.eco.eco-client")  # type: ignore[import-not-found]
        except ModuleNotFoundError:
            module = None
        return module

    def run(self) -> Dict[str, Any]:
        clusters = self._load_json(self.config.clusters_path)
        progression = self._load_json(self.config.progression_path) if self.config.progression_path else {}
        cluster_entries = clusters.get("clusters") or {}
        mapping_payload = []
        review_queue: List[Dict[str, Any]] = []
        for cluster_id, cluster_info in cluster_entries.items():
            occupation_id = self._build_occupation_id(cluster_id)
            aliases = self._build_aliases(cluster_info)
            skill_requirements = self._infer_skill_requirements(cluster_info, aliases)
            experience_range = self._infer_experience_range(cluster_info)
            progression_track = self._find_progressions_for_cluster(cluster_info, progression)
            confidence_summary = self._summarize_alias_confidence(aliases)
            review_required = self._needs_review(cluster_info, confidence_summary)
            if review_required:
                review_queue.append(
                    {
                        "occupation_id": occupation_id,
                        "cluster_id": cluster_id,
                        "reason": self._build_review_reason(cluster_info, confidence_summary),
                        "confidence_summary": confidence_summary,
                    }
                )
            mapping_payload.append(
                {
                    "occupation_id": occupation_id,
                    "display_name": self._build_display_name(cluster_info),
                    "aliases": aliases,
                    "cluster_id": cluster_id,
                    "frequency": cluster_info.get("frequency", 0),
                    "progression": progression_track,
                    "skill_requirements": skill_requirements,
                    "experience_range_years": experience_range,
                    "metadata": {
                        "sources": cluster_info.get("sources", {}),
                        "representative": cluster_info.get("representative"),
                        "confidence_summary": confidence_summary,
                        "review_required": review_required,
                    },
                }
            )
        payload = {
            "category": self.config.category,
            "occupations": mapping_payload,
            "review_queue": review_queue,
        }
        if self.config.output_path:
            self.config.output_path.parent.mkdir(parents=True, exist_ok=True)
            with self.config.output_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            logger.info("Wrote ECO occupation mapping to %s", self.config.output_path)
        return payload

    def _build_occupation_id(self, cluster_id: Any) -> str:
        raw = str(cluster_id)
        if ":" in raw:
            raw = raw.split(":", 1)[1]
        sanitized = re.sub(r"[^A-Za-z0-9_.]+", "_", raw)
        sanitized = sanitized.strip("_") or "UNK"
        return f"ECO.BR.SE.{self.config.category}.{sanitized}"

    def _build_display_name(self, cluster_info: Mapping[str, Any]) -> str:
        representative = cluster_info.get("representative") or {}
        text = representative.get("text")
        if text:
            return text
        titles = [title.get("text") for title in cluster_info.get("titles", []) if title.get("text")]
        return titles[0] if titles else "Ocupação Desconhecida"

    def _build_aliases(self, cluster_info: Mapping[str, Any]) -> List[Dict[str, Any]]:
        aliases = []
        for title in cluster_info.get("titles", []):
            text = title.get("text")
            if not text:
                continue
            score = self._score_alias(text, cluster_info.get("representative", {}).get("text"))
            aliases.append(
                {
                    "alias": text,
                    "confidence": score,
                    "frequency": title.get("metadata", {}).get("frequency", 1),
                }
            )
        aliases.sort(key=lambda alias: (-alias["confidence"], -alias["frequency"]))
        return aliases

    def _score_alias(self, alias: str, canonical: Optional[str]) -> float:
        if hasattr(self.alias_scorer, "score"):
            return float(self.alias_scorer.score(alias, canonical))
        if hasattr(self.alias_scorer, "score_alias"):
            return float(self.alias_scorer.score_alias(alias, canonical))
        if hasattr(self.alias_scorer, "__call__"):
            return float(self.alias_scorer(alias, canonical))
        return 0.5

    def _infer_skill_requirements(
        self,
        cluster_info: Mapping[str, Any],
        aliases: Sequence[Mapping[str, Any]],
    ) -> List[str]:
        text_corpus = " ".join(alias.get("alias", "") for alias in aliases).lower()
        representative = (cluster_info.get("representative") or {}).get("text", "")
        text_corpus += f" {representative.lower()}"
        skill_map = {
            "frontend": ["react", "javascript", "typescript"],
            "backend": ["java", "python", "node"],
            "dados": ["sql", "python", "spark"],
            "devops": ["aws", "kubernetes", "terraform"],
            "mobile": ["kotlin", "swift", "flutter"],
        }
        inferred: List[str] = []
        for track, skills in skill_map.items():
            if track in text_corpus:
                inferred.extend(skills)
        if "full stack" in text_corpus or "fullstack" in text_corpus:
            inferred.extend(["javascript", "node", "react"])
        if "qa" in text_corpus or "teste" in text_corpus:
            inferred.extend(["test automation", "cypress", "selenium"])
        return sorted({skill.capitalize() for skill in inferred})

    def _infer_experience_range(self, cluster_info: Mapping[str, Any]) -> Dict[str, Optional[int]]:
        representative = (cluster_info.get("representative") or {}).get("text", "").lower()
        titles = " ".join(title.get("text", "").lower() for title in cluster_info.get("titles", []))
        text = f"{representative} {titles}"
        if "estagi" in text:
            return {"min": 0, "max": 1}
        if any(keyword in text for keyword in ("junior", "jr")):
            return {"min": 0, "max": 3}
        if "pleno" in text or "mid" in text:
            return {"min": 2, "max": 5}
        if any(keyword in text for keyword in ("sênior", "senior", "sr")):
            return {"min": 5, "max": 9}
        if any(keyword in text for keyword in ("tech lead", "líder", "principal", "coordenador", "gerente")):
            return {"min": 7, "max": None}
        return {"min": None, "max": None}

    def _summarize_alias_confidence(self, aliases: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        if not aliases:
            return {"mean": None, "min": None, "max": None}
        confidences = [alias.get("confidence", 0.0) for alias in aliases]
        return {
            "mean": sum(confidences) / len(confidences),
            "min": min(confidences),
            "max": max(confidences),
        }

    def _needs_review(self, cluster_info: Mapping[str, Any], confidence_summary: Mapping[str, Any]) -> bool:
        frequency = cluster_info.get("frequency", 0)
        if frequency < 5:
            return True
        min_conf = confidence_summary.get("min") or 0
        if min_conf < 0.45:
            return True
        representative = (cluster_info.get("representative") or {}).get("text", "")
        if not representative:
            return True
        return False

    def _build_review_reason(self, cluster_info: Mapping[str, Any], confidence_summary: Mapping[str, Any]) -> str:
        reasons = []
        if cluster_info.get("frequency", 0) < 5:
            reasons.append("low frequency")
        if (confidence_summary.get("min") or 0) < 0.45:
            reasons.append("low alias confidence")
        if not (cluster_info.get("representative") or {}).get("text"):
            reasons.append("missing representative title")
        return ", ".join(reasons) or "manual review requested"

    def _find_progressions_for_cluster(self, cluster_info: Mapping[str, Any], progression: Mapping[str, Any]) -> List[Mapping[str, Any]]:
        representative = cluster_info.get("representative") or {}
        rep_texts = {
            text
            for text in [representative.get("text")] + [title.get("text") for title in cluster_info.get("titles", [])]
            if text
        }
        matches: List[Mapping[str, Any]] = []
        for entry in progression.get("progressions", []):
            examples = entry.get("examples", []) or []
            for example in examples:
                if isinstance(example, Mapping):
                    example_text = example.get("text")
                else:
                    example_text = str(example) if example else None
                if example_text and example_text in rep_texts:
                    matches.append(entry)
                    break
        return matches

    def _load_json(self, path: Optional[Path]) -> Mapping[str, Any]:
        if not path:
            return {}
        if not path.exists():
            logger.warning("File %s does not exist; returning empty payload", path)
            return {}
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)


def _parse_args(argv: Optional[Sequence[str]] = None) -> Any:
    import argparse

    parser = argparse.ArgumentParser(description="Generate ECO occupation mappings for Brazilian clusters")
    parser.add_argument("clusters", help="Path to clustering output JSON")
    parser.add_argument("--progression", type=str, help="Path to career progression JSON")
    parser.add_argument("--output", type=str)
    parser.add_argument("--category", default=CATEGORY_DEFAULT)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = _parse_args(argv)
    config = OccupationMapperConfig(
        clusters_path=Path(args.clusters),
        progression_path=Path(args.progression) if args.progression else None,
        output_path=Path(args.output) if args.output else None,
        category=args.category,
    )
    mapper = EcoOccupationMapper(config)
    mapper.run()


if __name__ == "__main__":
    main()
