"""Orchestration script for Brazilian job title clustering pipeline."""

from __future__ import annotations

import json
import logging
import importlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from scripts.brazilian_job_data_loader import BrazilianJobDataLoader, DataLoaderConfig
from scripts.brazilian_title_embedding_generator import BrazilianTitleEmbeddingGenerator, EmbeddingJobConfig
from scripts.job_title_clustering_engine import ClusteringConfig, JobTitleClusteringEngine
from scripts.career_progression_detector import CareerProgressionDetector, ProgressionConfig
from scripts.eco_occupation_mapper import EcoOccupationMapper, OccupationMapperConfig

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    data_sources: Sequence[Path]
    working_dir: Path
    run_data_loader: bool = True
    run_embeddings: bool = True
    run_clustering: bool = True
    run_progression: bool = True
    run_mapping: bool = True
    min_frequency: int = 2
    dbscan_eps: float = 0.42
    dbscan_min_samples: int = 5
    checkpoint_path: Optional[Path] = None
    resume_from: Optional[str] = None
    category: str = "GENERAL"
    chunk_type: str = "job_title"
    incremental: bool = True
    parallelism: int = 1
    enable_monitoring: bool = True


class BrazilianClusteringOrchestrator:
    """Coordinates the full Brazilian clustering pipeline."""

    def __init__(self, config: PipelineConfig) -> None:
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
        self.config = config
        self.state: Dict[str, Any] = {}
        self._monitoring_executor = ThreadPoolExecutor(max_workers=2)
        self._monitoring_hook = self._load_monitoring_hook()
        self._load_checkpoint()

    def run(self) -> Dict[str, Any]:
        logger.info("Starting Brazilian clustering pipeline orchestrator")
        stage_sequence = [
            ("data_loader", self.config.run_data_loader, self._run_data_loader),
            ("embeddings", self.config.run_embeddings, self._run_embeddings),
            ("clustering", self.config.run_clustering, self._run_clustering),
            ("progression", self.config.run_progression, self._run_progression),
            ("mapping", self.config.run_mapping, self._run_mapping),
        ]
        try:
            for stage_name, should_run, handler in stage_sequence:
                if not should_run:
                    logger.info("Skipping stage %s", stage_name)
                    self._emit_monitoring_event(stage_name, "skipped", {})
                    continue
                if self.config.resume_from and not self._should_execute_stage(stage_name):
                    logger.info("Resuming pipeline; skipping stage %s", stage_name)
                    self._emit_monitoring_event(stage_name, "skipped", {"resume": True})
                    continue
                logger.info("Running stage %s", stage_name)
                try:
                    handler()
                except Exception as exc:
                    self._emit_monitoring_event(stage_name, "failed", {"error": str(exc)})
                    raise
                else:
                    self._write_checkpoint(stage_name)
                    self._emit_monitoring_event(stage_name, "completed", self.state.get(stage_name, {}))
            logger.info("Brazilian clustering pipeline completed")
            self._emit_monitoring_event("pipeline", "completed", self.state)
            return self.state
        finally:
            self._monitoring_executor.shutdown(wait=True)

    def _stage_output_path(self, stage: str, filename: str) -> Path:
        path = self.config.working_dir / stage / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _run_data_loader(self) -> None:
        output_path = self._stage_output_path("data_loader", "normalized_titles.json")
        config = DataLoaderConfig(
            sources=self.config.data_sources,
            output_path=output_path,
            min_frequency=self.config.min_frequency,
            parallelism=self.config.parallelism,
        )
        loader = BrazilianJobDataLoader(config)
        result = loader.load()
        self.state["data_loader"] = {"output": str(output_path), "metrics": result.get("metrics")}

    def _run_embeddings(self) -> None:
        dataset_path = self._get_previous_output("data_loader", "normalized_titles.json")
        config = EmbeddingJobConfig(dataset_path=dataset_path, chunk_type=self.config.chunk_type, incremental=self.config.incremental)
        generator = BrazilianTitleEmbeddingGenerator(config)
        metrics = generator.run()
        self.state["embeddings"] = {"metrics": metrics}

    def _run_clustering(self) -> None:
        output_path = self._stage_output_path("clustering", "clusters.json")
        config = ClusteringConfig(
            method="dbscan",
            eps=self.config.dbscan_eps,
            min_samples=self.config.dbscan_min_samples,
            chunk_type=self.config.chunk_type,
            output_path=output_path,
        )
        engine = JobTitleClusteringEngine(config)
        payload = engine.run()
        self.state["clustering"] = {"output": str(output_path), "metrics": payload.get("metrics")}

    def _run_progression(self) -> None:
        cluster_path = self._get_previous_output("clustering", "clusters.json")
        output_path = self._stage_output_path("progression", "progressions.json")
        config = ProgressionConfig(cluster_results_path=cluster_path)
        detector = CareerProgressionDetector(config)
        payload = detector.run()
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        self.state["progression"] = {"output": str(output_path)}

    def _run_mapping(self) -> None:
        cluster_path = self._get_previous_output("clustering", "clusters.json")
        progression_path = self._get_previous_output("progression", "progressions.json", optional=True)
        output_path = self._stage_output_path("mapping", "eco_occupations.json")
        config = OccupationMapperConfig(
            clusters_path=cluster_path,
            progression_path=progression_path,
            output_path=output_path,
            category=self.config.category,
        )
        mapper = EcoOccupationMapper(config)
        payload = mapper.run()
        self.state["mapping"] = {"output": str(output_path), "count": len(payload.get("occupations", []))}

    def _get_previous_output(self, stage: str, filename: str, optional: bool = False) -> Path:
        stage_dir = self.config.working_dir / stage
        path = stage_dir / filename
        if not path.exists():
            if optional:
                return path
            raise FileNotFoundError(f"Expected output for stage {stage} at {path} not found")
        return path

    def _load_checkpoint(self) -> None:
        if not self.config.checkpoint_path or not self.config.checkpoint_path.exists():
            return
        with self.config.checkpoint_path.open("r", encoding="utf-8") as handle:
            self.state = json.load(handle)
        logger.info("Loaded checkpoint state from %s", self.config.checkpoint_path)

    def _write_checkpoint(self, stage: str) -> None:
        if not self.config.checkpoint_path:
            return
        with self.config.checkpoint_path.open("w", encoding="utf-8") as handle:
            json.dump(self.state, handle, ensure_ascii=False, indent=2)
        logger.info("Updated checkpoint after stage %s", stage)

    def _should_execute_stage(self, stage_name: str) -> bool:
        if not self.config.resume_from:
            return True
        stages = ["data_loader", "embeddings", "clustering", "progression", "mapping"]
        resume_index = stages.index(self.config.resume_from)
        return stages.index(stage_name) >= resume_index

    def _emit_monitoring_event(self, stage: str, status: str, details: Optional[Mapping[str, Any]]) -> None:
        if not self.config.enable_monitoring:
            return
        payload = {
            "stage": stage,
            "status": status,
            "details": details or {},
        }
        if self._monitoring_hook:
            self._monitoring_executor.submit(self._monitoring_hook, payload)
        else:
            logger.debug("Monitoring event %s", payload)

    def _load_monitoring_hook(self):
        try:
            module = importlib.import_module("scripts.monitor_progress")
        except ModuleNotFoundError:
            return None
        if hasattr(module, "record_event"):
            return getattr(module, "record_event")
        if hasattr(module, "emit_event"):
            return getattr(module, "emit_event")
        return None


def _parse_args(argv: Optional[Sequence[str]] = None) -> Any:
    import argparse

    parser = argparse.ArgumentParser(description="Orchestrate Brazilian job title clustering pipeline")
    parser.add_argument("sources", nargs="+", help="Paths to data sources for loader stage")
    parser.add_argument("--workdir", required=True, help="Working directory for intermediates")
    parser.add_argument("--min-frequency", type=int, default=2)
    parser.add_argument("--dbscan-eps", type=float, default=0.42)
    parser.add_argument("--dbscan-min-samples", type=int, default=5)
    parser.add_argument("--skip", choices=["data_loader", "embeddings", "clustering", "progression", "mapping"], action="append")
    parser.add_argument("--checkpoint", type=str)
    parser.add_argument("--resume-from", type=str)
    parser.add_argument("--category", type=str, default="GENERAL")
    parser.add_argument("--no-incremental", dest="incremental", action="store_false")
    parser.add_argument("--parallelism", type=int, default=1)
    parser.add_argument("--no-monitoring", dest="enable_monitoring", action="store_false")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = _parse_args(argv)
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    skip = set(args.skip or [])
    config = PipelineConfig(
        data_sources=[Path(src) for src in args.sources],
        working_dir=workdir,
        run_data_loader="data_loader" not in skip,
        run_embeddings="embeddings" not in skip,
        run_clustering="clustering" not in skip,
        run_progression="progression" not in skip,
        run_mapping="mapping" not in skip,
        min_frequency=args.min_frequency,
        dbscan_eps=args.dbscan_eps,
        dbscan_min_samples=args.dbscan_min_samples,
        checkpoint_path=Path(args.checkpoint) if args.checkpoint else None,
        resume_from=args.resume_from,
        category=args.category,
        incremental=args.incremental,
        parallelism=args.parallelism,
        enable_monitoring=args.enable_monitoring,
    )
    orchestrator = BrazilianClusteringOrchestrator(config)
    orchestrator.run()


if __name__ == "__main__":
    main()
