#!/usr/bin/env python3
"""Validate ECO search integration against performance targets.

This script consumes control/treatment datasets and produces quality and latency
reports. It can be extended to call live endpoints or export experiment data,
but defaults to evaluating an offline dataset for reproducibility.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass
class QueryRecord:
    query_id: str
    text: str
    control_relevance: List[float]
    treatment_relevance: List[float]
    control_latency: List[float]
    treatment_latency: List[float]
    cache_hit_ratio: Optional[float] = None


@dataclass
class MetricSummary:
    mean: float
    stddev: float
    count: int
    confidence_low: float
    confidence_high: float


@dataclass
class PerformanceReport:
    ndcg_delta: MetricSummary
    mrr_delta: MetricSummary
    latency_delta_ms: MetricSummary
    cache_hit_ratio: Optional[MetricSummary]
    dataset_size: int
    generated_at: float = field(default_factory=time.time)


class ECOPerformanceValidator:
    """Runs quality and latency validation for ECO integration."""

    def __init__(self, target_ndcg_gain: Tuple[float, float] = (0.05, 0.10),
                 max_latency_delta_ms: float = 20.0) -> None:
        self.target_ndcg_gain = target_ndcg_gain
        self.max_latency_delta_ms = max_latency_delta_ms

    def run_search_quality_test(self, records: Sequence[QueryRecord]) -> MetricSummary:
        deltas = [
            self._ndcg(record.treatment_relevance) - self._ndcg(record.control_relevance)
            for record in records
        ]
        return self._summarize(deltas)

    def measure_latency_impact(self, records: Sequence[QueryRecord]) -> MetricSummary:
        deltas = [
            statistics.mean(record.treatment_latency) - statistics.mean(record.control_latency)
            for record in records
            if record.control_latency and record.treatment_latency
        ]
        return self._summarize(deltas)

    def calculate_mrr_delta(self, records: Sequence[QueryRecord]) -> MetricSummary:
        deltas = [
            self._mrr(record.treatment_relevance) - self._mrr(record.control_relevance)
            for record in records
        ]
        return self._summarize(deltas)

    def validate_cache_effectiveness(self, records: Sequence[QueryRecord]) -> Optional[MetricSummary]:
        ratios = [record.cache_hit_ratio for record in records if record.cache_hit_ratio is not None]
        if not ratios:
            return None
        return self._summarize(ratios)

    def generate_performance_report(self, records: Sequence[QueryRecord]) -> PerformanceReport:
        ndcg_summary = self.run_search_quality_test(records)
        mrr_summary = self.calculate_mrr_delta(records)
        latency_summary = self.measure_latency_impact(records)
        cache_summary = self.validate_cache_effectiveness(records)
        return PerformanceReport(
            ndcg_delta=ndcg_summary,
            mrr_delta=mrr_summary,
            latency_delta_ms=latency_summary,
            cache_hit_ratio=cache_summary,
            dataset_size=len(records),
        )

    @staticmethod
    def _ndcg(relevance: Sequence[float], k: int = 10) -> float:
        truncated = relevance[:k]
        if not truncated:
            return 0.0
        dcg = sum((2 ** rel - 1) / math.log2(idx + 2) for idx, rel in enumerate(truncated))
        ideal = sorted(truncated, reverse=True)
        ideal_dcg = sum((2 ** rel - 1) / math.log2(idx + 2) for idx, rel in enumerate(ideal))
        return 0.0 if ideal_dcg == 0 else dcg / ideal_dcg

    @staticmethod
    def _mrr(relevance: Sequence[float]) -> float:
        for idx, rel in enumerate(relevance, start=1):
            if rel > 0:
                return 1.0 / idx
        return 0.0

    @staticmethod
    def _summarize(values: Iterable[float]) -> MetricSummary:
        values = list(values)
        if not values:
            return MetricSummary(mean=0.0, stddev=0.0, count=0, confidence_low=0.0, confidence_high=0.0)
        mean = statistics.mean(values)
        stddev = statistics.pstdev(values)
        count = len(values)
        stderr = stddev / math.sqrt(count) if count else 0.0
        margin = 1.96 * stderr
        return MetricSummary(
            mean=mean,
            stddev=stddev,
            count=count,
            confidence_low=mean - margin,
            confidence_high=mean + margin,
        )


def load_dataset(path: Path) -> List[QueryRecord]:
    with path.open('r', encoding='utf-8') as handle:
        payload = json.load(handle)
    records: List[QueryRecord] = []
    for item in payload.get('queries', []):
        records.append(
            QueryRecord(
                query_id=item.get('id', ''),
                text=item.get('text', ''),
                control_relevance=item.get('control_relevance', []),
                treatment_relevance=item.get('treatment_relevance', []),
                control_latency=item.get('latency_ms_control', []),
                treatment_latency=item.get('latency_ms_treatment', []),
                cache_hit_ratio=item.get('cache_hit_ratio'),
            )
        )
    return records


def print_report(report: PerformanceReport, validator: ECOPerformanceValidator) -> None:
    target_low, target_high = validator.target_ndcg_gain
    print("ECO Performance Validation")
    print("===========================")
    print(f"Dataset size: {report.dataset_size} queries")
    print(f"Generated at: {time.ctime(report.generated_at)}")
    print()
    print("Search Quality Uplift")
    print("---------------------")
    print(_format_summary(report.ndcg_delta, 'NDCG@10 delta', target_low, target_high))
    print(_format_summary(report.mrr_delta, 'MRR delta'))
    print()
    print("Latency Impact")
    print("---------------")
    print(_format_summary(report.latency_delta_ms, 'Latency delta (ms)', upper_bound=validator.max_latency_delta_ms))
    if report.cache_hit_ratio:
        print()
        print("Cache Effectiveness")
        print("-------------------")
        print(_format_summary(report.cache_hit_ratio, 'Cache hit ratio'))


def _format_summary(summary: MetricSummary, label: str,
                    target_low: Optional[float] = None,
                    target_high: Optional[float] = None,
                    upper_bound: Optional[float] = None) -> str:
    if summary.count == 0:
        return f"{label}: no data"
    line = (
        f"{label}: mean={summary.mean:.4f} ± {summary.confidence_high - summary.mean:.4f}"
        f" (stddev={summary.stddev:.4f}, n={summary.count})"
    )
    if target_low is not None and target_high is not None:
        meets_low = summary.mean >= target_low
        line += f" · target ≥{target_low:.3f} ({'OK' if meets_low else 'below target'})"
        if summary.mean >= target_high:
            status = 'met' if math.isclose(summary.mean, target_high, rel_tol=1e-9, abs_tol=1e-9) else 'exceeded'
            line += f" · stretch {target_high:.3f} ({status})"
        else:
            line += f" · stretch {target_high:.3f} (not met)"
    elif target_low is not None:
        meets_low = summary.mean >= target_low
        line += f" · target ≥{target_low:.3f} ({'OK' if meets_low else 'below target'})"
    elif target_high is not None:
        line += f" · stretch {target_high:.3f}"

    if upper_bound is not None:
        ok = summary.mean <= upper_bound
        line += f" · max {upper_bound:.2f} ({'OK' if ok else 'outside target'})"
    return line


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate ECO search integration performance targets")
    parser.add_argument('--dataset', required=True, help='Path to JSON dataset with control/treatment comparisons')
    parser.add_argument('--target-ndcg-low', type=float, default=0.05)
    parser.add_argument('--target-ndcg-high', type=float, default=0.10)
    parser.add_argument('--max-latency-delta', type=float, default=20.0)
    parser.add_argument('--output', help='Optional path to write JSON report')
    args = parser.parse_args(argv)

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Dataset file not found: {dataset_path}", file=sys.stderr)
        return 1

    records = load_dataset(dataset_path)
    if not records:
        print("Dataset contains no query records", file=sys.stderr)
        return 1

    validator = ECOPerformanceValidator(
        target_ndcg_gain=(args.target_ndcg_low, args.target_ndcg_high),
        max_latency_delta_ms=args.max_latency_delta,
    )
    report = validator.generate_performance_report(records)
    print_report(report, validator)

    if args.output:
        out_path = Path(args.output)
        payload: Dict[str, any] = {
            'target_ndcg_low': args.target_ndcg_low,
            'target_ndcg_high': args.target_ndcg_high,
            'max_latency_delta_ms': args.max_latency_delta,
            'report': {
                'ndcg_delta': report.ndcg_delta.__dict__,
                'mrr_delta': report.mrr_delta.__dict__,
                'latency_delta_ms': report.latency_delta_ms.__dict__,
                'cache_hit_ratio': report.cache_hit_ratio.__dict__ if report.cache_hit_ratio else None,
                'dataset_size': report.dataset_size,
                'generated_at': report.generated_at,
            },
        }
        out_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        print(f"Report written to {out_path}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
