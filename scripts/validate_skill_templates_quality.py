"""Validation toolkit for ECO skill templates."""

from __future__ import annotations

import json
import logging
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence


@dataclass
class TemplateValidationConfig:
    templates_path: Path
    report_path: Path
    skill_golden_path: Optional[Path] = None
    regional_golden_path: Optional[Path] = None
    confidence_floor: float = 0.4
    min_required_skills: int = 3


class SkillTemplateQualityValidator:
    def __init__(self, config: TemplateValidationConfig) -> None:
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
        self.config = config
        self.logger = logging.getLogger(__name__)

    def run(self) -> Dict[str, Any]:
        templates = self._load_templates()
        skill_precision = self._evaluate_skills(templates)
        experience_metrics = self._evaluate_experience(templates)
        regional_metrics = self._evaluate_regions(templates)
        completeness = self._template_completeness(templates)
        recommendations = self._recommendations(skill_precision, experience_metrics, regional_metrics, completeness)
        payload = {
            "skill_precision": skill_precision,
            "experience_metrics": experience_metrics,
            "regional_metrics": regional_metrics,
            "completeness": completeness,
            "recommendations": recommendations,
        }
        self.config.report_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config.report_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        self.logger.info("Validation report written to %s", self.config.report_path)
        return payload

    def _load_templates(self) -> Mapping[str, Any]:
        if not self.config.templates_path.exists():
            raise FileNotFoundError(self.config.templates_path)
        with self.config.templates_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            payload = {entry.get("occupation", f"occupation-{idx}"): entry for idx, entry in enumerate(payload)}
        return payload

    def _evaluate_skills(self, templates: Mapping[str, Any]) -> Dict[str, Any]:
        total_required = []
        total_preferred = []
        below_threshold = []
        precision = None
        recall = None
        f1 = None
        if self.config.skill_golden_path and self.config.skill_golden_path.exists():
            golden = _load_golden(self.config.skill_golden_path)
            matches = 0
            total_pred = 0
            total_gold = 0
            for occupation, template in templates.items():
                required = {item.get("skill") for item in template.get("required_skills", [])}
                preferred = {item.get("skill") for item in template.get("preferred_skills", [])}
                total_required.append(len(required))
                total_preferred.append(len(preferred))
                total_pred += len(required)
                truth = set(golden.get(occupation, []))
                total_gold += len(truth)
                matches += len(required & truth)
                for item in template.get("required_skills", []):
                    if item.get("confidence", 0.0) < self.config.confidence_floor:
                        below_threshold.append((occupation, item.get("skill"), item.get("confidence")))
            precision = matches / total_pred if total_pred else None
            recall = matches / total_gold if total_gold else None
            if precision and recall:
                f1 = 2 * precision * recall / (precision + recall)
        else:
            for occupation, template in templates.items():
                required = template.get("required_skills", [])
                preferred = template.get("preferred_skills", [])
                total_required.append(len(required))
                total_preferred.append(len(preferred))
                for item in required:
                    if item.get("confidence", 0.0) < self.config.confidence_floor:
                        below_threshold.append((occupation, item.get("skill"), item.get("confidence")))
        stats = {
            "required_mean": statistics.mean(total_required) if total_required else 0,
            "preferred_mean": statistics.mean(total_preferred) if total_preferred else 0,
            "required_median": statistics.median(total_required) if total_required else 0,
            "templates_below_confidence": below_threshold,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
        return stats

    def _evaluate_experience(self, templates: Mapping[str, Any]) -> Dict[str, Any]:
        coverage = 0
        missing = []
        low_confidence = []
        ranges = []
        for occupation, template in templates.items():
            min_years = template.get("min_years_experience")
            max_years = template.get("max_years_experience")
            experience = template.get("experience_distribution", {})
            confidence = template.get("confidence", 0.0)
            if min_years is None or max_years is None:
                missing.append(occupation)
                continue
            if min_years < 0 or (max_years and max_years > 40):
                missing.append(occupation)
                continue
            coverage += 1
            ranges.append(max_years - min_years if max_years is not None else 0)
            if confidence < self.config.confidence_floor:
                low_confidence.append(occupation)
        return {
            "coverage": coverage,
            "total_templates": len(templates),
            "missing": missing,
            "low_confidence": low_confidence,
            "average_range": statistics.mean(ranges) if ranges else 0.0,
        }

    def _evaluate_regions(self, templates: Mapping[str, Any]) -> Dict[str, Any]:
        total_regions = []
        confidence_scores = []
        discrepancies = []
        golden = _load_golden(self.config.regional_golden_path) if self.config.regional_golden_path else {}
        for occupation, template in templates.items():
            prevalence = template.get("prevalence_by_region", {})
            total_regions.append(len(prevalence))
            confidence_scores.extend(info.get("confidence", 0.0) for info in prevalence.values())
            if golden:
                baseline = set(golden.get(occupation, []))
                inferred = {region for region, info in prevalence.items() if info.get("demand_level") in {"altíssimo", "alto"}}
                if baseline and not baseline.issubset(inferred):
                    discrepancies.append({"occupation": occupation, "expected": sorted(baseline), "observed": sorted(inferred)})
        return {
            "mean_regions": statistics.mean(total_regions) if total_regions else 0.0,
            "median_regions": statistics.median(total_regions) if total_regions else 0.0,
            "mean_confidence": statistics.mean(confidence_scores) if confidence_scores else 0.0,
            "discrepancies": discrepancies,
        }

    def _template_completeness(self, templates: Mapping[str, Any]) -> Dict[str, Any]:
        missing_required = []
        low_skill_count = []
        for occupation, template in templates.items():
            if not template.get("required_skills"):
                missing_required.append(occupation)
            elif len(template.get("required_skills", [])) < self.config.min_required_skills:
                low_skill_count.append(occupation)
            if template.get("confidence", 0.0) < self.config.confidence_floor:
                low_skill_count.append(occupation)
        return {
            "missing_required": missing_required,
            "low_skill_count": list(sorted(set(low_skill_count))),
        }

    def _recommendations(
        self,
        skill_metrics: Mapping[str, Any],
        experience_metrics: Mapping[str, Any],
        regional_metrics: Mapping[str, Any],
        completeness: Mapping[str, Any],
    ) -> Sequence[str]:
        recs = []
        if skill_metrics.get("precision") is not None and skill_metrics["precision"] < 0.7:
            recs.append("Expand gold standard alignment for skill extraction; precision below 0.7")
        if skill_metrics.get("templates_below_confidence"):
            recs.append("Review required skills with low confidence scores")
        if experience_metrics.get("coverage", 0) < experience_metrics.get("total_templates", 0):
            recs.append("Augment YoE extraction coverage for missing occupations")
        if regional_metrics.get("mean_regions", 0) < 2:
            recs.append("Increase geographic coverage; most occupations have <2 high-confidence regions")
        if completeness.get("missing_required"):
            recs.append("Fill missing required skills for occupations: " + ", ".join(completeness["missing_required"][:5]))
        if not recs:
            recs.append("Templates meet configured quality thresholds")
        return recs


def _load_golden(path: Optional[Path]) -> Dict[str, Sequence[str]]:
    if not path or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        return {key: value for key, value in payload.items()}
    if isinstance(payload, list):
        return {entry["occupation"]: entry.get("skills", []) for entry in payload if "occupation" in entry}
    return {}


def validate_skill_templates(templates_path: str, report_path: str, skill_golden: Optional[str] = None) -> Dict[str, Any]:
    config = TemplateValidationConfig(
        templates_path=Path(templates_path),
        report_path=Path(report_path),
        skill_golden_path=Path(skill_golden) if skill_golden else None,
    )
    validator = SkillTemplateQualityValidator(config)
    return validator.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate ECO skill templates")
    parser.add_argument("--templates", required=True, help="Path to generated templates JSON")
    parser.add_argument("--report", required=True, help="Destination for validation report")
    parser.add_argument("--golden-skills", help="Optional gold standard skills JSON")
    parser.add_argument("--golden-regions", help="Optional regional baseline JSON")
    args = parser.parse_args()

    config = TemplateValidationConfig(
        templates_path=Path(args.templates),
        report_path=Path(args.report),
        skill_golden_path=Path(args.golden_skills) if args.golden_skills else None,
        regional_golden_path=Path(args.golden_regions) if args.golden_regions else None,
    )
    SkillTemplateQualityValidator(config).run()
