from __future__ import annotations

import logging
import math
import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from math import log
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:
    from scripts.eco_title_normalizer import normalize_title_ptbr  # type: ignore
except Exception:  # pragma: no cover
    def normalize_title_ptbr(s: str) -> str:  # type: ignore
        return (s or "").lower()


logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )


SOURCE_TRUST: Dict[str, float] = {
    "LINKEDIN": 1.0,
    "VAGAS": 0.9,
    "INFOJOBS": 0.85,
    "CATHO": 0.85,
    "INDEED_BR": 0.8,
    "MANUAL": 0.95,
    "RECRUITER_FEEDBACK": 0.9,
}

EVIDENCE_TYPE_WEIGHTS: Dict[str, float] = {
    "job_postings": 1.0,
    "manual_curation": 1.3,
    "linkedin_profiles": 0.9,
    "recruiter_feedback": 1.1,
    "talent_pool": 0.85,
}


@dataclass
class ScoringWeights:
    tfidf: float = 0.35
    source_trust: float = 0.2
    edit_similarity: float = 0.2
    semantic_overlap: float = 0.15
    bayesian_smoothing: float = 0.1


@dataclass
class ScoreBreakdown:
    alias: str
    canonical: str
    base_score: float
    evidence_weight: float
    volume_adjustment: float
    temporal_decay: float
    consistency_factor: float
    final_score: float


def token_set(s: str) -> set:
    return set((s or "").lower().split())


def _wilson_interval(p: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n <= 0:
        return 0.0, 0.0
    denominator = 1 + z ** 2 / n
    centre = p + z ** 2 / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z ** 2 / (4 * n)) / n)
    lower = (centre - margin) / denominator
    upper = (centre + margin) / denominator
    return max(0.0, lower), min(1.0, upper)


def _safe_parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        logger.debug("Could not parse datetime value '%s'", value)
        return None


class AliasConfidenceScorer:
    def __init__(self, weights: Optional[ScoringWeights] = None, *, default_decay_rate: float = 0.04):
        self.w = weights or ScoringWeights()
        self.default_decay_rate = default_decay_rate

    def _tfidf(self, df: int, total_docs: int) -> float:
        if total_docs <= 0 or df <= 0:
            return 0.0
        tf = df / total_docs
        idf = log((total_docs + 1) / (df + 1)) + 1
        score = tf * idf * 2
        return float(max(0.0, min(1.0, score)))

    def _source_trust(self, source: Optional[str]) -> float:
        if not source:
            return 0.5
        return SOURCE_TRUST.get(source.upper(), 0.6)

    def _edit_similarity(self, a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()

    def _semantic_overlap(self, a: str, b: str) -> float:
        ta, tb = token_set(a), token_set(b)
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / max(len(ta), len(tb))

    def _bayes(self, df: int, alpha: float = 2.0, beta: float = 5.0) -> float:
        return min(1.0, (df + alpha) / (df + alpha + beta))

    def calculateEvidenceWeight(self, evidence_sources: Iterable[Mapping[str, Any]]) -> float:
        total_weight = 0.0
        trust_weight = 0.0
        aggregated: Counter[str] = Counter()
        for evidence in evidence_sources or []:
            if not isinstance(evidence, Mapping):
                continue
            etype = str(evidence.get("type") or "").strip().lower()
            source_raw = evidence.get("source")
            source = str(source_raw).strip().upper() if source_raw else ""
            confidence = float(evidence.get("confidence", 0.0))
            weight = float(evidence.get("weight", 1.0))
            postings = int(evidence.get("count", evidence.get("postings", 1)) or 1)
            type_lookup_key = etype or (source.lower() if source else "")
            type_weight = EVIDENCE_TYPE_WEIGHTS.get(type_lookup_key, 1.0)
            trust_key = source or (etype.upper() if etype else "")
            trust = SOURCE_TRUST.get(trust_key, 0.6)
            aggregated_key = trust_key or (type_lookup_key.upper() if type_lookup_key else "UNKNOWN")
            aggregated[aggregated_key] += postings
            total_weight += weight * type_weight
            trust_weight += confidence * trust * postings
        if total_weight <= 0:
            return 0.4
        evidence_weight = max(0.0, min(1.0, trust_weight / (total_weight + 1e-6)))
        logger.debug("Calculated evidence weight %.4f from sources=%s", evidence_weight, dict(aggregated))
        return evidence_weight

    def adjustForPostingVolume(self, base_score: float, posting_count: int, total_postings: Optional[int]) -> float:
        total = max(total_postings or posting_count, 1)
        ratio = max(0.0, min(1.0, posting_count / total))
        lower, upper = _wilson_interval(ratio, total)
        adjustment = (lower + upper) / 2
        adjusted_score = base_score * 0.7 + adjustment * 0.3
        logger.debug(
            "Adjusted for posting volume: base=%.4f count=%s total=%s -> %.4f",
            base_score,
            posting_count,
            total_postings,
            adjusted_score,
        )
        return float(max(0.0, min(1.0, adjusted_score)))

    def calculateTemporalDecay(self, base_score: float, last_seen_date: Optional[str], decay_rate: Optional[float] = None) -> float:
        decay = decay_rate if decay_rate is not None else self.default_decay_rate
        last_seen = _safe_parse_datetime(last_seen_date)
        if not last_seen:
            return base_score
        delta_days = max(0.0, (datetime.now(timezone.utc) - last_seen).total_seconds() / 86400.0)
        decay_factor = math.exp(-decay * (delta_days / 30.0))
        decayed_score = base_score * decay_factor
        logger.debug(
            "Applied temporal decay: base=%.4f days=%.1f decay_factor=%.4f -> %.4f",
            base_score,
            delta_days,
            decay_factor,
            decayed_score,
        )
        return float(max(0.0, min(1.0, decayed_score)))

    def scoreConsistency(self, alias_variants: Sequence[Tuple[str, float]]) -> float:
        if not alias_variants:
            return 1.0
        scores = [float(score) for _, score in alias_variants if score is not None]
        if not scores:
            return 1.0
        spread = statistics.pstdev(scores) if len(scores) > 1 else 0.0
        consistency = max(0.5, 1.0 - spread)
        logger.debug("Consistency factor %.4f from spread %.4f", consistency, spread)
        return float(max(0.5, min(1.0, consistency)))

    def score(
        self,
        alias: str,
        normalized_alias: Optional[str],
        canonical_norm: str,
        frequency: int,
        total_docs: int,
        source: Optional[str] = None,
        evidence_sources: Optional[Iterable[Mapping[str, Any]]] = None,
    ) -> float:
        norm = normalized_alias or normalize_title_ptbr(alias)
        evidence_list = list(evidence_sources or [])
        tfidf = self._tfidf(frequency, total_docs)
        trust = self._source_trust(source)
        edit = self._edit_similarity(norm, canonical_norm)
        sem = self._semantic_overlap(norm, canonical_norm)
        bayes = self._bayes(frequency)
        evidence_weight = self.calculateEvidenceWeight(evidence_list)

        score = (
            self.w.tfidf * tfidf
            + self.w.source_trust * trust
            + self.w.edit_similarity * edit
            + self.w.semantic_overlap * sem
            + self.w.bayesian_smoothing * bayes
        )
        blended = 0.8 * score + 0.2 * evidence_weight
        final = float(max(0.0, min(1.0, blended)))
        logger.debug(
            "score(alias=%s canonical=%s) base=%.4f evidence=%.4f final=%.4f",
            alias,
            canonical_norm,
            score,
            evidence_weight,
            final,
        )
        return final

    def scoreWithEvidence(
        self,
        alias: str,
        canonical_norm: str,
        evidence_sources: Optional[Iterable[Mapping[str, Any]]],
        posting_volume: int,
        last_seen_date: Optional[str],
        *,
        total_postings: Optional[int] = None,
        alias_variants: Optional[Sequence[Tuple[str, float]]] = None,
        decay_rate: Optional[float] = None,
    ) -> ScoreBreakdown:
        evidence_list = list(evidence_sources or [])
        base_score = self.score(
            alias,
            None,
            canonical_norm,
            posting_volume,
            total_postings or max(posting_volume, 1),
            source=None,
            evidence_sources=evidence_list,
        )
        evidence_weight = self.calculateEvidenceWeight(evidence_list)
        volume_adjusted = self.adjustForPostingVolume(base_score, posting_volume, total_postings)
        temporal = self.calculateTemporalDecay(volume_adjusted, last_seen_date, decay_rate)
        consistency = self.scoreConsistency(alias_variants or [])
        final_score = float(max(0.0, min(1.0, (temporal * 0.7 + evidence_weight * 0.3) * consistency)))
        logger.info(
            "Alias '%s' scored %.4f (base=%.4f evidence=%.4f volume=%.4f temporal=%.4f consistency=%.4f)",
            alias,
            final_score,
            base_score,
            evidence_weight,
            volume_adjusted,
            temporal,
            consistency,
        )
        return ScoreBreakdown(
            alias=alias,
            canonical=canonical_norm,
            base_score=base_score,
            evidence_weight=evidence_weight,
            volume_adjustment=volume_adjusted,
            temporal_decay=temporal,
            consistency_factor=consistency,
            final_score=final_score,
        )

    def generateConfidenceReport(
        self,
        alias: str,
        breakdown: ScoreBreakdown,
        evidence_sources: Optional[Iterable[Mapping[str, Any]]],
        posting_volume: int,
    ) -> Dict[str, Any]:
        evidence_list = list(evidence_sources or [])
        lower, upper = _wilson_interval(breakdown.final_score, max(posting_volume, 1))
        report = {
            "alias": alias,
            "canonical": breakdown.canonical,
            "score": round(breakdown.final_score, 4),
            "components": {
                "base_score": round(breakdown.base_score, 4),
                "evidence_weight": round(breakdown.evidence_weight, 4),
                "volume_adjustment": round(breakdown.volume_adjustment, 4),
                "temporal_decay": round(breakdown.temporal_decay, 4),
                "consistency_factor": round(breakdown.consistency_factor, 4),
            },
            "confidence_interval": [round(lower, 4), round(upper, 4)],
            "evidence": {
                "count": len(evidence_list),
                "sources": Counter(
                    (str(item.get("source") or item.get("type") or "unknown")).upper()
                    for item in evidence_list
                ),
            },
        }
        logger.debug("Generated confidence report for %s: %s", alias, report)
        return report

    def scoreBatch(
        self,
        payload: Sequence[Mapping[str, Any]],
        *,
        total_postings: Optional[int] = None,
        decay_rate: Optional[float] = None,
    ) -> List[ScoreBreakdown]:
        results: List[ScoreBreakdown] = []
        for item in payload:
            alias = str(item.get("alias"))
            canonical = str(item.get("canonical"))
            postings = int(item.get("posting_volume", 0))
            last_seen = item.get("last_seen")
            evidence = item.get("evidence") or []
            variants = item.get("variants") or []
            breakdown = self.scoreWithEvidence(
                alias,
                canonical,
                evidence,
                postings,
                last_seen,
                total_postings=total_postings,
                alias_variants=variants,
                decay_rate=decay_rate,
            )
            results.append(breakdown)
        return results

    def validateAgainstGoldStandard(
        self,
        predictions: Mapping[str, str],
        gold_standard: Mapping[str, str],
    ) -> Dict[str, float]:
        tp = fp = fn = 0
        for alias, predicted in predictions.items():
            gold = gold_standard.get(alias)
            if gold is None:
                fp += 1
            elif gold == predicted:
                tp += 1
            else:
                fp += 1
        for alias, truth in gold_standard.items():
            if alias not in predictions:
                fn += 1
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        if precision + recall == 0:
            f1 = 0.0
        else:
            f1 = 2 * precision * recall / (precision + recall)
        logger.info(
            "Gold standard validation tp=%s fp=%s fn=%s precision=%.4f recall=%.4f f1=%.4f",
            tp,
            fp,
            fn,
            precision,
            recall,
            f1,
        )
        return {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
        }
