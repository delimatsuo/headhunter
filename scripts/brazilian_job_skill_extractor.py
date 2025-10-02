#!/usr/bin/env python3
"""Brazilian job posting skill extractor for ECO templates.

This module analyses Brazilian Portuguese job postings and produces structured
skill requirement intelligence for ECO template generation. It combines the
existing Together AI integration with statistical aggregation so we can derive
required vs preferred skills, frequency-weighted confidence scores, and
comprehensive evidence metadata per ECO occupation.

Key capabilities
----------------
1. Loads normalized job posting payloads emitted by the eco_scraper collectors.
2. Uses Together's Qwen 2.5 32B model (or a local heuristic fallback) to extract
   structured skill observations for each posting.
3. Applies Bayesian frequency analysis with posting volume weighting to
   transform noisy observations into stable confidence scores.
4. Classifies skills as required vs preferred by combining Portuguese language
   cues with observed frequency across the occupation corpus.
5. Normalises Portuguese skill terminology and groups skills into high level
   taxonomies (Frontend, Backend, Dados, DevOps, QA, Gestão, Generalista).
6. Emits incremental friendly JSON so long-running backfills can resume without
   reprocessing historical postings.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple
import re
import unicodedata

try:
    from scripts.together_client import TogetherAIClient, TogetherAIError
except ModuleNotFoundError:  # pragma: no cover - tests may stub the client
    TogetherAIClient = None  # type: ignore
    TogetherAIError = RuntimeError  # type: ignore

logger = logging.getLogger(__name__)


REQUIRED_KEYWORDS = [
    r"obrigat[oó]rio",
    r"necess[aá]rio",
    r"indispens[aá]vel",
    r"requer",
    r"imprescind[ií]vel",
]

PREFERRED_KEYWORDS = [
    r"desej[aá]vel",
    r"diferencial",
    r"ser[aá] um extra",
    r"plus",
    r"nice to have",
]

SKILL_TAXONOMY = {
    "frontend": {"react", "javascript", "typescript", "angular", "vue"},
    "backend": {"java", "python", "node", "golang", "c#", "dotnet", "spring"},
    "dados": {"sql", "spark", "pyspark", "etl", "data", "hadoop", "power bi"},
    "devops": {"kubernetes", "docker", "terraform", "aws", "ci/cd", "azure", "gcp"},
    "qa": {"qa", "quality", "teste", "automation", "cypress", "selenium"},
    "gestao": {"scrum", "kanban", "lideran", "gest", "product owner", "project"},
}

DEFAULT_TAXONOMY = "generalista"


TECH_TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9+.#/\-]*")
HEURISTIC_WHITELIST = {"c#", "c++", "node.js", "react-native"}


@dataclass
class SkillExtractorConfig:
    """Runtime configuration for the extractor."""

    input_paths: Sequence[Path]
    output_path: Path
    model: str = "Qwen/Qwen2.5-32B-Instruct"
    batch_size: int = 16
    max_concurrent_requests: int = 4
    occupation_field: str = "eco_occupation"
    job_text_field: str = "description"
    location_field: str = "location"
    posting_id_field: str = "posting_id"
    source_field: str = "source"
    min_frequency_threshold: int = 2
    min_confidence_threshold: float = 0.35
    resume_state_path: Optional[Path] = None
    incremental: bool = True
    enable_llm: bool = True
    limit: Optional[int] = None


@dataclass
class SkillObservation:
    """Single skill observation returned by the LLM or heuristic extractor."""

    skill: str
    category: str  # "required" | "preferred"
    confidence: float
    source: Optional[str]
    posting_id: Optional[str]
    occupation: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillAggregate:
    """Aggregated statistics for a given skill inside an occupation."""

    skill: str
    taxonomy: str
    required_hits: int = 0
    preferred_hits: int = 0
    postings: set[str] = field(default_factory=set)
    weighted_confidence: float = 0.0
    weight_sum: float = 0.0
    sources: Counter = field(default_factory=Counter)
    last_seen_timestamp: Optional[str] = None

    def register(self, observation: SkillObservation, weight: float, timestamp: Optional[str]) -> None:
        if observation.category == "required":
            self.required_hits += 1
        else:
            self.preferred_hits += 1
        if observation.posting_id:
            self.postings.add(observation.posting_id)
        self.weighted_confidence += weight * observation.confidence
        self.weight_sum += weight
        if observation.source:
            self.sources[observation.source] += 1
        if timestamp:
            self.last_seen_timestamp = max(self.last_seen_timestamp or timestamp, timestamp)

    def serialize(self, total_postings: int, alpha: float, beta: float) -> Dict[str, Any]:
        occurrences = self.required_hits + self.preferred_hits
        bayesian_confidence = (occurrences + alpha) / (total_postings + alpha + beta)
        weighted_confidence = self.weighted_confidence / self.weight_sum if self.weight_sum else 0.0
        combined_confidence = float(min(1.0, 0.4 * bayesian_confidence + 0.6 * weighted_confidence))
        evidence_level = len(self.postings)
        distribution = {
            "required": self.required_hits,
            "preferred": self.preferred_hits,
            "postings": evidence_level,
            "samples": sorted(self.postings)[:20],
        }
        return {
            "skill": self.skill,
            "taxonomy": self.taxonomy,
            "confidence": round(combined_confidence, 4),
            "distribution": distribution,
            "sources": dict(self.sources),
            "last_seen": self.last_seen_timestamp,
        }


class SkillStatisticsAggregator:
    """Accumulates skill evidence per ECO occupation."""

    def __init__(self, alpha: float = 2.0, beta: float = 3.0) -> None:
        self.alpha = alpha
        self.beta = beta
        self._occupation_postings: Dict[str, set[str]] = defaultdict(set)
        self._skills: Dict[str, Dict[str, SkillAggregate]] = defaultdict(dict)
        self._occupation_metadata: Dict[str, Dict[str, Any]] = defaultdict(dict)

    def register_observation(self, observation: SkillObservation, weight: float, timestamp: Optional[str]) -> None:
        occupation = observation.occupation
        skill_key = observation.skill
        occupation_map = self._skills[occupation]
        if skill_key not in occupation_map:
            occupation_map[skill_key] = SkillAggregate(skill=observation.skill, taxonomy=_infer_taxonomy(observation.skill))
        occupation_map[skill_key].register(observation, weight, timestamp)

    def register_posting(self, occupation: str, posting_id: Optional[str]) -> int:
        if not posting_id:
            return len(self._occupation_postings.get(occupation, set()))
        postings = self._occupation_postings[occupation]
        postings.add(posting_id)
        return len(postings)

    def register_metadata(self, occupation: str, **metadata: Any) -> None:
        self._occupation_metadata[occupation].update(metadata)

    def occupation_posting_count(self, occupation: str) -> int:
        return len(self._occupation_postings.get(occupation, set()))

    def to_payload(self, min_frequency: int, min_confidence: float) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for occupation, aggregate_map in self._skills.items():
            total_postings = max(1, self.occupation_posting_count(occupation))
            required_list: List[Dict[str, Any]] = []
            preferred_list: List[Dict[str, Any]] = []
            for aggregate in aggregate_map.values():
                data = aggregate.serialize(total_postings, self.alpha, self.beta)
                occurrences = aggregate.required_hits + aggregate.preferred_hits
                if occurrences < min_frequency or data["confidence"] < min_confidence:
                    continue
                if aggregate.required_hits >= aggregate.preferred_hits:
                    required_list.append(data)
                else:
                    preferred_list.append(data)
            if not required_list and not preferred_list:
                continue
            required_list.sort(key=lambda item: item["confidence"], reverse=True)
            preferred_list.sort(key=lambda item: item["confidence"], reverse=True)
            result[occupation] = {
                "occupation": occupation,
                "required_skills": required_list,
                "preferred_skills": preferred_list,
                "total_observations": total_postings,
                "metadata": self._occupation_metadata.get(occupation, {}),
            }
        return result


def _normalize_skill(text: str) -> str:
    text = (text or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9+#/\-\.\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _infer_taxonomy(skill: str) -> str:
    normalized = _normalize_skill(skill)
    for taxonomy, keywords in SKILL_TAXONOMY.items():
        if any(keyword in normalized for keyword in keywords):
            return taxonomy
    return DEFAULT_TAXONOMY


def _estimate_weight(posting: Mapping[str, Any]) -> float:
    # Posting weight increases with more descriptive content and recency (if available)
    description = posting.get("description") or posting.get("job_description") or ""
    word_count = len(str(description).split())
    base = 1.0 + min(2.0, word_count / 500)
    freshness = posting.get("posted_at") or posting.get("published_at")
    if freshness:
        # Simple recency heuristic: more recent postings up-weighted slightly
        return base * 1.1
    return base


def _classify_skill_from_text(skill: str, context: str) -> str:
    for pattern in REQUIRED_KEYWORDS:
        if re.search(pattern, context, re.IGNORECASE):
            return "required"
    for pattern in PREFERRED_KEYWORDS:
        if re.search(pattern, context, re.IGNORECASE):
            return "preferred"
    # Default classification based on heuristics: popular Portuguese verbs
    if re.search(r"precisamos|necessitamos|respons[aá]vel", context, re.IGNORECASE):
        return "required"
    return "preferred"


class BrazilianJobSkillExtractor:
    """High level orchestrator that extracts skill requirements from postings."""

    def __init__(self, config: SkillExtractorConfig, client: Optional[TogetherAIClient] = None) -> None:
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
        self.config = config
        self.client = client
        self._aggregator = SkillStatisticsAggregator()
        self._seen_postings: set[str] = set()
        if self.config.enable_llm and self.client is None:
            if TogetherAIClient is None:
                raise RuntimeError("TogetherAIClient is not available; set enable_llm=False for tests")
            self.client = TogetherAIClient(model=self.config.model)
        if self.config.resume_state_path and self.config.resume_state_path.exists():
            self._resume_from_state(self.config.resume_state_path)

    def run(self) -> Dict[str, Any]:
        logger.info("Starting Brazilian job skill extraction pipeline")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._process_all())
        finally:
            loop.close()
        payload = self._aggregator.to_payload(
            min_frequency=self.config.min_frequency_threshold,
            min_confidence=self.config.min_confidence_threshold,
        )
        self._write_output(payload)
        logger.info("Skill extraction pipeline finished | occupations=%d", len(payload))
        return payload

    async def _process_all(self) -> None:
        semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
        tasks: List[asyncio.Task[None]] = []
        for idx, posting in enumerate(self._iter_postings()):
            if self.config.limit and idx >= self.config.limit:
                break
            posting_id = str(posting.get(self.config.posting_id_field) or f"posting-{idx}")
            if posting_id in self._seen_postings:
                continue
            self._seen_postings.add(posting_id)
            occupation = _ensure_occupation(posting.get(self.config.occupation_field))
            total = self._aggregator.register_posting(occupation, posting_id)
            self._aggregator.register_metadata(occupation, total_postings=total)
            task = asyncio.create_task(self._handle_posting(posting, semaphore))
            tasks.append(task)
        if tasks:
            await asyncio.gather(*tasks)

    async def _handle_posting(self, posting: Mapping[str, Any], semaphore: asyncio.Semaphore) -> None:
        occupation = _ensure_occupation(posting.get(self.config.occupation_field))
        if not occupation:
            logger.debug("Skipping posting without occupation: %s", posting.get(self.config.posting_id_field))
            return
        weight = _estimate_weight(posting)
        timestamp = posting.get("posted_at") or posting.get("published_at")
        try:
            observations = await self._extract_skills_from_posting(posting, semaphore)
        except Exception as exc:  # noqa: BLE001 - we log and continue so one failure does not kill the batch
            logger.warning("Failed to extract skills for posting %s | err=%s", posting.get(self.config.posting_id_field), exc)
            return
        for observation in observations:
            normalized_skill = _normalize_skill(observation.skill)
            if not normalized_skill:
                continue
            obs = SkillObservation(
                skill=normalized_skill,
                category=observation.category,
                confidence=max(0.0, min(1.0, observation.confidence)),
                source=observation.source,
                posting_id=observation.posting_id,
                occupation=occupation,
                metadata=observation.metadata,
            )
            self._aggregator.register_observation(obs, weight=weight, timestamp=timestamp)

    async def _extract_skills_from_posting(
        self,
        posting: Mapping[str, Any],
        semaphore: asyncio.Semaphore,
    ) -> Sequence[SkillObservation]:
        if not self.config.enable_llm:
            return self._heuristic_extraction(posting)
        if TogetherAIClient is None:
            raise RuntimeError("TogetherAIClient is not available; set enable_llm=False for tests")
        if self.client is None:
            raise RuntimeError("TogetherAI client was not initialised despite enable_llm=True")
        async with semaphore:
            prompt = self._build_prompt(posting)
            try:
                response = await self.client.chat_completion(
                    [
                        {
                            "role": "system",
                            "content": "Você é um especialista em mercado de trabalho brasileiro. Extraia habilidades obrigatórias e desejáveis em JSON estruturado.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=800,
                    temperature=0.1,
                    top_p=0.9,
                )
            except TogetherAIError as exc:  # pragma: no cover - depends on real API failures
                logger.warning("Together completion failed (%s); falling back to heuristics", exc)
                return self._heuristic_extraction(posting)
            return self._parse_llm_payload(response, posting)

    def _heuristic_extraction(self, posting: Mapping[str, Any]) -> Sequence[SkillObservation]:
        description = str(posting.get(self.config.job_text_field) or "")
        occupation = _ensure_occupation(posting.get(self.config.occupation_field))
        posting_id = str(posting.get(self.config.posting_id_field) or "unknown")
        source = posting.get(self.config.source_field)
        normalized_description = _normalize_skill(description)
        raw_tokens = set(TECH_TOKEN_PATTERN.findall(normalized_description))
        raw_tokens.update({token for token in HEURISTIC_WHITELIST if token in normalized_description})
        candidate_skills = {
            tok
            for tok in raw_tokens
            if (len(tok) > 2 or tok in HEURISTIC_WHITELIST) and any(ch.isalpha() for ch in tok)
        }
        observations: List[SkillObservation] = []
        for token in candidate_skills:
            context = _context_window(normalized_description, token)
            category = _classify_skill_from_text(token, context)
            confidence = 0.55 if category == "required" else 0.4
            observations.append(
                SkillObservation(
                    skill=token,
                    category=category,
                    confidence=confidence,
                    source=source,
                    posting_id=posting_id,
                    occupation=occupation,
                    metadata={"heuristic": True},
                )
            )
        return observations

    def _parse_llm_payload(self, response: str, posting: Mapping[str, Any]) -> Sequence[SkillObservation]:
        try:
            payload = json.loads(response)
        except json.JSONDecodeError:
            logger.debug("LLM returned non JSON payload; applying repair heuristics")
            payload = _repair_json(response)
        occupation = _ensure_occupation(posting.get(self.config.occupation_field))
        posting_id = str(posting.get(self.config.posting_id_field) or "unknown")
        source = posting.get(self.config.source_field)
        observations: List[SkillObservation] = []
        for category in ("required_skills", "preferred_skills"):
            for entry in payload.get(category, []):
                skill_name = entry.get("skill") or entry.get("name")
                if not skill_name:
                    continue
                confidence = float(entry.get("confidence", 0.6 if category == "required_skills" else 0.4))
                reasoning = entry.get("reasoning")
                observations.append(
                    SkillObservation(
                        skill=skill_name,
                        category="required" if category == "required_skills" else "preferred",
                        confidence=max(0.0, min(1.0, confidence / 100 if confidence > 1 else confidence)),
                        source=source,
                        posting_id=posting_id,
                        occupation=occupation,
                        metadata={"reasoning": reasoning, "llm": True},
                    )
                )
        if not observations:
            logger.debug("LLM payload missing expected keys; falling back to heuristics")
            return self._heuristic_extraction(posting)
        return observations

    def _build_prompt(self, posting: Mapping[str, Any]) -> str:
        occupation = posting.get(self.config.occupation_field) or "ocupação desconhecida"
        company = posting.get("company") or posting.get("employer") or "empresa não informada"
        location = posting.get(self.config.location_field) or "Local não informado"
        description = posting.get(self.config.job_text_field) or posting.get("job_description") or ""
        return (
            "Analise a vaga abaixo e devolva JSON com arrays `required_skills` e `preferred_skills`. "
            "Cada item deve ter os campos: skill (string), confidence (0-1 ou 0-100), reasoning (breve explicação).\n\n"
            f"Ocupação ECO: {occupation}\n"
            f"Empresa: {company}\n"
            f"Local: {location}\n"
            "Descrição da vaga (português brasileiro):\n"
            f"""{description}"""
        )

    def _iter_postings(self) -> Iterable[Mapping[str, Any]]:
        for path in self.config.input_paths:
            if not path.exists():
                logger.warning("Input dataset %s does not exist; skipping", path)
                continue
            if path.suffix.lower() == ".jsonl":
                yield from self._iter_jsonl(path)
            elif path.suffix.lower() == ".json":
                with path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                    entries = payload if isinstance(payload, list) else payload.get("postings", [])
                    for entry in entries:
                        yield entry
            else:
                logger.warning("Unsupported dataset format for %s; expected json/jsonl", path)

    def _iter_jsonl(self, path: Path) -> Iterable[Mapping[str, Any]]:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    logger.debug("Skipping malformed JSONL line in %s", path)
                    continue

    def _write_output(self, payload: Mapping[str, Any]) -> None:
        self.config.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config.output_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        if self.config.resume_state_path:
            with self.config.resume_state_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)

    def _resume_from_state(self, state_path: Path) -> None:
        try:
            with state_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except json.JSONDecodeError:  # pragma: no cover - defensive
            logger.warning("Existing state at %s is corrupted; ignoring", state_path)
            return
        occupation_postings: Dict[str, set[str]] = defaultdict(set)
        occupation_metadata: Dict[str, Dict[str, Any]] = {}
        for occupation, data in payload.items():
            for category in ("required_skills", "preferred_skills"):
                for entry in data.get(category, []):
                    skill_name = _normalize_skill(entry.get("skill", ""))
                    distribution = entry.get("distribution", {})
                    sample_ids = {
                        str(sample)
                        for sample in distribution.get("samples", [])
                        if isinstance(sample, (str, int)) and str(sample)
                    }
                    occupation_postings[occupation].update(sample_ids)
                    aggregate = SkillAggregate(
                        skill=skill_name,
                        taxonomy=entry.get("taxonomy", DEFAULT_TAXONOMY),
                        required_hits=int(distribution.get("required", 0)),
                        preferred_hits=int(distribution.get("preferred", 0)),
                        postings=sample_ids,
                        weighted_confidence=float(entry.get("confidence", 0.0)),
                        weight_sum=max(1.0, len(sample_ids)),
                        sources=Counter(entry.get("sources", {})),
                        last_seen_timestamp=entry.get("last_seen"),
                    )
                    self._skills_for(occupation)[aggregate.skill] = aggregate
            metadata = data.get("metadata", {}) if isinstance(data, dict) else {}
            if isinstance(metadata, dict) and metadata:
                self._aggregator.register_metadata(occupation, **metadata)
                occupation_metadata[occupation] = metadata
        for occupation, postings in occupation_postings.items():
            metadata = occupation_metadata.get(occupation, {})
            payload_entry = payload.get(occupation, {}) if isinstance(payload.get(occupation), Mapping) else {}
            raw_total = metadata.get("total_postings") if metadata else None
            if raw_total in (None, 0, "0", 0.0) and isinstance(payload_entry, Mapping):
                raw_total = payload_entry.get("total_observations")
            try:
                metadata_total = int(raw_total) if raw_total is not None else 0
            except (TypeError, ValueError):
                metadata_total = 0
            if metadata_total > len(postings):
                needed = metadata_total - len(postings)
                for idx in range(needed):
                    postings.add(f"{occupation}::resume::{idx}")
            for posting_id in postings:
                self._aggregator.register_posting(occupation, posting_id)
                self._seen_postings.add(posting_id)
            total_postings = metadata_total or len(postings)
            if total_postings:
                self._aggregator.register_metadata(occupation, total_postings=total_postings)

    def _skills_for(self, occupation: str) -> Dict[str, SkillAggregate]:
        return self._aggregator._skills[occupation]


def _repair_json(raw: str) -> Dict[str, Any]:
    try:
        candidate = raw[raw.index("{") : raw.rindex("}") + 1]
        return json.loads(candidate)
    except Exception as exc:  # noqa: BLE001 - best effort repair; fall back to empty payload
        logger.debug("Failed to repair JSON payload (%s); returning empty response", exc)
        return {"required_skills": [], "preferred_skills": []}


def _context_window(text: str, token: str, window: int = 80) -> str:
    idx = text.lower().find(token.lower())
    if idx == -1:
        return text[: window * 2]
    start = max(0, idx - window)
    end = min(len(text), idx + len(token) + window)
    return text[start:end]


def _ensure_occupation(raw: Any) -> str:
    if not raw:
        return "ocupacao_nao_informada"
    normalized = _normalize_skill(str(raw))
    return normalized.replace(" ", "_")


def load_skill_templates(
    input_paths: Sequence[str],
    output_path: str,
    *,
    enable_llm: bool = False,
    model: str = "Qwen/Qwen2.5-32B-Instruct",
) -> Dict[str, Any]:
    """Convenience function for scripts/tests."""

    config = SkillExtractorConfig(
        input_paths=[Path(path) for path in input_paths],
        output_path=Path(output_path),
        enable_llm=enable_llm,
        model=model,
    )
    extractor = BrazilianJobSkillExtractor(config)
    return extractor.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract skill requirements from Brazilian job postings")
    parser.add_argument("inputs", nargs="+", help="Paths to job posting JSON/JSONL datasets")
    parser.add_argument("--output", required=True, help="Output JSON file for skill templates")
    parser.add_argument("--model", default="Qwen/Qwen2.5-32B-Instruct", help="Together model identifier")
    parser.add_argument("--disable-llm", action="store_true", help="Use heuristic extraction only (offline mode)")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for debugging")
    parser.add_argument("--min-frequency", type=int, default=2)
    parser.add_argument("--min-confidence", type=float, default=0.35)
    args = parser.parse_args()

    cfg = SkillExtractorConfig(
        input_paths=[Path(path) for path in args.inputs],
        output_path=Path(args.output),
        model=args.model,
        enable_llm=not args.disable_llm,
        min_frequency_threshold=args.min_frequency,
        min_confidence_threshold=args.min_confidence,
        limit=args.limit,
    )
    extractor = BrazilianJobSkillExtractor(cfg)
    extractor.run()
