"""Validation tooling for Brazilian clustering pipeline quality assurance."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score

from scripts.job_title_clustering_engine import ClusteringConfig, JobTitleClusteringEngine
from scripts.eco_occupation_mapper import EcoOccupationMapper, OccupationMapperConfig

logger = logging.getLogger(__name__)


@dataclass
class ValidationConfig:
    clusters_path: Path
    occupation_path: Optional[Path] = None
    chunk_type: str = "job_title"
    report_path: Optional[Path] = None
    visualization_dir: Optional[Path] = None


class ClusteringQualityValidator:
    """Evaluates quality metrics for clustering outputs."""

    def __init__(self, config: ValidationConfig) -> None:
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
        self.config = config

    def run(self) -> Dict[str, Any]:
        clusters = self._load_clusters()
        embeddings, labels = self._load_embeddings_and_labels(clusters)
        metrics = self._calculate_metrics(embeddings, labels)
        occupation_metrics, alias_confidences = self._evaluate_occupations()
        cluster_stats, cluster_sizes, cluster_frequencies = self._cluster_statistics(clusters)
        payload = {
            "cluster_metrics": metrics,
            "occupation_metrics": occupation_metrics,
            "recommendations": self._generate_recommendations(metrics, occupation_metrics),
            "cluster_statistics": cluster_stats,
        }
        if self.config.report_path:
            self.config.report_path.parent.mkdir(parents=True, exist_ok=True)
            with self.config.report_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            logger.info("Wrote clustering validation report to %s", self.config.report_path)
        if self.config.visualization_dir:
            self._generate_visualizations(cluster_stats, alias_confidences, cluster_sizes, cluster_frequencies)
        return payload

    def _load_clusters(self) -> Mapping[str, Any]:
        with self.config.clusters_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _load_embeddings_and_labels(self, clusters: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
        config = ClusteringConfig(method=clusters.get("method", "dbscan"), chunk_type=self.config.chunk_type)
        engine = JobTitleClusteringEngine(config)
        embeddings, metadata = engine._load_embeddings()  # type: ignore[attr-defined]
        cluster_map = clusters.get("clusters", {})
        label_lookup: Dict[str, int] = {}
        for cluster_id, item in cluster_map.items():
            cid = int(cluster_id)
            representative = item.get("representative", {})
            normalized_rep = (representative.get("metadata") or {}).get("normalized_title")
            if normalized_rep:
                label_lookup[normalized_rep] = cid
            for title in item.get("titles", []):
                normalized = (title.get("metadata") or {}).get("normalized_title")
                if normalized:
                    label_lookup[normalized] = cid
        labels = []
        for info in metadata:
            normalized = info.get("metadata", {}).get("normalized_title")
            labels.append(label_lookup.get(normalized, -1))
        return embeddings, np.array(labels)

    def _calculate_metrics(self, embeddings: np.ndarray, labels: np.ndarray) -> Dict[str, Any]:
        mask = labels >= 0
        if not mask.any():
            logger.warning("No valid cluster labels for metric computation")
            return {"clusters": 0, "silhouette": None, "davies_bouldin": None}
        filtered_embeddings = embeddings[mask]
        filtered_labels = labels[mask]
        unique_labels = np.unique(filtered_labels)
        metrics = {
            "clusters": int(unique_labels.size),
            "silhouette": None,
            "davies_bouldin": None,
            "calinski_harabasz": None,
        }
        if unique_labels.size > 1 and filtered_embeddings.shape[0] > unique_labels.size:
            metrics["silhouette"] = float(silhouette_score(filtered_embeddings, filtered_labels, metric="cosine"))
            metrics["davies_bouldin"] = float(davies_bouldin_score(filtered_embeddings, filtered_labels))
            metrics["calinski_harabasz"] = float(calinski_harabasz_score(filtered_embeddings, filtered_labels))
        logger.info("Cluster metrics computed %s", metrics)
        return metrics

    def _evaluate_occupations(self) -> tuple[Dict[str, Any], List[float]]:
        if not self.config.occupation_path or not self.config.occupation_path.exists():
            return {}, []
        mapper_config = OccupationMapperConfig(clusters_path=self.config.clusters_path)
        mapper = EcoOccupationMapper(mapper_config)
        payload = mapper.run()
        alias_confidences = [alias["confidence"] for occupation in payload.get("occupations", []) for alias in occupation.get("aliases", [])]
        if not alias_confidences:
            metrics = {"occupations": len(payload.get("occupations", [])), "alias_confidence_mean": None}
        else:
            metrics = {
                "occupations": len(payload.get("occupations", [])),
                "alias_confidence_mean": float(np.mean(alias_confidences)),
                "alias_confidence_p10": float(np.percentile(alias_confidences, 10)),
                "alias_confidence_p90": float(np.percentile(alias_confidences, 90)),
            }
        return metrics, alias_confidences

    def _generate_recommendations(self, metrics: Mapping[str, Any], occupation_metrics: Mapping[str, Any]) -> Sequence[str]:
        recommendations = []
        silhouette = metrics.get("silhouette")
        if silhouette is not None and silhouette < 0.3:
            recommendations.append("Consider increasing DBSCAN eps or using KMeans for denser clustering")
        if metrics.get("clusters", 0) < 5:
            recommendations.append("Increase dataset coverage to capture more distinct occupations")
        if occupation_metrics.get("alias_confidence_mean") and occupation_metrics["alias_confidence_mean"] < 0.6:
            recommendations.append("Review alias normalization rules to improve confidence")
        if not recommendations:
            recommendations.append("Clustering quality meets configured thresholds")
        return recommendations

    def _cluster_statistics(
        self,
        clusters: Mapping[str, Any],
    ) -> tuple[Dict[str, Any], List[int], List[int]]:
        entries = clusters.get("clusters") or {}
        raw_sizes = [len(info.get("titles", [])) for info in entries.values() if info.get("titles")]
        raw_frequencies = [info.get("frequency", 0) for info in entries.values() if info.get("frequency")]
        stats: Dict[str, Any] = {"cluster_count": len(entries)}
        if raw_sizes:
            stats.update(
                {
                    "mean_size": float(np.mean(raw_sizes)),
                    "median_size": float(np.median(raw_sizes)),
                    "p90_size": float(np.percentile(raw_sizes, 90)),
                }
            )
        if raw_frequencies:
            stats.update(
                {
                    "mean_frequency": float(np.mean(raw_frequencies)),
                    "median_frequency": float(np.median(raw_frequencies)),
                }
            )
        stats["sample_sizes"] = raw_sizes[:50]
        stats["sample_frequencies"] = raw_frequencies[:50]
        return stats, raw_sizes, raw_frequencies

    def _generate_visualizations(
        self,
        cluster_stats: Mapping[str, Any],
        alias_confidences: Sequence[float],
        cluster_sizes: Sequence[int],
        cluster_frequencies: Sequence[int],
    ) -> None:
        self.config.visualization_dir.mkdir(parents=True, exist_ok=True)
        try:
            import matplotlib.pyplot as plt
            import seaborn as sns
        except ImportError:  # pragma: no cover - optional dependency
            logger.warning("Visualization libraries not available; skipping charts")
            return
        if cluster_sizes:
            plt.figure(figsize=(8, 5))
            sns.histplot(cluster_sizes, bins=min(30, max(10, len(cluster_sizes) // 3)))
            plt.title("Cluster Size Distribution")
            plt.xlabel("Titles per cluster")
            plt.ylabel("Count")
            plt.tight_layout()
            path = self.config.visualization_dir / "cluster_sizes.png"
            plt.savefig(path)
            plt.close()
            logger.info("Saved cluster size histogram to %s", path)
        if alias_confidences:
            plt.figure(figsize=(8, 5))
            sns.kdeplot(alias_confidences, fill=True)
            plt.title("Alias Confidence Distribution")
            plt.xlabel("Confidence")
            plt.tight_layout()
            path = self.config.visualization_dir / "alias_confidence.png"
            plt.savefig(path)
            plt.close()
            logger.info("Saved alias confidence distribution to %s", path)
        supplemental_path = self.config.visualization_dir / "cluster_stats.json"
        with supplemental_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "cluster_stats": cluster_stats,
                    "alias_count": len(alias_confidences),
                    "mean_alias_confidence": float(np.mean(alias_confidences)) if alias_confidences else None,
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
        logger.info("Saved clustering statistics to %s", supplemental_path)


def _parse_args(argv: Optional[Sequence[str]] = None) -> Any:
    import argparse

    parser = argparse.ArgumentParser(description="Validate clustering quality for Brazilian job titles")
    parser.add_argument("clusters", help="Path to clustering output JSON")
    parser.add_argument("--occupations", type=str, help="Optional ECO occupation mapping JSON")
    parser.add_argument("--report", type=str, help="Where to output validation report JSON")
    parser.add_argument("--chunk-type", default="job_title")
    parser.add_argument("--viz-dir", type=str, help="Directory to store validation visualizations")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = _parse_args(argv)
    config = ValidationConfig(
        clusters_path=Path(args.clusters),
        occupation_path=Path(args.occupations) if args.occupations else None,
        chunk_type=args.chunk_type,
        report_path=Path(args.report) if args.report else None,
        visualization_dir=Path(args.viz_dir) if args.viz_dir else None,
    )
    validator = ClusteringQualityValidator(config)
    validator.run()


if __name__ == "__main__":
    main()
