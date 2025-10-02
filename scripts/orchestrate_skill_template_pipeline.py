"""Orchestrates the Skill Requirement Template pipeline."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from scripts.brazilian_job_skill_extractor import BrazilianJobSkillExtractor, SkillExtractorConfig
from scripts.yoe_range_analyzer import YoEAnalyzerConfig, YoERangeAnalyzer
from scripts.regional_prevalence_mapper import RegionalMapperConfig, RegionalPrevalenceMapper
from scripts.eco_template_generator import TemplateGeneratorConfig, EcoTemplateGenerator


@dataclass
class SkillTemplatePipelineConfig:
    job_posting_paths: Sequence[Path]
    working_dir: Path
    run_skill_stage: bool = True
    run_yoe_stage: bool = True
    run_regional_stage: bool = True
    run_template_stage: bool = True
    enable_llm: bool = True
    checkpoint_path: Optional[Path] = None
    resume_from: Optional[str] = None
    min_skill_frequency: int = 2
    min_skill_confidence: float = 0.35
    min_yoe_records: int = 5
    limit: Optional[int] = None


class SkillTemplatePipelineOrchestrator:
    def __init__(self, config: SkillTemplatePipelineConfig) -> None:
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
        self.config = config
        self.state: Dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)
        self._completed_stage: Optional[str] = None
        self._load_checkpoint()

    def run(self) -> Dict[str, Any]:
        stage_sequence = [
            ("skills", self.config.run_skill_stage, self._run_skill_stage),
            ("yoe", self.config.run_yoe_stage, self._run_yoe_stage),
            ("regional", self.config.run_regional_stage, self._run_regional_stage),
            ("templates", self.config.run_template_stage, self._run_template_stage),
        ]
        for stage_name, enabled, handler in stage_sequence:
            if not enabled:
                self.logger.info("Skipping stage %s", stage_name)
                continue
            if self._should_skip_stage(stage_name):
                self.logger.info("Resuming pipeline; skipping stage %s", stage_name)
                continue
            self.logger.info("Running stage %s", stage_name)
            handler()
            self._completed_stage = stage_name
            self._write_checkpoint(stage_name)
        self.logger.info("Skill template pipeline completed")
        return self.state

    def _skill_output(self) -> Path:
        return self.config.working_dir / "skills" / "skill_templates.json"

    def _yoe_output(self) -> Path:
        return self.config.working_dir / "yoe" / "yoe_ranges.json"

    def _regional_output(self) -> Path:
        return self.config.working_dir / "regional" / "regional_prevalence.json"

    def _template_output(self) -> Path:
        return self.config.working_dir / "templates" / "eco_templates.json"

    def _evidence_output(self) -> Path:
        return self.config.working_dir / "templates" / "eco_template_evidence.json"

    def _run_skill_stage(self) -> None:
        output_path = self._skill_output()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        extractor_config = SkillExtractorConfig(
            input_paths=list(self.config.job_posting_paths),
            output_path=output_path,
            min_frequency_threshold=self.config.min_skill_frequency,
            min_confidence_threshold=self.config.min_skill_confidence,
            enable_llm=self.config.enable_llm,
            limit=self.config.limit,
        )
        extractor = BrazilianJobSkillExtractor(extractor_config)
        payload = extractor.run()
        self.state["skills"] = {"output": str(output_path), "occupations": len(payload)}

    def _run_yoe_stage(self) -> None:
        output_path = self._yoe_output()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        yoe_config = YoEAnalyzerConfig(
            input_paths=list(self.config.job_posting_paths),
            mapping_path=None,
            output_path=output_path,
            min_records=self.config.min_yoe_records,
            limit=self.config.limit,
        )
        analyzer = YoERangeAnalyzer(yoe_config)
        payload = analyzer.run()
        self.state["yoe"] = {"output": str(output_path), "occupations": len(payload)}

    def _run_regional_stage(self) -> None:
        output_path = self._regional_output()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        regional_config = RegionalMapperConfig(
            input_paths=list(self.config.job_posting_paths),
            output_path=output_path,
            limit=self.config.limit,
        )
        mapper = RegionalPrevalenceMapper(regional_config)
        payload = mapper.run()
        self.state["regional"] = {"output": str(output_path), "occupations": len(payload)}

    def _run_template_stage(self) -> None:
        template_config = TemplateGeneratorConfig(
            skill_path=self._skill_output(),
            yoe_path=self._yoe_output(),
            regional_path=self._regional_output(),
            output_path=self._template_output(),
            evidence_path=self._evidence_output(),
        )
        generator = EcoTemplateGenerator(template_config)
        payload = generator.run()
        self.state["templates"] = {"output": str(self._template_output()), "occupations": len(payload)}

    def _load_checkpoint(self) -> None:
        path = self.config.checkpoint_path
        if not path or not path.exists():
            return
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except json.JSONDecodeError:
            self.logger.warning("Checkpoint %s is corrupted; ignoring", path)
            self.state = {}
            self._completed_stage = None
            return
        self._completed_stage = payload.get("completed_stage")
        self.state = payload.get("state", {})

    def _write_checkpoint(self, stage_name: str) -> None:
        if not self.config.checkpoint_path:
            return
        checkpoint = {"completed_stage": stage_name, "state": self.state}
        self.config.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config.checkpoint_path.open("w", encoding="utf-8") as handle:
            json.dump(checkpoint, handle, indent=2)

    def _should_skip_stage(self, stage_name: str) -> bool:
        if not self.config.resume_from:
            return False
        completed_stage = self._completed_stage
        if not completed_stage:
            return False
        stages = ["skills", "yoe", "regional", "templates"]
        if stage_name in stages and completed_stage in stages:
            completed_index = stages.index(completed_stage)
            return stages.index(stage_name) <= completed_index
        return False


def run_pipeline(job_posting_paths: Sequence[str], working_dir: str, enable_llm: bool = True) -> Dict[str, Any]:
    config = SkillTemplatePipelineConfig(
        job_posting_paths=[Path(path) for path in job_posting_paths],
        working_dir=Path(working_dir),
        enable_llm=enable_llm,
    )
    orchestrator = SkillTemplatePipelineOrchestrator(config)
    return orchestrator.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the Skill Requirement Template pipeline")
    parser.add_argument("inputs", nargs="+", help="Paths to job posting datasets")
    parser.add_argument("--working-dir", required=True, help="Working directory for artefacts")
    parser.add_argument("--disable-llm", action="store_true", help="Use heuristic extraction only")
    parser.add_argument("--checkpoint", help="Optional checkpoint path")
    parser.add_argument("--resume-from", help="Resume pipeline from a later stage")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    cfg = SkillTemplatePipelineConfig(
        job_posting_paths=[Path(path) for path in args.inputs],
        working_dir=Path(args.working_dir),
        enable_llm=not args.disable_llm,
        checkpoint_path=Path(args.checkpoint) if args.checkpoint else None,
        resume_from=args.resume_from,
        limit=args.limit,
    )
    orchestrator = SkillTemplatePipelineOrchestrator(cfg)
    orchestrator.run()
