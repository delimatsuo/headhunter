"""Evidence tracking system for ECO template generation."""

from __future__ import annotations

import json
import logging
import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

try:
    from scripts.alias_confidence_scorer import SOURCE_TRUST
except Exception:  # pragma: no cover - fallback when module not available in tests
    SOURCE_TRUST = {
        "LINKEDIN": 1.0,
        "VAGAS": 0.9,
        "INFOJOBS": 0.85,
        "CATHO": 0.85,
        "INDEED_BR": 0.8,
    }


@dataclass
class EvidenceTrackerConfig:
    output_path: Path
    snapshot_path: Optional[Path] = None
    min_support: int = 3
    credibility_floor: float = 0.4


@dataclass
class EvidenceItem:
    entity_key: str
    attribute: str
    support: int = 0
    weighted_support: float = 0.0
    confidence: float = 0.0
    sources: Dict[str, int] = field(default_factory=dict)
    postings: List[str] = field(default_factory=list)
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def register(self, postings: Iterable[str], confidence: float, weight: float, sources: Iterable[str]) -> None:
        self.support += 1
        self.weighted_support += weight
        self.confidence = max(self.confidence, confidence)
        for source in sources:
            if not source:
                continue
            key = source.upper()
            self.sources[key] = self.sources.get(key, 0) + 1
        for posting_id in postings:
            if posting_id and len(self.postings) < 100:
                self.postings.append(posting_id)
        self.last_updated = datetime.utcnow().isoformat()

    def to_dict(
        self,
        status: str = "ok",
        *,
        trend: Optional[str] = None,
        delta_confidence: Optional[float] = None,
        stdev_confidence: Optional[float] = None,
        history: Optional[Sequence[Mapping[str, Any]]] = None,
    ) -> Dict[str, Any]:
        lower, upper = _wilson_interval(self.confidence, self.support)
        metadata = dict(self.metadata)
        if history is not None:
            metadata = dict(metadata)
            metadata["history"] = list(history)
        return {
            "entity": self.entity_key,
            "attribute": self.attribute,
            "support": self.support,
            "weighted_support": round(self.weighted_support, 2),
            "confidence": round(self.confidence, 4),
            "confidence_interval": [round(lower, 4), round(upper, 4)],
            "sources": self.sources,
            "postings": self.postings,
            "metadata": metadata,
            "last_updated": self.last_updated,
            "status": status,
            "trend": trend,
            "delta_confidence": None if delta_confidence is None else round(delta_confidence, 4),
            "stdev_confidence": None if stdev_confidence is None else round(stdev_confidence, 4),
        }


class EvidenceTracker:
    """Central evidence registry used across the template pipeline."""

    def __init__(self, config: EvidenceTrackerConfig) -> None:
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
        self.config = config
        self.items: Dict[str, EvidenceItem] = {}
        self.history: List[Dict[str, Any]] = []
        if config.snapshot_path and config.snapshot_path.exists():
            self._load_snapshot(config.snapshot_path)

    def register_skill(
        self,
        occupation: str,
        skill: str,
        postings: Sequence[str],
        confidence: float,
        volume: int,
        sources: Sequence[str],
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> None:
        key = f"skill::{occupation}::{skill}"
        item = self.items.setdefault(key, EvidenceItem(entity_key=occupation, attribute=skill))
        weight = _compute_weight(volume, sources)
        item.register(postings, confidence, weight, sources)
        if metadata:
            item.metadata.update(metadata)

    def register_yoe(self, occupation: str, summary: Mapping[str, Any]) -> None:
        key = f"yoe::{occupation}"
        item = self.items.setdefault(key, EvidenceItem(entity_key=occupation, attribute="experience_range"))
        confidence = float(summary.get("confidence", 0.0))
        postings = [f"yoe-sample-{idx}" for idx in range(min(10, int(summary.get("postings", 0))))]
        weight = float(summary.get("postings", 0))
        item.register(postings, confidence, weight, [])
        item.metadata.update(summary)

    def register_region(self, occupation: str, region: str, info: Mapping[str, Any]) -> None:
        key = f"region::{occupation}::{region}"
        item = self.items.setdefault(key, EvidenceItem(entity_key=occupation, attribute=f"region::{region}"))
        confidence = float(info.get("confidence", 0.0))
        postings = info.get("postings", [])
        weight = float(info.get("occurrences", 0))
        sources = info.get("sources", {}).keys() if isinstance(info.get("sources"), dict) else []
        item.register(postings, confidence, weight, sources)
        item.metadata.update(info)

    def finalize(self) -> Dict[str, Any]:
        snapshot_id = datetime.utcnow().strftime("%Y-%m")
        payload: Dict[str, List[Dict[str, Any]]] = {}
        flagged: List[Dict[str, Any]] = []
        all_records: List[Dict[str, Any]] = []
        metrics_by_key: Dict[str, Mapping[str, Any]] = {}
        for key, item in self.items.items():
            if item.support == 0 and not key.startswith("yoe::"):
                continue
            metrics = self._compute_item_metrics(item, snapshot_id)
            metrics_by_key[key] = metrics
            status = self._status_for_item(key, item, metrics)
            record = item.to_dict(
                status=status,
                trend=metrics.get("trend"),
                delta_confidence=metrics.get("delta_confidence"),
                stdev_confidence=metrics.get("stdev_confidence"),
                history=metrics.get("history"),
            )
            payload.setdefault(item.entity_key, []).append(record)
            all_records.append(record)
            if status != "ok":
                flagged.append(record)
        for occupation, evidence_list in payload.items():
            evidence_list.sort(key=lambda entry: entry.get("confidence", 0.0), reverse=True)
        self._update_history(payload, all_records, flagged, snapshot_id, metrics_by_key)
        output_payload = {
            "generated_at": datetime.utcnow().isoformat(),
            "history": self.history,
            "occupations": payload,
            "flagged": flagged,
        }
        self._write_output(output_payload)
        return payload

    def _compute_item_metrics(self, item: EvidenceItem, snapshot_id: str) -> Mapping[str, Any]:
        history_entries: List[Mapping[str, Any]] = []
        raw_history = item.metadata.get("history", [])
        if isinstance(raw_history, Sequence):
            for entry in raw_history:
                if isinstance(entry, Mapping):
                    snapshot_label = entry.get("snapshot")
                    if isinstance(snapshot_label, str):
                        history_entries.append(
                            {
                                "snapshot": snapshot_label,
                                "support": int(entry.get("support", 0)),
                                "weighted_support": float(entry.get("weighted_support", 0.0)),
                                "confidence": float(entry.get("confidence", 0.0)),
                            }
                        )
        history_entries = [entry for entry in history_entries if entry.get("snapshot") != snapshot_id]
        previous_entry: Optional[Mapping[str, Any]] = history_entries[-1] if history_entries else None
        delta_confidence: Optional[float] = None
        if previous_entry is not None:
            delta_confidence = float(item.confidence) - float(previous_entry.get("confidence", 0.0))

        new_entry = {
            "snapshot": snapshot_id,
            "support": item.support,
            "weighted_support": round(item.weighted_support, 2),
            "confidence": round(item.confidence, 4),
        }
        history_with_current = history_entries + [new_entry]
        if len(history_with_current) > 6:
            history_with_current = history_with_current[-6:]

        series = [float(entry.get("confidence", 0.0)) for entry in history_with_current]
        stdev_confidence: Optional[float] = None
        mean_confidence: Optional[float] = None
        if len(series) >= 3:
            mean_confidence = sum(series) / len(series)
            stdev_confidence = statistics.pstdev(series)
        elif series:
            mean_confidence = sum(series) / len(series)

        epsilon = 0.02
        trend = "flat"
        if delta_confidence is not None:
            if delta_confidence > epsilon:
                trend = "up"
            elif delta_confidence < -epsilon:
                trend = "down"

        return {
            "history": history_with_current,
            "delta_confidence": delta_confidence,
            "stdev_confidence": stdev_confidence,
            "mean_confidence": mean_confidence,
            "trend": trend,
        }

    def _status_for_item(self, key: str, item: EvidenceItem, metrics: Mapping[str, Any]) -> str:
        floor = self.config.credibility_floor
        if item.support < self.config.min_support and not key.startswith("yoe::"):
            return "low_support"
        if item.confidence < floor:
            return "low_credibility"
        delta_confidence = metrics.get("delta_confidence")
        if delta_confidence is not None and delta_confidence <= -0.1:
            return "confidence_drop"
        stdev_confidence = metrics.get("stdev_confidence")
        mean_confidence = metrics.get("mean_confidence")
        history = metrics.get("history")
        if (
            stdev_confidence is not None
            and isinstance(history, Sequence)
            and len(history) >= 3
            and mean_confidence
            and mean_confidence > 0
            and stdev_confidence / mean_confidence > 0.5
        ):
            return "high_variance"
        return "ok"

    def _update_history(
        self,
        payload: Mapping[str, Sequence[Mapping[str, Any]]],
        records: Sequence[Mapping[str, Any]],
        flagged: Sequence[Mapping[str, Any]],
        snapshot_id: str,
        item_metrics: Mapping[str, Mapping[str, Any]],
    ) -> None:
        average_confidence = 0.0
        if records:
            total_confidence = sum(record.get("confidence", 0.0) for record in records)
            average_confidence = total_confidence / len(records)
        snapshot = {
            "snapshot": snapshot_id,
            "total_items": len(records),
            "flagged": len(flagged),
            "avg_confidence": round(average_confidence, 4),
            "occupations": {occupation: len(entries) for occupation, entries in payload.items()},
        }
        self.history = [entry for entry in self.history if entry.get("snapshot") != snapshot_id]
        self.history.append(snapshot)
        self.history = self.history[-6:]
        for key, metrics in item_metrics.items():
            history = metrics.get("history")
            if not isinstance(history, Sequence):
                continue
            item = self.items.get(key)
            if not item:
                continue
            item.metadata = dict(item.metadata)
            history_list = list(history)[-6:]
            item.metadata["history"] = history_list

    def _write_output(self, payload: Mapping[str, Any]) -> None:
        self.config.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config.output_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        if self.config.snapshot_path:
            with self.config.snapshot_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)

    def _load_snapshot(self, snapshot: Path) -> None:
        try:
            with snapshot.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except json.JSONDecodeError:  # pragma: no cover - defensive
            logging.getLogger(__name__).warning("Invalid evidence snapshot at %s", snapshot)
            return
        records_payload: Mapping[str, Any]
        if isinstance(payload, Mapping) and "occupations" in payload:
            self.history = list(payload.get("history", []))[-6:]
            records_payload = payload.get("occupations", {})  # type: ignore[assignment]
        else:
            records_payload = payload if isinstance(payload, Mapping) else {}
        if not isinstance(records_payload, Mapping):
            return
        for occupation, records in records_payload.items():
            for record in records:
                attribute = record.get("attribute") or record.get("skill")
                if not attribute:
                    continue
                if attribute.startswith("region::"):
                    region = attribute.split("::", 1)[1]
                    key = f"region::{occupation}::{region}"
                elif attribute == "experience_range":
                    key = f"yoe::{occupation}"
                else:
                    key = f"skill::{occupation}::{attribute}"
                item = EvidenceItem(entity_key=occupation, attribute=attribute)
                item.support = record.get("support", 0)
                item.weighted_support = record.get("weighted_support", 0.0)
                item.confidence = record.get("confidence", 0.0)
                item.sources = record.get("sources", {})
                item.postings = record.get("postings", [])
                metadata = record.get("metadata", {})
                if not isinstance(metadata, Mapping):
                    metadata = {}
                history = metadata.get("history")
                if history is not None and not isinstance(history, list):
                    metadata = dict(metadata)
                    metadata["history"] = []
                item.metadata = dict(metadata)
                item.last_updated = record.get("last_updated", item.last_updated)
                self.items[key] = item


def _compute_weight(volume: int, sources: Sequence[str]) -> float:
    weight = 1.0 + math.log1p(max(0, volume))
    if sources:
        average_trust = sum(SOURCE_TRUST.get(source.upper(), 0.6) for source in sources) / len(sources)
        weight *= average_trust
    return weight


def _wilson_interval(confidence: float, support: int, z: float = 1.96) -> tuple[float, float]:
    if support == 0:
        return (0.0, 0.0)
    phat = min(1.0, max(0.0, confidence))
    denominator = 1 + z**2 / support
    center = phat + z**2 / (2 * support)
    margin = z * math.sqrt((phat * (1 - phat) + z**2 / (4 * support)) / support)
    lower = (center - margin) / denominator
    upper = (center + margin) / denominator
    return max(0.0, lower), min(1.0, upper)


def build_evidence_registry(
    output_path: str,
    *,
    snapshot_path: Optional[str] = None,
    min_support: int = 3,
) -> EvidenceTracker:
    config = EvidenceTrackerConfig(
        output_path=Path(output_path),
        snapshot_path=Path(snapshot_path) if snapshot_path else None,
        min_support=min_support,
    )
    return EvidenceTracker(config)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate evidence tracking snapshot for ECO templates")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--snapshot", help="Optional snapshot path")
    parser.add_argument("--min-support", type=int, default=3)
    args = parser.parse_args()

    tracker = build_evidence_registry(args.output, snapshot_path=args.snapshot, min_support=args.min_support)
    tracker.finalize()
