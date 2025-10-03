"""Aggregates analysis outputs into ECO template payloads."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from scripts.evidence_tracking_system import EvidenceTracker, EvidenceTrackerConfig


@dataclass
class TemplateGeneratorConfig:
    skill_path: Path
    yoe_path: Path
    regional_path: Path
    output_path: Path
    evidence_path: Path
    version: str = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    generate_reports: bool = True


class EcoTemplateGenerator:
    def __init__(self, config: TemplateGeneratorConfig) -> None:
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
        self.config = config
        self.logger = logging.getLogger(__name__)

    def run(self) -> Dict[str, Any]:
        self.logger.info("Loading analysis artefacts")
        skill_payload = _load_json(self.config.skill_path)
        yoe_payload = _load_json(self.config.yoe_path)
        regional_payload = _load_json(self.config.regional_path)
        tracker = EvidenceTracker(
            EvidenceTrackerConfig(output_path=self.config.evidence_path, snapshot_path=self.config.evidence_path)
        )
        templates: Dict[str, Any] = {}
        for occupation, skills in skill_payload.items():
            yoe = yoe_payload.get(occupation, {})
            regional = regional_payload.get(occupation, {}).get("prevalence_by_region", {})
            template = self._build_template(occupation, skills, yoe, regional)
            templates[occupation] = template
            self._register_evidence(tracker, occupation, skills, yoe, regional)
        evidence_map = tracker.finalize()
        for occupation, template in templates.items():
            template["evidence"] = evidence_map.get(occupation, [])
        self._write_output(templates)
        return templates

    def _build_template(
        self,
        occupation: str,
        skills: Mapping[str, Any],
        yoe: Mapping[str, Any],
        regional: Mapping[str, Any],
    ) -> Dict[str, Any]:
        required = skills.get("required_skills", [])
        preferred = skills.get("preferred_skills", [])
        min_years = yoe.get("min_years")
        max_years = yoe.get("max_years")
        distribution = {key: yoe.get(key) for key in ("p25", "p50", "p75", "mean") if key in yoe}
        regional_payload = regional
        skill_confidence = _average_confidence(required + preferred)
        yoe_confidence = float(yoe.get("confidence", 0.0))
        region_confidence = _average_regional_confidence(regional_payload)
        composite_confidence = round(min(1.0, 0.5 * skill_confidence + 0.3 * yoe_confidence + 0.2 * region_confidence), 4)
        return {
            "occupation": occupation,
            "required_skills": required,
            "preferred_skills": preferred,
            "min_years_experience": min_years,
            "max_years_experience": max_years,
            "experience_distribution": distribution,
            "prevalence_by_region": regional_payload,
            "confidence": composite_confidence,
            "version": self.config.version,
            "generated_at": datetime.utcnow().isoformat(),
            "metadata": {
                "required_skill_count": len(required),
                "preferred_skill_count": len(preferred),
                "experience_postings": yoe.get("postings"),
                "regional_coverage": list(regional_payload.keys()),
            },
        }

    def _register_evidence(
        self,
        tracker: EvidenceTracker,
        occupation: str,
        skills: Mapping[str, Any],
        yoe: Mapping[str, Any],
        regional: Mapping[str, Any],
    ) -> None:
        required = skills.get("required_skills", [])
        preferred = skills.get("preferred_skills", [])
        for entry in required + preferred:
            distribution = entry.get("distribution", {})
            samples = distribution.get("samples")
            if isinstance(samples, list) and samples:
                posting_ids = samples
            else:
                posting_ids = [
                    f"skill-{occupation}-{entry.get('skill')}-{idx}"
                    for idx in range(int(distribution.get("postings") or 0))
                ]
            sources = list((entry.get("sources") or {}).keys())
            tracker.register_skill(
                occupation,
                entry.get("skill", ""),
                posting_ids,
                entry.get("confidence", 0.0),
                distribution.get("required", 0) + distribution.get("preferred", 0),
                sources,
                metadata={"taxonomy": entry.get("taxonomy"), "category": "required" if entry in required else "preferred"},
            )
        tracker.register_yoe(occupation, yoe)
        for region, info in regional.items():
            tracker.register_region(occupation, region, info)

    def _write_output(self, payload: Mapping[str, Any]) -> None:
        self.config.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config.output_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        logging.getLogger(__name__).warning("Template generator missing artefact: %s", path)
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _average_confidence(entries: Sequence[Mapping[str, Any]]) -> float:
    if not entries:
        return 0.0
    values = [entry.get("confidence", 0.0) for entry in entries]
    return sum(values) / len(values)


def _average_regional_confidence(regional: Mapping[str, Any]) -> float:
    if not regional:
        return 0.0
    values = [info.get("confidence", 0.0) for info in regional.values()]
    return sum(values) / max(1, len(values))


def generate_eco_templates(
    skill_path: str,
    yoe_path: str,
    regional_path: str,
    output_path: str,
    evidence_path: str,
    version: Optional[str] = None,
) -> Dict[str, Any]:
    config = TemplateGeneratorConfig(
        skill_path=Path(skill_path),
        yoe_path=Path(yoe_path),
        regional_path=Path(regional_path),
        output_path=Path(output_path),
        evidence_path=Path(evidence_path),
        version=version or datetime.utcnow().strftime("%Y%m%d%H%M%S"),
    )
    generator = EcoTemplateGenerator(config)
    return generator.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate ECO templates from pipeline artefacts")
    parser.add_argument("--skills", required=True, help="Path to skill extraction JSON")
    parser.add_argument("--yoe", required=True, help="Path to YoE analysis JSON")
    parser.add_argument("--regions", required=True, help="Path to regional prevalence JSON")
    parser.add_argument("--output", required=True, help="Destination for ECO templates JSON")
    parser.add_argument("--evidence", required=True, help="Evidence output JSON")
    parser.add_argument("--version", help="Template version identifier")
    args = parser.parse_args()

    generate_eco_templates(
        skill_path=args.skills,
        yoe_path=args.yoe,
        regional_path=args.regions,
        output_path=args.output,
        evidence_path=args.evidence,
        version=args.version,
    )
