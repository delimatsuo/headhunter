"""Orchestrates the ECO quality assurance pipeline."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

try:
    import psycopg  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    psycopg = None  # type: ignore

from scripts.alias_confidence_scorer import AliasConfidenceScorer
from scripts.eco_clustering_validator import ClusteringValidator, ClusteringValidatorConfig
from scripts.eco_template_accuracy_validator import TemplateAccuracyValidator, TemplateAccuracyValidatorConfig

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")


QUEUE_UPSERT_SQL = """
INSERT INTO eco_validation_queue (item_type, item_id, eco_id, reason, priority, status)
VALUES (%s, %s, %s, %s, %s, 'pending')
ON CONFLICT (item_type, item_id) DO UPDATE
SET reason = EXCLUDED.reason,
    priority = GREATEST(EXCLUDED.priority, eco_validation_queue.priority),
    eco_id = COALESCE(EXCLUDED.eco_id, eco_validation_queue.eco_id),
    status = CASE WHEN eco_validation_queue.status IN ('resolved','rejected') THEN 'pending' ELSE eco_validation_queue.status END,
    assigned_reviewer = CASE WHEN eco_validation_queue.status IN ('resolved','rejected') THEN NULL ELSE eco_validation_queue.assigned_reviewer END,
    resolved_at = CASE WHEN eco_validation_queue.status IN ('resolved','rejected') THEN NULL ELSE eco_validation_queue.resolved_at END,
    updated_at = NOW();
"""


@dataclass
class QualityThresholds:
    occupation_f1: float = 0.85
    cluster_coherence: float = 0.6
    template_quality: float = 0.8
    feedback_sla_hours: int = 48


@dataclass
class OrchestratorConfig:
    output_dir: Path
    validation_thresholds: QualityThresholds = field(default_factory=QualityThresholds)
    clustering_config: Optional[ClusteringValidatorConfig] = None
    template_config: Optional[TemplateAccuracyValidatorConfig] = None
    database_dsn: Optional[str] = None
    max_queue_batch: int = 500


class ECOQualityOrchestrator:
    """Coordinates end-to-end validation flows for ECO data."""

    def __init__(self, config: OrchestratorConfig) -> None:
        self.config = config
        self.alias_scorer = AliasConfidenceScorer()
        self.metrics: Dict[str, Any] = {}
        self.output_dir = config.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------
    def populateValidationQueue(self) -> Dict[str, Any]:
        logger.info("Populating validation queue using low-confidence aliases and conflicts")
        queue_items: List[Dict[str, Any]] = []
        enqueued = 0
        if self.config.database_dsn and psycopg:
            with psycopg.connect(self.config.database_dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT eco_id, alias, normalized_alias, confidence
                        FROM eco_alias
                        WHERE confidence < 0.55
                        ORDER BY confidence ASC
                        LIMIT %s
                        """,
                        (self.config.max_queue_batch,),
                    )
                    for eco_id, alias, normalized, confidence in cur.fetchall():
                        queue_items.append(
                            {
                                "item_type": "alias",
                                "item_id": normalized,
                                "eco_id": eco_id,
                                "reason": f"Low confidence ({confidence:.2f})",
                                "priority": 4 if confidence < 0.4 else 3,
                            }
                        )
                    if queue_items:
                        enqueued = self._upsert_validation_queue(cur, queue_items)
                conn.commit()
                if enqueued:
                    logger.info("Upserted %s queue items into eco_validation_queue", enqueued)
        else:
            logger.warning("No database connection available; generating synthetic queue preview")
            queue_items.append(
                {
                    "item_type": "alias",
                    "item_id": "desenvolvedor backend sr",
                    "eco_id": "ECO.BR.SE.BACKEND",
                    "reason": "Synthetic example (confidence 0.38)",
                    "priority": 4,
                }
            )
        self.metrics["queue_populated"] = {
            "count": len(queue_items),
            "generated_at": datetime.utcnow().isoformat(),
            "enqueued": enqueued,
        }
        self._write_json("validation_queue_batch.json", queue_items)
        return self.metrics["queue_populated"]

    def runClusteringValidation(self) -> Dict[str, Any]:
        if not self.config.clustering_config:
            raise RuntimeError("ClusteringValidatorConfig not provided")
        logger.info("Running clustering validation")
        validator = ClusteringValidator(self.config.clustering_config)
        report = validator.generateValidationReport()
        self.metrics["clustering"] = report
        return report

    def performTemplateAccuracy(self) -> Dict[str, Any]:
        if not self.config.template_config:
            raise RuntimeError("TemplateAccuracyValidatorConfig not provided")
        logger.info("Running template accuracy validation")
        validator = TemplateAccuracyValidator(self.config.template_config)
        report = validator.generateValidationReport()
        self.metrics["templates"] = report
        return report

    def processFeedbackLoop(self, feedback_records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        logger.info("Processing %s recruiter feedback records", len(feedback_records))
        auto_records: List[Dict[str, Any]] = []
        manual_records: List[Dict[str, Any]] = []
        for record in feedback_records:
            rec = dict(record)
            confidence = float(rec.get("confidence_rating", 0) or 0)
            alias = rec.get("alias")
            canonical = rec.get("canonical")
            if confidence >= 4 and alias and canonical:
                scores = self.alias_scorer.scoreWithEvidence(
                    alias,
                    canonical,
                    rec.get("evidence"),
                    int(rec.get("posting_volume", 1)),
                    rec.get("last_seen"),
                )
                if scores.final_score >= 0.8:
                    rec["score"] = scores.final_score
                    auto_records.append(rec)
                    continue
            manual_records.append(rec)

        auto_summary = [
            {
                "alias": rec.get("alias"),
                "score": rec.get("score"),
                "feedback_id": rec.get("id"),
            }
            for rec in auto_records
        ]
        manual_summary = [
            {
                "alias": rec.get("alias"),
                "feedback_id": rec.get("id"),
                "feedback_type": rec.get("feedback_type"),
            }
            for rec in manual_records
        ]

        db_result: Dict[str, Any] = {
            "feedback_applied": 0,
            "queue_enqueued": 0,
            "aliases_adjusted": 0,
            "events": [],
        }

        if self.config.database_dsn and psycopg and (auto_records or manual_records):
            with psycopg.connect(self.config.database_dsn) as conn:
                with conn.cursor() as cur:
                    if auto_records:
                        feedback_ids = [rec.get("id") for rec in auto_records if rec.get("id") is not None]
                        if feedback_ids:
                            cur.executemany(
                                """
                                UPDATE eco_feedback
                                SET status = 'applied',
                                    reviewed_by = COALESCE(reviewed_by, 'eco-automation'),
                                    applied_at = NOW(),
                                    updated_at = NOW()
                                WHERE id = %s
                                """,
                                [(fid,) for fid in feedback_ids],
                            )
                            db_result["feedback_applied"] = len(feedback_ids)
                        for rec in auto_records:
                            eco_id = rec.get("eco_id")
                            normalized = rec.get("normalized_alias") or rec.get("alias")
                            score_value = float(rec.get("score") or 0.0)
                            if eco_id and normalized and score_value > 0:
                                capped_score = max(0.0, min(1.0, score_value))
                                cur.execute(
                                    """
                                    UPDATE eco_alias
                                    SET confidence = GREATEST(confidence, %s),
                                        updated_at = NOW()
                                    WHERE eco_id = %s AND normalized_alias = %s
                                    """,
                                    (capped_score, eco_id, normalized),
                                )
                                if cur.rowcount:
                                    db_result["aliases_adjusted"] += cur.rowcount
                                    db_result["events"].append(
                                        {
                                            "type": "alias_confidence_adjusted",
                                            "eco_id": eco_id,
                                            "alias": normalized,
                                            "confidence": capped_score,
                                        }
                                    )

                    queue_entries = [self._queue_entry_from_feedback(rec) for rec in manual_records]
                    queue_entries = [entry for entry in queue_entries if entry.get("item_id")]
                    if queue_entries:
                        db_result["queue_enqueued"] = self._upsert_validation_queue(cur, queue_entries)
                conn.commit()

        payload: Dict[str, Any] = {
            "auto_resolved": auto_summary,
            "needs_manual_review": manual_summary,
        }
        if any(
            db_result.get(key)
            for key in ("feedback_applied", "queue_enqueued", "aliases_adjusted")
        ) or db_result.get("events"):
            payload["db_updates"] = db_result

        self.metrics["feedback_loop"] = payload
        self._write_json("feedback_processing_summary.json", payload)
        return payload

    def generateQualityReports(self) -> Path:
        logger.info("Generating consolidated quality report")
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "metrics": self.metrics,
            "thresholds": self.config.validation_thresholds.__dict__,
            "quality_gate": self.executeQualityGates(),
        }
        path = self._write_json("eco_quality_report.json", report)
        return path

    def executeQualityGates(self) -> Dict[str, Any]:
        thresholds = self.config.validation_thresholds
        clustering_f1 = self._metric_path(["clustering", "occupation_metrics", "f1"], default=0.0)
        coherence = self._metric_path(["clustering", "cluster_coherence", "coherence_mean"], default=0.0)
        template_score = self._metric_path(["templates", "quality_score", "score"], default=0.0)
        gate = {
            "clustering_passed": clustering_f1 >= thresholds.occupation_f1,
            "coherence_passed": coherence >= thresholds.cluster_coherence,
            "template_passed": template_score >= thresholds.template_quality,
        }
        gate["overall_passed"] = all(gate.values())
        self.metrics["quality_gate"] = gate
        return gate

    def coordinateValidationScheduling(self) -> Dict[str, Any]:
        logger.info("Coordinating validation scheduling")
        schedule = {
            "queue_population": datetime.utcnow().isoformat(),
            "clustering_validation": datetime.utcnow().isoformat(),
            "template_validation": datetime.utcnow().isoformat(),
        }
        self.metrics["schedule"] = schedule
        return schedule

    def handleErrorRecovery(self, error: Exception) -> Dict[str, Any]:
        logger.error("Validation pipeline failure: %s", error, exc_info=True)
        recovery = {
            "error": str(error),
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.metrics.setdefault("errors", []).append(recovery)
        self._write_json("eco_quality_errors.json", self.metrics["errors"])
        return recovery

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _upsert_validation_queue(cursor: Any, items: Sequence[Mapping[str, Any]]) -> int:
        if not items:
            return 0
        params: List[Tuple[str, str, Optional[str], str, int]] = []
        for item in items:
            item_type = str(item.get("item_type") or "alias")
            item_id = item.get("item_id")
            if not item_id:
                continue
            reason = str(item.get("reason") or "Queued by orchestrator")
            eco_id = item.get("eco_id")
            eco_value = str(eco_id) if eco_id else None
            priority = int(item.get("priority") or 3)
            params.append((item_type, str(item_id), eco_value, reason, priority))
        if not params:
            return 0
        cursor.executemany(QUEUE_UPSERT_SQL, params)
        return len(params)

    @staticmethod
    def _queue_entry_from_feedback(record: Mapping[str, Any]) -> Dict[str, Any]:
        feedback_type = str(record.get("feedback_type") or "").lower()
        if feedback_type == "occupation_mapping":
            item_type = "occupation"
        elif feedback_type == "skill_template":
            item_type = "template"
        else:
            item_type = "alias"
        candidate = (
            record.get("normalized_alias")
            or record.get("alias")
            or record.get("original_value")
            or record.get("eco_id")
            or record.get("id")
        )
        item_id = str(candidate) if candidate is not None else None
        feedback_id = record.get("id")
        identifier = feedback_id if feedback_id is not None else "unknown"
        label = feedback_type.replace("_", " ") if feedback_type else "feedback"
        reason = record.get("feedback_notes") or f"{label.title()} requires manual review (feedback {identifier})"
        eco_id = record.get("eco_id")
        priority = 4 if float(record.get("confidence_rating") or 0) >= 4 else 3
        return {
            "item_type": item_type,
            "item_id": item_id,
            "eco_id": eco_id,
            "reason": reason,
            "priority": priority,
        }

    def _write_json(self, filename: str, payload: Any) -> Path:
        path = self.output_dir / filename
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        logger.info("Wrote %s", path)
        return path

    def _metric_path(self, path: Sequence[str], default: Any = None) -> Any:
        cursor: Any = self.metrics
        for key in path:
            if isinstance(cursor, Mapping) and key in cursor:
                cursor = cursor[key]
            else:
                return default
        return cursor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ECO Quality Assurance Orchestrator")
    parser.add_argument("--config", type=Path, help="Path to orchestrator configuration JSON")
    parser.add_argument("--output", type=Path, default=Path("reports/eco_quality"), help="Directory for generated reports")
    parser.add_argument("--cluster-results", type=Path, help="Path to clustering results JSON")
    parser.add_argument("--gold-standard", type=Path, help="Path to gold standard mapping file")
    parser.add_argument("--template-path", type=Path, help="Path to ECO templates JSON")
    parser.add_argument("--postings-path", type=Path, help="Path to job postings JSON")
    parser.add_argument("--database-dsn", type=str, help="PostgreSQL DSN for ECO database")
    return parser


def load_config(args: argparse.Namespace) -> OrchestratorConfig:
    thresholds = QualityThresholds()
    if args.config and args.config.exists():
        with args.config.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        thresholds = QualityThresholds(**payload.get("thresholds", {}))
    clustering_config = None
    if args.cluster_results and args.gold_standard:
        clustering_config = ClusteringValidatorConfig(
            gold_standard_path=args.gold_standard,
            cluster_results_path=args.cluster_results,
            output_dir=args.output,
        )
    template_config = None
    if args.template_path and args.postings_path:
        template_config = TemplateAccuracyValidatorConfig(
            template_path=args.template_path,
            job_postings_path=args.postings_path,
            output_dir=args.output,
        )
    return OrchestratorConfig(
        output_dir=args.output,
        validation_thresholds=thresholds,
        clustering_config=clustering_config,
        template_config=template_config,
        database_dsn=args.database_dsn,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config(args)
    orchestrator = ECOQualityOrchestrator(config)
    try:
        orchestrator.coordinateValidationScheduling()
        orchestrator.populateValidationQueue()
        if config.clustering_config:
            orchestrator.runClusteringValidation()
        if config.template_config:
            orchestrator.performTemplateAccuracy()
        orchestrator.generateQualityReports()
    except Exception as exc:  # pragma: no cover - error handling path
        orchestrator.handleErrorRecovery(exc)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
