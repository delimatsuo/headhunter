"""Comprehensive clustering validation for ECO quality assurance."""

from __future__ import annotations

import json
import logging
import math
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

try:  # Optional dependencies for advanced metrics
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - numpy not required at runtime
    np = None  # type: ignore

try:  # YAML support is optional
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )


@dataclass
class ClusteringValidatorConfig:
    gold_standard_path: Path
    cluster_results_path: Path
    output_dir: Path = Path("reports/eco_quality")
    alias_dump_path: Optional[Path] = None
    benchmarks_path: Optional[Path] = None
    quality_gate_threshold: float = 0.85
    min_support: int = 10
    quality_thresholds: Sequence[float] = field(default_factory=lambda: [0.6, 0.7, 0.8, 0.9])
    significance_level: float = 0.05


def _load_structured_file(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as handle:
        data = handle.read()
    if path.suffix.lower() in {".yaml", ".yml"}:
        if not yaml:  # pragma: no cover - optional dependency
            raise ImportError("PyYAML not installed, unable to parse YAML gold standard")
        return yaml.safe_load(data)
    return json.loads(data)


def _wilson_interval(p: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    denominator = 1 + z ** 2 / n
    centre = p + z ** 2 / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z ** 2 / (4 * n)) / n)
    lower = (centre - margin) / denominator
    upper = (centre + margin) / denominator
    return max(0.0, lower), min(1.0, upper)


class ClusteringValidator:
    """Validates ECO clustering outputs against curated benchmarks."""

    def __init__(self, config: ClusteringValidatorConfig) -> None:
        self.config = config
        self.gold_standard: List[Mapping[str, Any]] = []
        self.cluster_data: Mapping[str, Any] = {}
        self.predicted_lookup: Dict[str, Mapping[str, Any]] = {}
        self.alias_metadata: Dict[str, Mapping[str, Any]] = {}
        self.benchmarks: Mapping[str, Any] = {}
        self.metrics: Dict[str, Any] = {}
        self._load_inputs()

    # ------------------------------------------------------------------
    # Data loading helpers
    # ------------------------------------------------------------------
    def _load_inputs(self) -> None:
        logger.info("Loading gold standard data from %s", self.config.gold_standard_path)
        gs_payload = _load_structured_file(self.config.gold_standard_path)
        self.gold_standard = list(gs_payload.get("records", gs_payload if isinstance(gs_payload, list) else []))

        logger.info("Loading clustering results from %s", self.config.cluster_results_path)
        cluster_payload = _load_structured_file(self.config.cluster_results_path)
        self.cluster_data = cluster_payload.get("clusters", cluster_payload)

        self.predicted_lookup = self._build_prediction_lookup(self.cluster_data)

        if self.config.alias_dump_path and self.config.alias_dump_path.exists():
            alias_payload = _load_structured_file(self.config.alias_dump_path)
            self.alias_metadata = {entry.get("normalized_alias", entry.get("alias")): entry for entry in alias_payload}

        if self.config.benchmarks_path and self.config.benchmarks_path.exists():
            self.benchmarks = _load_structured_file(self.config.benchmarks_path)

    def _build_prediction_lookup(self, clusters: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
        lookup: Dict[str, Mapping[str, Any]] = {}
        for cluster_id, entry in clusters.items():
            eco_id = entry.get("eco_id") or entry.get("canonical_eco_id") or entry.get("eco")
            aliases = entry.get("aliases") or entry.get("titles") or []
            for alias_entry in aliases:
                if isinstance(alias_entry, Mapping):
                    normalized = alias_entry.get("normalized") or alias_entry.get("normalized_alias") or alias_entry.get("alias")
                    confidence = float(alias_entry.get("confidence", 0.0))
                else:
                    normalized = str(alias_entry)
                    confidence = 0.0
                if not normalized:
                    continue
                lookup[normalized.lower()] = {
                    "alias": alias_entry,
                    "eco_id": eco_id,
                    "cluster_id": cluster_id,
                    "confidence": confidence,
                }
        logger.info("Built prediction lookup for %s aliases", len(lookup))
        return lookup

    # ------------------------------------------------------------------
    # Validation methods requested in implementation plan
    # ------------------------------------------------------------------
    def validateOccupationMappings(self) -> Dict[str, Any]:
        tp = fp = fn = 0
        mismatches: List[Dict[str, Any]] = []
        for entry in self.gold_standard:
            alias = str(entry.get("alias") or entry.get("normalized_alias") or "").lower()
            expected = entry.get("eco_id") or entry.get("expected_eco_id")
            if not alias or not expected:
                continue
            predicted = self.predicted_lookup.get(alias)
            if predicted and predicted.get("eco_id") == expected:
                tp += 1
            elif predicted:
                fp += 1
                mismatches.append(
                    {
                        "alias": alias,
                        "expected": expected,
                        "predicted": predicted.get("eco_id"),
                        "cluster_id": predicted.get("cluster_id"),
                        "confidence": predicted.get("confidence"),
                    }
                )
            else:
                fn += 1
                mismatches.append(
                    {
                        "alias": alias,
                        "expected": expected,
                        "predicted": None,
                        "cluster_id": None,
                        "confidence": None,
                    }
                )
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        lower_p, upper_p = _wilson_interval(precision, tp + fp)
        lower_r, upper_r = _wilson_interval(recall, tp + fn)
        quality_gate = f1 >= self.config.quality_gate_threshold
        payload = {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "precision_interval": [round(lower_p, 4), round(upper_p, 4)],
            "recall_interval": [round(lower_r, 4), round(upper_r, 4)],
            "quality_gate_passed": quality_gate,
            "mismatches": mismatches[:200],  # cap for report readability
        }
        logger.info(
            "Occupation mapping validation complete: precision=%.4f recall=%.4f f1=%.4f (gate:%s)",
            precision,
            recall,
            f1,
            quality_gate,
        )
        self.metrics["occupation_validation"] = payload
        return payload

    def validateClusterCoherence(self) -> Dict[str, Any]:
        coherences: List[float] = []
        density: List[float] = []
        for entry in self.cluster_data.values():
            if np is not None and entry.get("embeddings"):
                vectors = np.array(entry["embeddings"], dtype=float)
                if vectors.shape[0] > 1:
                    centroid = np.mean(vectors, axis=0)
                    distances = np.linalg.norm(vectors - centroid, axis=1)
                    coherences.append(float(np.exp(-distances.mean())))
                    density.append(float(1.0 / (1.0 + distances.std())))
            elif entry.get("similarities"):
                sims = [float(val) for val in entry["similarities"] if val is not None]
                if sims:
                    coherences.append(sum(sims) / len(sims))
                    density.append(statistics.pstdev(sims) if len(sims) > 1 else 0.0)
        coherence_mean = statistics.mean(coherences) if coherences else 0.0
        coherence_p10 = statistics.quantiles(coherences, n=10)[0] if len(coherences) >= 10 else min(coherences) if coherences else 0.0
        payload = {
            "cluster_count": len(self.cluster_data),
            "coherence_mean": round(coherence_mean, 4),
            "coherence_p10": round(coherence_p10, 4),
            "density_mean": round(statistics.mean(density), 4) if density else 0.0,
        }
        logger.info("Cluster coherence mean=%.4f p10=%.4f", coherence_mean, coherence_p10)
        self.metrics["cluster_coherence"] = payload
        return payload

    def validateAliasQuality(self) -> Dict[str, Any]:
        low_confidence: List[Dict[str, Any]] = []
        alias_confidences: List[float] = []
        for alias, predicted in self.predicted_lookup.items():
            confidence = float(predicted.get("confidence", 0.0))
            alias_confidences.append(confidence)
            if confidence < 0.5:
                origin = self.alias_metadata.get(alias, {}) if self.alias_metadata else {}
                low_confidence.append(
                    {
                        "alias": alias,
                        "eco_id": predicted.get("eco_id"),
                        "confidence": confidence,
                        "source": origin.get("source"),
                    }
                )
        alias_confidences.sort()
        payload = {
            "count": len(alias_confidences),
            "mean": round(statistics.mean(alias_confidences), 4) if alias_confidences else 0.0,
            "p10": round(alias_confidences[int(0.1 * len(alias_confidences))], 4) if alias_confidences else 0.0,
            "p90": round(alias_confidences[int(0.9 * len(alias_confidences))], 4) if alias_confidences else 0.0,
            "low_confidence_samples": low_confidence[:100],
        }
        logger.info(
            "Alias quality distribution mean=%.4f p10=%.4f", payload["mean"], payload["p10"]
        )
        self.metrics["alias_quality"] = payload
        return payload

    def validateCrossValidation(self) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        total_records = len(self.predicted_lookup)
        baseline_metrics = self.metrics.get("occupation_validation")
        for threshold in self.config.quality_thresholds:
            filtered_predictions = {
                alias: info
                for alias, info in self.predicted_lookup.items()
                if info.get("confidence", 0.0) >= threshold
            }
            temp_lookup = self.predicted_lookup
            self.predicted_lookup = filtered_predictions
            metrics = self.validateOccupationMappings()
            metrics["coverage"] = round(len(filtered_predictions) / total_records, 4) if total_records else 0.0
            results[str(threshold)] = metrics
            self.predicted_lookup = temp_lookup
            if baseline_metrics is not None:
                self.metrics["occupation_validation"] = baseline_metrics
            else:
                self.metrics.pop("occupation_validation", None)
        self.metrics["threshold_scenarios"] = results
        return results

    def generateValidationReport(self) -> Dict[str, Any]:
        occupation_metrics = self.metrics.get("occupation_validation") or self.validateOccupationMappings()
        coherence_metrics = self.metrics.get("cluster_coherence") or self.validateClusterCoherence()
        alias_metrics = self.metrics.get("alias_quality") or self.validateAliasQuality()
        threshold_metrics = self.metrics.get("threshold_scenarios") or self.validateCrossValidation()

        report = {
            "occupation_metrics": occupation_metrics,
            "cluster_coherence": coherence_metrics,
            "alias_quality": alias_metrics,
            "threshold_metrics": threshold_metrics,
            "quality_gate_passed": occupation_metrics.get("quality_gate_passed", False)
            and coherence_metrics.get("coherence_mean", 0.0) >= 0.6,
            "benchmark_comparison": self._benchmark_comparison(occupation_metrics, alias_metrics, coherence_metrics),
        }

        self._write_outputs(report)
        return report

    # ------------------------------------------------------------------
    # Supporting helpers
    # ------------------------------------------------------------------
    def _benchmark_comparison(
        self,
        occupation_metrics: Mapping[str, Any],
        alias_metrics: Mapping[str, Any],
        coherence_metrics: Mapping[str, Any],
    ) -> Dict[str, Any]:
        if not self.benchmarks:
            return {}
        comparison: Dict[str, Any] = {}
        for metric_name, current_value in (
            ("precision", occupation_metrics.get("precision")),
            ("recall", occupation_metrics.get("recall")),
            ("f1", occupation_metrics.get("f1")),
            ("alias_mean", alias_metrics.get("mean")),
            ("coherence_mean", coherence_metrics.get("coherence_mean")),
        ):
            benchmark_value = self.benchmarks.get(metric_name)
            if benchmark_value is None or current_value is None:
                continue
            comparison[metric_name] = {
                "current": current_value,
                "benchmark": benchmark_value,
                "delta": round(float(current_value) - float(benchmark_value), 4),
            }
        return comparison

    def _write_outputs(self, report: Mapping[str, Any]) -> None:
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.config.output_dir / "clustering_validation_report.json"
        with report_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        logger.info("Wrote clustering validation report to %s", report_path)

        diagnostics_path = self.config.output_dir / "clustering_validation_diagnostics.json"
        diagnostics_payload = {
            "mismatches": self.metrics.get("occupation_validation", {}).get("mismatches", []),
            "alias_low_confidence": self.metrics.get("alias_quality", {}).get("low_confidence_samples", []),
        }
        with diagnostics_path.open("w", encoding="utf-8") as handle:
            json.dump(diagnostics_payload, handle, ensure_ascii=False, indent=2)

        if self.metrics.get("threshold_scenarios"):
            scenarios_path = self.config.output_dir / "clustering_threshold_scenarios.json"
            with scenarios_path.open("w", encoding="utf-8") as handle:
                json.dump(self.metrics["threshold_scenarios"], handle, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Incremental validation support
    # ------------------------------------------------------------------
    def run_incremental_validation(
        self,
        updated_clusters: Mapping[str, Any],
    ) -> Dict[str, Any]:
        logger.info("Running incremental clustering validation on %s clusters", len(updated_clusters))
        previous_lookup = self.predicted_lookup
        self.predicted_lookup = self._build_prediction_lookup(updated_clusters)
        metrics = self.validateOccupationMappings()
        self.predicted_lookup = previous_lookup
        delta = {
            "previous_f1": self.metrics.get("occupation_validation", {}).get("f1"),
            "incremental_f1": metrics.get("f1"),
        }
        logger.info(
            "Incremental validation delta previous=%.4f new=%.4f",
            delta.get("previous_f1"),
            delta.get("incremental_f1"),
        )
        return delta


__all__ = ["ClusteringValidator", "ClusteringValidatorConfig"]
