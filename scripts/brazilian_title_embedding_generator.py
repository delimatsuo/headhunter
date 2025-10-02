"""Brazilian title embedding generator using existing embedding infrastructure."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import importlib

try:
    from scripts import clustering_dao
except ModuleNotFoundError:  # pragma: no cover - optional dependency during tests
    clustering_dao = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def _ensure_logger_configured() -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")


def _load_embedding_service() -> Any:
    module = importlib.import_module("scripts.embedding_service")
    if hasattr(module, "EmbeddingService"):
        return module.EmbeddingService()
    if hasattr(module, "get_embedding_service"):
        return module.get_embedding_service()
    raise AttributeError("Embedding service implementation not found in scripts.embedding_service")


def _load_pgvector_store() -> Any:
    try:
        module = importlib.import_module("scripts.pgvector_store_adapter")
    except ModuleNotFoundError:
        module = importlib.import_module("scripts.pgvector_store")
    if hasattr(module, "PgVectorStoreAdapter"):
        return module.PgVectorStoreAdapter()
    if hasattr(module, "get_store"):
        return module.get_store()
    raise AttributeError("Pgvector store implementation not found")


def _load_normalizer() -> Any:
    module = importlib.import_module("scripts.eco_title_normalizer")
    if hasattr(module, "EcoTitleNormalizer"):
        return module.EcoTitleNormalizer()
    if hasattr(module, "BrazilianPortugueseNormalizer"):
        return module.BrazilianPortugueseNormalizer()
    if hasattr(module, "normalize_title"):
        return module
    raise AttributeError("Normalizer implementation not found")


@dataclass
class EmbeddingJobConfig:
    dataset_path: Path
    batch_size: int = 64
    chunk_type: str = "job_title"
    overwrite: bool = False
    incremental: bool = True
    expected_dim: int = 768


class BrazilianTitleEmbeddingGenerator:
    """Generates embeddings for Brazilian job titles and stores them in pgvector."""

    def __init__(self, config: EmbeddingJobConfig) -> None:
        _ensure_logger_configured()
        self.config = config
        self.embedding_service = _load_embedding_service()
        self.store = _load_pgvector_store()
        self.normalizer = _load_normalizer()
        logger.debug("Initialized embedding generator with %s", config)

    def run(self) -> Dict[str, Any]:
        dataset = self._load_dataset()
        logger.info("Loaded %d normalized titles from %s", len(dataset), self.config.dataset_path)
        already_indexed = set()
        if self.config.incremental:
            already_indexed = self._load_existing_titles()
            logger.info("Found %d titles already embedded", len(already_indexed))
        to_embed = [entry for entry in dataset if not self._should_skip(entry, already_indexed)]
        logger.info("Preparing to embed %d new titles", len(to_embed))
        processed = self._process_batches(to_embed)
        metrics = {
            "total_titles": len(dataset),
            "new_embeddings": processed,
            "skipped": len(dataset) - processed,
            "expected_dimension": self.config.expected_dim,
        }
        logger.info("Embedding generation completed: %s", metrics)
        return metrics

    def _load_dataset(self) -> List[Mapping[str, Any]]:
        with self.config.dataset_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        titles = payload.get("titles") if isinstance(payload, Mapping) else payload
        if isinstance(titles, Mapping):
            return [self._expand_title(k, v) for k, v in titles.items()]
        return [self._expand_title(str(entry.get("normalized_title")), entry) for entry in titles]

    def _expand_title(self, key: str, value: Mapping[str, Any]) -> Mapping[str, Any]:
        normalized = value.get("normalized_title") or key
        canonical = value.get("canonical_title") or value.get("raw_title") or normalized
        return {
            "normalized_title": self._normalize(normalized),
            "canonical_title": canonical,
            "frequency": value.get("frequency", 1),
            "sources": value.get("sources", {}),
        }

    def _normalize(self, title: str) -> str:
        if hasattr(self.normalizer, "normalize"):
            return self.normalizer.normalize(title)
        if hasattr(self.normalizer, "normalize_title"):
            return self.normalizer.normalize_title(title)
        if hasattr(self.normalizer, "__call__"):
            return self.normalizer(title)
        return title

    def _load_existing_titles(self) -> set[str]:
        if hasattr(self.store, "list_chunk_ids"):
            records = self.store.list_chunk_ids(chunk_type=self.config.chunk_type)
            return set(records)
        if hasattr(self.store, "list_titles"):
            return set(self.store.list_titles(chunk_type=self.config.chunk_type))
        logger.warning("PgVector store does not expose listing API; skipping incremental detection")
        return set()

    def _should_skip(self, entry: Mapping[str, Any], existing: set[str]) -> bool:
        normalized = entry["normalized_title"]
        if self.config.overwrite:
            return False
        return normalized in existing

    def _process_batches(self, entries: Sequence[Mapping[str, Any]]) -> int:
        total_processed = 0
        batch: List[Mapping[str, Any]] = []
        for entry in entries:
            batch.append(entry)
            if len(batch) >= self.config.batch_size:
                self._process_single_batch(batch)
                total_processed += len(batch)
                batch = []
        if batch:
            self._process_single_batch(batch)
            total_processed += len(batch)
        return total_processed

    def _process_single_batch(self, batch: Sequence[Mapping[str, Any]]) -> None:
        texts = [entry["canonical_title"] for entry in batch]
        logger.debug("Embedding batch of %d titles", len(texts))
        embeddings = self._embed_texts(texts)
        if len(embeddings) != len(batch):
            raise RuntimeError("Embedding service returned mismatched embedding count")
        self._validate_embeddings(embeddings)
        payload = []
        for entry, vector in zip(batch, embeddings):
            payload.append(
                {
                    "chunk_id": entry["normalized_title"],
                    "chunk_type": self.config.chunk_type,
                    "text": entry["canonical_title"],
                    "metadata": {
                        "normalized_title": entry["normalized_title"],
                        "frequency": entry.get("frequency", 1),
                        "sources": entry.get("sources", {}),
                    },
                    "embedding": vector,
                }
            )
        logger.debug("Writing %d embeddings to pgvector", len(payload))
        self._upsert_embeddings(payload)
        self._persist_title_embeddings(payload)

    def _embed_texts(self, texts: Sequence[str]) -> List[Sequence[float]]:
        if hasattr(self.embedding_service, "embed_texts"):
            return self.embedding_service.embed_texts(texts)
        if hasattr(self.embedding_service, "get_embeddings"):
            return self.embedding_service.get_embeddings(texts)
        return [self.embedding_service.embed(text) for text in texts]

    def _validate_embeddings(self, embeddings: Sequence[Sequence[float]]) -> None:
        expected = self.config.expected_dim
        mismatches = [idx for idx, vector in enumerate(embeddings) if len(vector) != expected]
        if mismatches:
            raise ValueError(f"Embedding dimension mismatch at indices {mismatches}; expected {expected}")

    def _upsert_embeddings(self, payload: Sequence[Mapping[str, Any]]) -> None:
        if hasattr(self.store, "upsert_chunks"):
            self.store.upsert_chunks(payload)
            return
        if hasattr(self.store, "upsert_batch"):
            self.store.upsert_batch(payload)
            return
        if hasattr(self.store, "index_embeddings"):
            self.store.index_embeddings(payload)
            return
        raise AttributeError("PgVector store does not expose an upsert method")

    def _persist_title_embeddings(self, payload: Sequence[Mapping[str, Any]]) -> None:
        if clustering_dao is None or not hasattr(clustering_dao, "upsert_title_embedding"):
            return
        for entry in payload:
            metadata = dict(entry.get("metadata") or {})
            normalized = metadata.get("normalized_title") or entry.get("chunk_id")
            if not normalized:
                continue
            canonical = entry.get("text") or metadata.get("canonical_title") or normalized
            frequency = int(metadata.get("frequency", 1))
            chunk_type = entry.get("chunk_type", self.config.chunk_type)
            try:
                self._run_async(
                    lambda nt=normalized, ct=canonical, emb=list(entry.get("embedding") or []),
                    ch=chunk_type, freq=frequency, meta=dict(metadata):
                    clustering_dao.upsert_title_embedding(
                        normalized_title=nt,
                        canonical_title=ct,
                        embedding=emb,
                        chunk_type=ch,
                        frequency=freq,
                        metadata=meta,
                    )
                )
            except Exception as exc:  # pragma: no cover - database optional in tests
                logger.warning("Failed to persist clustering embedding for %s: %s", normalized, exc)
                break

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


def _parse_args(argv: Optional[Sequence[str]] = None) -> Any:
    import argparse

    parser = argparse.ArgumentParser(description="Generate embeddings for Brazilian job titles")
    parser.add_argument("dataset", help="Path to normalized dataset JSON from data loader")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--chunk-type", default="job_title")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--no-incremental", dest="incremental", action="store_false")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = _parse_args(argv)
    config = EmbeddingJobConfig(
        dataset_path=Path(args.dataset),
        batch_size=args.batch_size,
        chunk_type=args.chunk_type,
        overwrite=args.overwrite,
        incremental=args.incremental,
    )
    generator = BrazilianTitleEmbeddingGenerator(config)
    generator.run()


if __name__ == "__main__":
    main()
