"""Template accuracy validation for ECO quality assurance."""

from __future__ import annotations

import json
import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )


@dataclass
class TemplateAccuracyValidatorConfig:
    template_path: Path
    job_postings_path: Path
    output_dir: Path = Path("reports/eco_quality")
    benchmark_quality_score: float = 0.82
    drift_window_days: int = 90
    region_field: str = "region"
    score_weights: Mapping[str, float] = field(
        default_factory=lambda: {
            "skill_coverage": 0.35,
            "yoe_accuracy": 0.2,
            "skill_classification": 0.2,
            "regional_accuracy": 0.15,
            "drift": 0.1,
        }
    )


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class TemplateAccuracyValidator:
    """Validates ECO templates against live job posting requirements."""

    def __init__(self, config: TemplateAccuracyValidatorConfig) -> None:
        self.config = config
        self.templates = _load_json(config.template_path)
        self.postings = _load_json(config.job_postings_path)
        self.metrics: Dict[str, Any] = {}

    def _template_index(self) -> Mapping[str, Mapping[str, Any]]:
        if isinstance(self.templates, Mapping) and "templates" in self.templates:
            iterable = self.templates["templates"]
        else:
            iterable = self.templates
        return {str(item.get("eco_id")): item for item in iterable if item.get("eco_id")}

    def _postings_by_eco(self) -> Mapping[str, List[Mapping[str, Any]]]:
        groups: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
        for posting in self.postings:
            eco_id = posting.get("eco_id") or posting.get("template_id")
            if eco_id:
                groups[str(eco_id)].append(posting)
        return groups

    # ------------------------------------------------------------------
    # Metric computations requested in the implementation plan
    # ------------------------------------------------------------------
    def validateSkillCoverage(self) -> Dict[str, Any]:
        templates = self._template_index()
        postings = self._postings_by_eco()
        coverage_scores: Dict[str, float] = {}
        detailed: Dict[str, Dict[str, Any]] = {}
        for eco_id, template in templates.items():
            required_template = set(template.get("required_skills", []) or [])
            preferred_template = set(template.get("preferred_skills", []) or [])
            posting_skills = set()
            for posting in postings.get(eco_id, []):
                posting_skills.update(posting.get("required_skills", []) or [])
            coverage = len(required_template & posting_skills) / len(posting_skills) if posting_skills else 0.0
            coverage_scores[eco_id] = coverage
            missing = sorted(posting_skills - required_template)
            detailed[eco_id] = {
                "coverage": round(coverage, 4),
                "missing_skills": missing,
                "template_required": sorted(required_template),
                "posting_required": sorted(posting_skills),
            }
        average_coverage = statistics.mean(coverage_scores.values()) if coverage_scores else 0.0
        payload = {
            "average_coverage": round(average_coverage, 4),
            "per_template": detailed,
        }
        logger.info("Skill coverage average=%.4f", average_coverage)
        self.metrics["skill_coverage"] = payload
        return payload

    def validateYoEAccuracy(self) -> Dict[str, Any]:
        templates = self._template_index()
        postings = self._postings_by_eco()
        errors: List[float] = []
        per_template: Dict[str, Any] = {}
        for eco_id, template in templates.items():
            min_template = template.get("min_years_experience")
            max_template = template.get("max_years_experience")
            posting_ranges = [
                (
                    posting.get("min_years_experience") or posting.get("yoe_min"),
                    posting.get("max_years_experience") or posting.get("yoe_max"),
                )
                for posting in postings.get(eco_id, [])
            ]
            posting_ranges = [r for r in posting_ranges if r[0] is not None or r[1] is not None]
            if not posting_ranges:
                continue
            avg_min = statistics.mean([float(r[0]) for r in posting_ranges if r[0] is not None]) if any(r[0] is not None for r in posting_ranges) else None
            avg_max = statistics.mean([float(r[1]) for r in posting_ranges if r[1] is not None]) if any(r[1] is not None for r in posting_ranges) else None
            err_min = abs((min_template or avg_min or 0) - (avg_min or min_template or 0))
            err_max = abs((max_template or avg_max or 0) - (avg_max or max_template or 0))
            errors.append((err_min + err_max) / 2)
            per_template[eco_id] = {
                "template_range": [min_template, max_template],
                "observed_range": [avg_min, avg_max],
                "error": round((err_min + err_max) / 2, 4),
            }
        mae = statistics.mean(errors) if errors else 0.0
        payload = {"mean_absolute_error": round(mae, 4), "per_template": per_template}
        logger.info("YoE mean absolute error=%.4f", mae)
        self.metrics["yoe_accuracy"] = payload
        return payload

    def validateSkillClassification(self) -> Dict[str, Any]:
        templates = self._template_index()
        postings = self._postings_by_eco()
        precision_scores: List[float] = []
        recall_scores: List[float] = []
        per_template: Dict[str, Any] = {}
        for eco_id, template in templates.items():
            required_template = set(template.get("required_skills", []) or [])
            preferred_template = set(template.get("preferred_skills", []) or [])
            required_posting = set()
            preferred_posting = set()
            for posting in postings.get(eco_id, []):
                required_posting.update(posting.get("required_skills", []) or [])
                preferred_posting.update(posting.get("preferred_skills", []) or [])
            if not required_posting:
                continue
            true_positive = len(required_template & required_posting)
            false_positive = len(required_template - required_posting)
            false_negative = len(required_posting - required_template)
            precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 0.0
            recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) else 0.0
            precision_scores.append(precision)
            recall_scores.append(recall)
            per_template[eco_id] = {
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "false_positive": sorted(required_template - required_posting),
                "missed_required": sorted(required_posting - required_template),
                "preferred_alignment": round(len(preferred_template & preferred_posting) / max(len(preferred_posting) or 1, 1), 4)
                if preferred_posting
                else None,
            }
        avg_precision = statistics.mean(precision_scores) if precision_scores else 0.0
        avg_recall = statistics.mean(recall_scores) if recall_scores else 0.0
        payload = {
            "precision": round(avg_precision, 4),
            "recall": round(avg_recall, 4),
            "per_template": per_template,
        }
        logger.info("Skill classification precision=%.4f recall=%.4f", avg_precision, avg_recall)
        self.metrics["skill_classification"] = payload
        return payload

    def validateRegionalAccuracy(self) -> Dict[str, Any]:
        postings = self._postings_by_eco()
        templates = self._template_index()
        region_field = self.config.region_field
        region_scores: Dict[str, List[float]] = defaultdict(list)
        for eco_id, items in postings.items():
            template_required = set(templates.get(eco_id, {}).get("required_skills", []) or [])
            for posting in items:
                region = posting.get(region_field, "UNKNOWN")
                posting_skills = set(posting.get("required_skills", []) or [])
                if not posting_skills:
                    continue
                coverage = len(template_required & posting_skills) / len(posting_skills)
                region_scores[str(region)].append(coverage)
        summary = {
            region: round(statistics.mean(values), 4) if values else 0.0 for region, values in region_scores.items()
        }
        payload = {
            "regions": summary,
            "region_count": len(summary),
            "lowest_region": min(summary, key=summary.get) if summary else None,
        }
        logger.info("Regional accuracy summary=%s", summary)
        self.metrics["regional_accuracy"] = payload
        return payload

    def detectTemplateDrift(self) -> Dict[str, Any]:
        cutoff = datetime.utcnow() - timedelta(days=self.config.drift_window_days)
        drift_scores: Dict[str, List[float]] = defaultdict(list)
        templates = self._template_index()
        for posting in self.postings:
            timestamp = posting.get("collected_at")
            if not timestamp:
                continue
            try:
                observed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            except ValueError:
                continue
            if observed < cutoff:
                continue
            eco_id = posting.get("eco_id")
            template = templates.get(str(eco_id))
            if not template:
                continue
            required = set(template.get("required_skills", []) or [])
            posting_skills = set(posting.get("required_skills", []) or [])
            if not posting_skills:
                continue
            coverage = len(required & posting_skills) / len(posting_skills)
            drift_scores[str(eco_id)].append(coverage)
        drift_summary = {
            eco_id: round(statistics.mean(values), 4)
            for eco_id, values in drift_scores.items()
            if values
        }
        payload = {
            "templates_in_window": len(drift_summary),
            "mean_recent_coverage": round(statistics.mean(drift_summary.values()), 4) if drift_summary else 0.0,
            "at_risk_templates": [eco_id for eco_id, score in drift_summary.items() if score < 0.6],
        }
        logger.info("Detected template drift across %s templates", payload["templates_in_window"])
        self.metrics["drift"] = payload
        return payload

    def calculateTemplateQualityScore(self) -> Dict[str, Any]:
        weights = self.config.score_weights
        skill_cov = self.metrics.get("skill_coverage") or self.validateSkillCoverage()
        yoe = self.metrics.get("yoe_accuracy") or self.validateYoEAccuracy()
        classification = self.metrics.get("skill_classification") or self.validateSkillClassification()
        regional = self.metrics.get("regional_accuracy") or self.validateRegionalAccuracy()
        drift = self.metrics.get("drift") or self.detectTemplateDrift()

        components = {
            "skill_coverage": skill_cov.get("average_coverage", 0.0),
            "yoe_accuracy": max(0.0, 1.0 - (yoe.get("mean_absolute_error", 0.0) / 5.0)),
            "skill_classification": (classification.get("precision", 0.0) + classification.get("recall", 0.0)) / 2,
            "regional_accuracy": statistics.mean(regional.get("regions", {}).values()) if regional.get("regions") else 0.0,
            "drift": drift.get("mean_recent_coverage", 0.0),
        }
        overall = 0.0
        for key, value in components.items():
            overall += weights.get(key, 0.0) * float(value)
        payload = {"score": round(overall, 4), "components": {k: round(v, 4) for k, v in components.items()}}
        logger.info("Template quality score %.4f (benchmark %.4f)", payload["score"], self.config.benchmark_quality_score)
        self.metrics["quality_score"] = payload
        return payload

    def generateImprovementRecommendations(self) -> Dict[str, Any]:
        skill_cov = self.metrics.get("skill_coverage") or self.validateSkillCoverage()
        classification = self.metrics.get("skill_classification") or self.validateSkillClassification()
        drift = self.metrics.get("drift") or self.detectTemplateDrift()
        recommendations: List[str] = []
        low_coverage = sorted(
            (
                (eco_id, data)
                for eco_id, data in skill_cov.get("per_template", {}).items()
                if data.get("coverage", 0.0) < 0.6 and data.get("missing_skills")
            ),
            key=lambda item: item[1]["coverage"],
        )[:25]
        for eco_id, data in low_coverage:
            recommendations.append(
                f"Increase required skills for {eco_id}: add {', '.join(data['missing_skills'][:5])}"
            )
        low_precision = [
            eco_id
            for eco_id, data in classification.get("per_template", {}).items()
            if data.get("precision", 1.0) < 0.7
        ]
        for eco_id in low_precision[:25]:
            recommendations.append(f"Review optional vs required skills for {eco_id} (precision < 0.7)")
        for eco_id in drift.get("at_risk_templates", [])[:25]:
            recommendations.append(f"Template {eco_id} shows drift; refresh with latest postings")
        payload = {"recommendations": recommendations, "count": len(recommendations)}
        self.metrics["recommendations"] = payload
        return payload

    def generateValidationReport(self) -> Dict[str, Any]:
        report = {
            "skill_coverage": self.validateSkillCoverage(),
            "yoe_accuracy": self.validateYoEAccuracy(),
            "skill_classification": self.validateSkillClassification(),
            "regional_accuracy": self.validateRegionalAccuracy(),
            "drift": self.detectTemplateDrift(),
            "quality_score": self.calculateTemplateQualityScore(),
            "recommendations": self.generateImprovementRecommendations(),
            "benchmark_passed": self.metrics["quality_score"]["score"] >= self.config.benchmark_quality_score,
        }
        self._write_outputs(report)
        return report

    def _write_outputs(self, report: Mapping[str, Any]) -> None:
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.config.output_dir / "template_accuracy_report.json"
        with path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        logger.info("Wrote template accuracy report to %s", path)


__all__ = ["TemplateAccuracyValidator", "TemplateAccuracyValidatorConfig"]
