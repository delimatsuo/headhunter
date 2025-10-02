"""Job title clustering engine for Brazilian job titles."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, Tuple

import importlib
import numpy as np
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import davies_bouldin_score, silhouette_score

import matplotlib.pyplot as plt
import seaborn as sns

logger = logging.getLogger(__name__)

try:
    from scripts import clustering_dao
except ModuleNotFoundError:  # pragma: no cover - optional during certain tests
    clustering_dao = None  # type: ignore[assignment]


_DEFAULT_DBSCAN_EPS = 0.4
_DEFAULT_DBSCAN_MIN_SAMPLES = 5


@dataclass
class ClusteringConfig:
    method: str = "dbscan"
    chunk_type: str = "job_title"
    eps: float = _DEFAULT_DBSCAN_EPS
    min_samples: int = _DEFAULT_DBSCAN_MIN_SAMPLES
    k_range: Tuple[int, int] = (5, 30)
    output_path: Optional[Path] = None
    visualization_dir: Optional[Path] = None
    category_overrides: Mapping[str, Dict[str, Any]] = field(default_factory=dict)
    default_category: str = "default"


class VectorSource(Protocol):
    def list_embeddings(self, chunk_type: str) -> List[Dict[str, Any]]:  # pragma: no cover - protocol definition
        ...


class PgVectorVectorSource:
    """Load vectors from the pgvector adapter."""

    def __init__(self, store: Optional[Any] = None) -> None:
        self._store = store or self._load_store()

    @staticmethod
    def _load_store() -> Any:
        try:
            module = importlib.import_module("scripts.pgvector_store_adapter")
        except ModuleNotFoundError:
            module = importlib.import_module("scripts.pgvector_store")
        if hasattr(module, "PgVectorStoreAdapter"):
            return module.PgVectorStoreAdapter()
        if hasattr(module, "get_store"):
            return module.get_store()
        raise AttributeError("Pgvector store adapter not found")

    def list_embeddings(self, chunk_type: str) -> List[Dict[str, Any]]:
        if not hasattr(self._store, "list_embeddings"):
            raise AttributeError("Configured store does not expose list_embeddings")
        return self._store.list_embeddings(chunk_type=chunk_type)


class JobTitleClusteringEngine:
    """Clusters job title embeddings using pgvector store data."""

    def __init__(self, config: ClusteringConfig, vector_source: Optional[VectorSource] = None) -> None:
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
        self.config = config
        self.vector_source = vector_source or PgVectorVectorSource()
        self.normalizer = self._load_normalizer()
        self._category_patterns = {
            name: [re.compile(pattern, re.IGNORECASE) for pattern in options.get("patterns", [])]
            for name, options in self.config.category_overrides.items()
        }
        self._category_keywords = {
            name: [keyword.lower() for keyword in options.get("keywords", [])]
            for name, options in self.config.category_overrides.items()
        }
        logger.debug("Initialized clustering engine with config %s", config)

    def _load_normalizer(self) -> Any:
        module = importlib.import_module("scripts.eco_title_normalizer")
        if hasattr(module, "EcoTitleNormalizer"):
            return module.EcoTitleNormalizer()
        if hasattr(module, "BrazilianPortugueseNormalizer"):
            return module.BrazilianPortugueseNormalizer()
        return None

    def run(self) -> Dict[str, Any]:
        embeddings, metadata = self._load_embeddings()
        logger.info("Loaded %d embeddings for clustering", len(embeddings))
        if embeddings.size == 0:
            raise RuntimeError("No embeddings available for clustering")
        categories = self._categorize_metadata(metadata)
        category_groups = self._group_indices_by_category(categories)
        global_labels = np.full(len(metadata), -1, dtype=int)
        clusters: Dict[str, Dict[str, Any]] = {}
        summary_entries: List[Mapping[str, Any]] = []
        category_metrics: Dict[str, Any] = {}
        cluster_counter = 0
        for category, indices in category_groups.items():
            subset_embeddings = embeddings[indices]
            if subset_embeddings.size == 0:
                continue
            subset_metadata = [metadata[i] for i in indices]
            category_config = self._derive_category_config(category)
            labels, model = self._run_category_clustering(subset_embeddings, category_config)
            metrics = self._calculate_metrics(
                subset_embeddings,
                labels,
                model,
                method=category_config["method"],
                parameters=category_config,
            )
            category_metrics[category] = metrics
            label_mapping: Dict[int, int] = {}
            for label in np.unique(labels):
                if label < 0:
                    continue
                cluster_counter += 1
                label_mapping[int(label)] = cluster_counter
            for local_idx, label in enumerate(labels):
                if label >= 0:
                    global_labels[indices[local_idx]] = label_mapping[int(label)]
            category_clusters, category_summary = self._build_cluster_payload(
                labels,
                subset_metadata,
                metrics,
                category,
                label_mapping,
            )
            clusters.update(category_clusters)
            summary_entries.extend(category_summary)
        metrics = self._calculate_metrics(
            embeddings,
            global_labels,
            None,
            method=self.config.method,
            parameters={
                "eps": self.config.eps,
                "min_samples": self.config.min_samples,
                "k_range": self.config.k_range,
            },
        )
        metrics["category_breakdown"] = category_metrics
        summary = {
            "method": self.config.method,
            "metrics": metrics,
            "clusters": clusters,
        }
        summary["summary"] = summary_entries
        self._persist_cluster_assignments(clusters, metrics)
        if self.config.output_path:
            self._write_output(summary)
        if self.config.visualization_dir:
            self._generate_visualizations(embeddings, global_labels, summary_entries)
        return summary

    def _load_embeddings(self) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        records = self.vector_source.list_embeddings(chunk_type=self.config.chunk_type)
        vectors = []
        metadata: List[Dict[str, Any]] = []
        for record in records:
            vector = record.get("embedding") or record.get("vector")
            if vector is None:
                continue
            vectors.append(np.array(vector, dtype="float32"))
            metadata.append(
                {
                    "chunk_id": record.get("chunk_id") or record.get("id"),
                    "text": record.get("text"),
                    "metadata": record.get("metadata", {}),
                }
            )
        return np.vstack(vectors), metadata

    def _categorize_metadata(self, metadata: Sequence[Mapping[str, Any]]) -> List[str]:
        categories: List[str] = []
        for info in metadata:
            categories.append(self._detect_category(info))
        return categories

    def _detect_category(self, info: Mapping[str, Any]) -> str:
        meta = info.get("metadata") or {}
        base = str(meta.get("normalized_title") or info.get("text") or "")
        normalized_text = self._normalize_text(base).lower()
        folded_text = self._strip_diacritics(normalized_text).lower()
        search_values = {normalized_text, folded_text}
        for category, patterns in self._category_patterns.items():
            if any(pattern.search(value) for value in search_values for pattern in patterns):
                return category
        for category, keywords in self._category_keywords.items():
            if any(keyword and keyword in value for value in search_values for keyword in keywords):
                return category
        return self.config.default_category

    def _normalize_text(self, text: str) -> str:
        if not text:
            return ""
        if self.normalizer:
            if hasattr(self.normalizer, "normalize"):
                return str(self.normalizer.normalize(text))
            if hasattr(self.normalizer, "normalize_title"):
                return str(self.normalizer.normalize_title(text))
        return text.lower()

    @staticmethod
    def _strip_diacritics(text: str) -> str:
        if not text:
            return ""
        normalized = unicodedata.normalize("NFD", text)
        return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")

    @staticmethod
    def _group_indices_by_category(categories: Sequence[str]) -> Dict[str, List[int]]:
        groups: Dict[str, List[int]] = {}
        for idx, category in enumerate(categories):
            groups.setdefault(category, []).append(idx)
        return groups

    def _derive_category_config(self, category: str) -> Dict[str, Any]:
        override = dict(self.config.category_overrides.get(category, {}))
        method = override.get("method", self.config.method)
        eps = override.get("eps", self.config.eps)
        min_samples = override.get("min_samples", self.config.min_samples)
        k_range = tuple(override.get("k_range", self.config.k_range))
        return {
            "category": category,
            "method": method,
            "eps": eps,
            "min_samples": min_samples,
            "k_range": k_range,
        }

    def _run_category_clustering(self, embeddings: np.ndarray, config: Mapping[str, Any]) -> Tuple[np.ndarray, Any]:
        method = config.get("method", self.config.method)
        if method == "dbscan":
            return self._run_dbscan(embeddings, eps=config.get("eps"), min_samples=config.get("min_samples"))
        if method == "kmeans":
            return self._run_kmeans(embeddings, k_range=tuple(config.get("k_range", self.config.k_range)))
        raise ValueError(f"Unsupported clustering method {method}")

    def _run_dbscan(self, embeddings: np.ndarray, eps: Optional[float] = None, min_samples: Optional[int] = None) -> Tuple[np.ndarray, DBSCAN]:
        eps_value = eps if eps is not None else self.config.eps
        min_samples_value = min_samples if min_samples is not None else self.config.min_samples
        logger.info("Running DBSCAN with eps=%.3f, min_samples=%d", eps_value, min_samples_value)
        model = DBSCAN(eps=eps_value, min_samples=min_samples_value, metric="cosine")
        labels = model.fit_predict(embeddings)
        return labels, model

    def _run_kmeans(self, embeddings: np.ndarray, k: Optional[int] = None, k_range: Optional[Tuple[int, int]] = None) -> Tuple[np.ndarray, KMeans]:
        if k is None:
            optimal_k = self._find_optimal_k(embeddings, k_range or self.config.k_range)
        else:
            optimal_k = k
        logger.info("Running KMeans with k=%d", optimal_k)
        model = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
        labels = model.fit_predict(embeddings)
        return labels, model

    def _find_optimal_k(self, embeddings: np.ndarray, k_range: Tuple[int, int]) -> int:
        inertias = []
        silhouettes = []
        start, end = k_range
        for k in range(start, end + 1):
            model = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = model.fit_predict(embeddings)
            inertias.append(model.inertia_)
            try:
                silhouettes.append(silhouette_score(embeddings, labels, metric="cosine"))
            except ValueError:
                silhouettes.append(-1)
        optimal_by_silhouette = (silhouettes.index(max(silhouettes)) + start) if silhouettes else start
        elbow_k = self._detect_elbow(inertias, start)
        logger.info("KMeans selection: silhouette=%d, elbow=%d", optimal_by_silhouette, elbow_k)
        return optimal_by_silhouette if silhouettes[optimal_by_silhouette - start] >= 0 else elbow_k

    @staticmethod
    def _detect_elbow(inertias: Sequence[float], start: int) -> int:
        if len(inertias) < 3:
            return start
        deltas = np.diff(inertias)
        second_deltas = np.diff(deltas)
        if not len(second_deltas):
            return start
        elbow_index = int(np.argmin(second_deltas)) + start + 1
        return elbow_index

    def _calculate_metrics(
        self,
        embeddings: np.ndarray,
        labels: np.ndarray,
        model: Any,
        *,
        method: Optional[str] = None,
        parameters: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not isinstance(labels, np.ndarray):
            labels = np.array(labels)
        mask = labels >= 0
        cluster_count = int(np.unique(labels[mask]).size) if mask.any() else 0
        metrics: Dict[str, Any] = {
            "method": method or self.config.method,
            "parameters": parameters or {
                "eps": self.config.eps,
                "min_samples": self.config.min_samples,
                "k_range": self.config.k_range,
            },
            "cluster_count": cluster_count,
            "noise_count": int((labels < 0).sum()),
            "silhouette_score": None,
            "davies_bouldin_index": None,
        }
        if mask.any() and cluster_count > 1:
            try:
                metrics["silhouette_score"] = float(silhouette_score(embeddings[mask], labels[mask], metric="cosine"))
            except ValueError:
                metrics["silhouette_score"] = None
            try:
                metrics["davies_bouldin_index"] = float(davies_bouldin_score(embeddings[mask], labels[mask]))
            except ValueError:
                metrics["davies_bouldin_index"] = None
        if model is not None and hasattr(model, "inertia_"):
            metrics["inertia"] = float(model.inertia_)
        return metrics

    def _build_cluster_payload(
        self,
        labels: np.ndarray,
        metadata: Sequence[Mapping[str, Any]],
        metrics: Mapping[str, Any],
        category: str,
        label_mapping: Mapping[int, int],
    ) -> Tuple[Dict[str, Any], List[Mapping[str, Any]]]:
        clusters: Dict[str, Dict[str, Any]] = {}
        for label, info in zip(labels, metadata):
            local_label = int(label)
            key: str
            cluster_id: Any
            if local_label < 0:
                key = f"{category}:noise"
                cluster_id = -1
            else:
                cluster_id = label_mapping.get(local_label, local_label)
                key = f"{category}:{cluster_id}"
            entry = clusters.setdefault(
                key,
                {
                    "cluster_key": key,
                    "cluster_id": cluster_id,
                    "category": category,
                    "local_label": local_label,
                    "method": metrics.get("method", self.config.method),
                    "titles": [],
                    "representative": None,
                    "frequency": 0,
                    "sources": {},
                },
            )
            entry["titles"].append(
                {
                    "chunk_id": info.get("chunk_id"),
                    "text": info.get("text"),
                    "metadata": info.get("metadata"),
                }
            )
            freq = info.get("metadata", {}).get("frequency", 1)
            entry["frequency"] += freq
            for source, count in (info.get("metadata", {}).get("sources", {}) or {}).items():
                entry["sources"][source] = entry["sources"].get(source, 0) + count
        for cluster in clusters.values():
            cluster["representative"] = self._choose_representative(cluster["titles"])
        return clusters, self._summarize_clusters(clusters)

    def _choose_representative(self, titles: Sequence[Mapping[str, Any]]) -> Optional[Mapping[str, Any]]:
        if not titles:
            return None
        sorted_titles = sorted(
            titles,
            key=lambda entry: entry.get("metadata", {}).get("frequency", 0),
            reverse=True,
        )
        return sorted_titles[0]

    def _summarize_clusters(self, clusters: Mapping[str, Mapping[str, Any]]) -> List[Mapping[str, Any]]:
        summary = []
        for cluster_key, info in clusters.items():
            titles = [item.get("text") for item in info.get("titles", []) if item.get("text")]
            summary.append(
                {
                    "cluster_key": cluster_key,
                    "cluster_id": info.get("cluster_id"),
                    "category": info.get("category"),
                    "representative": info.get("representative"),
                    "title_count": len(titles),
                    "frequency": info.get("frequency", 0),
                    "samples": titles[:5],
                }
            )
        summary.sort(key=lambda item: item["frequency"], reverse=True)
        return summary

    def _persist_cluster_assignments(self, clusters: Mapping[str, Mapping[str, Any]], metrics: Mapping[str, Any]) -> None:
        if clustering_dao is None or not hasattr(clustering_dao, "bulk_upsert_title_clusters"):
            return
        entries: List[Dict[str, Any]] = []
        default_quality = metrics.get("silhouette_score")
        for info in clusters.values():
            cluster_id = info.get("cluster_id")
            method = info.get("method", self.config.method)
            numeric_cluster_id: Any = cluster_id
            if isinstance(cluster_id, (int, np.integer)):
                if int(cluster_id) < 0:
                    continue
                numeric_cluster_id = int(cluster_id)
            else:
                try:
                    numeric_cluster_id = int(cluster_id)
                    if numeric_cluster_id < 0:
                        continue
                except (TypeError, ValueError):
                    numeric_cluster_id = cluster_id
            for title in info.get("titles", []):
                metadata = title.get("metadata") or {}
                normalized = metadata.get("normalized_title")
                if not normalized:
                    continue
                entries.append(
                    {
                        "normalized_title": normalized,
                        "cluster_id": numeric_cluster_id,
                        "method": method,
                        "quality_score": default_quality,
                        "metadata": {
                            "category": info.get("category"),
                            "frequency": info.get("frequency"),
                            "sources": info.get("sources"),
                            "representative": info.get("representative"),
                            "cluster_key": info.get("cluster_key"),
                        },
                    }
                )
        if not entries:
            return
        try:
            self._run_async(lambda: clustering_dao.bulk_upsert_title_clusters(entries))
        except Exception as exc:  # pragma: no cover - database optional in tests
            logger.warning("Failed to persist cluster assignments: %s", exc)

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

    def _write_output(self, payload: Mapping[str, Any]) -> None:
        self.config.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config.output_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        logger.info("Wrote clustering output to %s", self.config.output_path)

    def _generate_visualizations(self, embeddings: np.ndarray, labels: np.ndarray, summary: Sequence[Mapping[str, Any]]) -> None:
        self.config.visualization_dir.mkdir(parents=True, exist_ok=True)
        palette = sns.color_palette("husl", n_colors=len(set(labels)))
        try:
            import umap

            reducer = umap.UMAP(random_state=42)
            embedding_2d = reducer.fit_transform(embeddings)
        except Exception:  # pragma: no cover - visualization fallback
            logger.warning("UMAP not available, falling back to PCA visualization")
            from sklearn.decomposition import PCA

            reducer = PCA(n_components=2, random_state=42)
            embedding_2d = reducer.fit_transform(embeddings)
        plt.figure(figsize=(12, 8))
        sns.scatterplot(x=embedding_2d[:, 0], y=embedding_2d[:, 1], hue=labels, palette=palette, legend=False, s=10)
        plt.title("Brazilian Job Title Clusters")
        plt.tight_layout()
        path = self.config.visualization_dir / "clusters.png"
        plt.savefig(path)
        plt.close()
        logger.info("Saved cluster visualization to %s", path)
        summary_path = self.config.visualization_dir / "cluster_summary.json"
        with summary_path.open("w", encoding="utf-8") as handle:
            json.dump(list(summary), handle, ensure_ascii=False, indent=2)
        logger.info("Saved cluster summary to %s", summary_path)


def _parse_args(argv: Optional[Sequence[str]] = None) -> Any:
    import argparse

    parser = argparse.ArgumentParser(description="Cluster Brazilian job title embeddings")
    parser.add_argument("--method", choices=["dbscan", "kmeans"], default="dbscan")
    parser.add_argument("--chunk-type", default="job_title")
    parser.add_argument("--eps", type=float, default=_DEFAULT_DBSCAN_EPS)
    parser.add_argument("--min-samples", type=int, default=_DEFAULT_DBSCAN_MIN_SAMPLES)
    parser.add_argument("--k-start", type=int, default=5)
    parser.add_argument("--k-end", type=int, default=30)
    parser.add_argument("--output", type=str)
    parser.add_argument("--viz-dir", type=str)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = _parse_args(argv)
    config = ClusteringConfig(
        method=args.method,
        chunk_type=args.chunk_type,
        eps=args.eps,
        min_samples=args.min_samples,
        k_range=(args.k_start, args.k_end),
        output_path=Path(args.output) if args.output else None,
        visualization_dir=Path(args.viz_dir) if args.viz_dir else None,
    )
    engine = JobTitleClusteringEngine(config)
    engine.run()


if __name__ == "__main__":
    main()
