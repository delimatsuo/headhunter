import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


import numpy as np
import pytest

# --- Fixtures -----------------------------------------------------------------

@pytest.fixture(autouse=True)
def stub_normalizer(monkeypatch):
    module = types.ModuleType("scripts.eco_title_normalizer")

    class _Normalizer:
        def normalize(self, text: str) -> str:
            return text.lower()

    module.EcoTitleNormalizer = _Normalizer
    module.normalize_title = lambda text: text.lower()
    sys.modules["scripts.eco_title_normalizer"] = module
    yield
    sys.modules.pop("scripts.eco_title_normalizer", None)


@pytest.fixture(autouse=True)
def stub_embedding_service(monkeypatch):
    module = types.ModuleType("scripts.embedding_service")

    class _EmbeddingService:
        def embed_texts(self, texts):
            return [[float(len(text))] * 4 for text in texts]

    module.EmbeddingService = _EmbeddingService
    sys.modules["scripts.embedding_service"] = module
    yield
    sys.modules.pop("scripts.embedding_service", None)


@pytest.fixture(autouse=True)
def stub_alias_scorer(monkeypatch):
    module = types.ModuleType("scripts.alias_confidence_scorer")

    class _AliasScorer:
        def score(self, alias, canonical):
            return 0.8 if canonical and alias.lower() in canonical.lower() else 0.5

    module.AliasConfidenceScorer = _AliasScorer
    sys.modules["scripts.alias_confidence_scorer"] = module
    yield
    sys.modules.pop("scripts.alias_confidence_scorer", None)


@pytest.fixture(autouse=True)
def stub_threadpoolctl(monkeypatch):
    try:
        import threadpoolctl  # type: ignore
    except ImportError:
        module = types.ModuleType("threadpoolctl")
        module.threadpool_info = lambda: []
        sys.modules["threadpoolctl"] = module
        yield
        sys.modules.pop("threadpoolctl", None)
    else:
        monkeypatch.setattr(threadpoolctl, "threadpool_info", lambda: [])
        yield


@pytest.fixture(autouse=True)
def stub_pgvector_store(monkeypatch):
    store_module = types.ModuleType("scripts.pgvector_store")
    adapter_module = types.ModuleType("scripts.pgvector_store_adapter")

    class _FakeStore:
        data = {"chunks": {}}

        def __init__(self):
            self.__class__.data.setdefault("chunks", {})

        def upsert_chunks(self, payload):
            for item in payload:
                self.__class__.data["chunks"][item["chunk_id"]] = item

        def list_chunk_ids(self, chunk_type="job_title"):
            return [chunk_id for chunk_id, record in self.__class__.data["chunks"].items() if record["chunk_type"] == chunk_type]

        def list_embeddings(self, chunk_type="job_title"):
            return [record for record in self.__class__.data["chunks"].values() if record["chunk_type"] == chunk_type]

    store_module.PgVectorStore = _FakeStore
    store_module.get_store = lambda *args, **kwargs: _FakeStore()
    adapter_module.PgVectorStoreAdapter = _FakeStore
    adapter_module.get_store = lambda *args, **kwargs: _FakeStore()
    sys.modules["scripts.pgvector_store"] = store_module
    sys.modules["scripts.pgvector_store_adapter"] = adapter_module
    yield
    _FakeStore.data = {"chunks": {}}
    sys.modules.pop("scripts.pgvector_store", None)
    sys.modules.pop("scripts.pgvector_store_adapter", None)


@pytest.fixture(autouse=True)
def stub_clustering_dao():
    module = types.ModuleType("scripts.clustering_dao")

    async def upsert_title_embedding(**_kwargs):
        return None

    async def bulk_upsert_title_clusters(_entries):
        return None

    async def upsert_career_progression(**_kwargs):
        return None

    module.upsert_title_embedding = upsert_title_embedding
    module.bulk_upsert_title_clusters = bulk_upsert_title_clusters
    module.upsert_career_progression = upsert_career_progression
    sys.modules["scripts.clustering_dao"] = module
    yield
    sys.modules.pop("scripts.clustering_dao", None)


@pytest.fixture(autouse=True)
def stub_monitor_progress(monkeypatch):
    module = types.ModuleType("scripts.monitor_progress")
    events = []

    def record_event(payload):
        events.append(payload)

    module.record_event = record_event
    module._events = events
    sys.modules["scripts.monitor_progress"] = module
    yield
    sys.modules.pop("scripts.monitor_progress", None)


# --- Tests --------------------------------------------------------------------

def test_data_loader_deduplicates_titles(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    payload = {"title": "Engenheiro de Software", "company": "Empresa", "location": "São Paulo", "posted_at": "2024-01-01T00:00:00"}
    with dataset.open("w", encoding="utf-8") as handle:
        for _ in range(3):
            handle.write(json.dumps(payload) + "\n")
    from scripts.brazilian_job_data_loader import load_from_sources

    output_path = tmp_path / "output.json"
    result = load_from_sources([str(dataset)], str(output_path))
    assert result["metrics"]["total_titles"] == 1
    assert output_path.exists()
    assert "quality" in result


def test_data_loader_incremental_merge(tmp_path):
    from scripts.brazilian_job_data_loader import load_from_sources

    dataset1 = tmp_path / "dataset1.jsonl"
    dataset2 = tmp_path / "dataset2.jsonl"
    record1 = {"title": "Engenheiro de Software", "company": "Empresa", "posted_at": "2024-01-01T00:00:00"}
    record2 = {"title": "Engenheiro de Software", "company": "Empresa", "posted_at": "2024-01-02T00:00:00"}
    with dataset1.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(record1) + "\n")
    with dataset2.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(record2) + "\n")
    output_path = tmp_path / "output.json"
    load_from_sources([str(dataset1)], str(output_path), parallelism=2)
    merged = load_from_sources([str(dataset2)], str(output_path), parallelism=2)
    titles = merged["titles"]
    assert titles["engenheiro de software"]["frequency"] == 2


def test_embedding_generator_stores_vectors(tmp_path):
    normalized = {
        "titles": {
            "engenheiro de software": {
                "normalized_title": "engenheiro de software",
                "canonical_title": "Engenheiro de Software",
                "frequency": 5,
                "sources": {"dataset": 5},
            }
        }
    }
    dataset_path = tmp_path / "normalized.json"
    with dataset_path.open("w", encoding="utf-8") as handle:
        json.dump(normalized, handle)
    from scripts.brazilian_title_embedding_generator import BrazilianTitleEmbeddingGenerator, EmbeddingJobConfig

    config = EmbeddingJobConfig(dataset_path=dataset_path, batch_size=1, expected_dim=4)
    generator = BrazilianTitleEmbeddingGenerator(config)
    metrics = generator.run()
    assert metrics["new_embeddings"] == 1


@pytest.mark.parametrize("method", ["dbscan", "kmeans"] )
def test_clustering_engine_returns_clusters(method, monkeypatch):
    from scripts.job_title_clustering_engine import JobTitleClusteringEngine, ClusteringConfig
    store = sys.modules["scripts.pgvector_store"].PgVectorStore()
    store.upsert_chunks(
        [
            {"chunk_id": "engenheiro", "chunk_type": "job_title", "text": "Engenheiro", "metadata": {"frequency": 3, "sources": {"a": 3}}, "embedding": [0.1, 0.2, 0.3, 0.4]},
            {"chunk_id": "desenvolvedor", "chunk_type": "job_title", "text": "Desenvolvedor", "metadata": {"frequency": 2, "sources": {"a": 2}}, "embedding": [0.2, 0.3, 0.4, 0.5]},
            {"chunk_id": "analista", "chunk_type": "job_title", "text": "Analista", "metadata": {"frequency": 1, "sources": {"a": 1}}, "embedding": [0.8, 0.9, 1.0, 1.1]},
        ]
    )
    if method == 'dbscan':
        config = ClusteringConfig(method=method, chunk_type='job_title', eps=0.5, min_samples=1)
    else:
        monkeypatch.setattr(
            JobTitleClusteringEngine,
            '_run_kmeans',
            lambda self, embeddings, k=None, k_range=None: (np.zeros(len(embeddings), dtype=int), types.SimpleNamespace(inertia_=0.0)),
        )
        config = ClusteringConfig(method=method, chunk_type='job_title', k_range=(2, 2))
    engine = JobTitleClusteringEngine(config)
    payload = engine.run()
    assert payload['metrics']['cluster_count'] >= 1
    assert 'category_breakdown' in payload['metrics']


def test_clustering_engine_category_overrides(monkeypatch):
    from scripts.job_title_clustering_engine import JobTitleClusteringEngine, ClusteringConfig

    store = sys.modules["scripts.pgvector_store"].PgVectorStore()
    store.upsert_chunks(
        [
            {"chunk_id": "frontend_junior", "chunk_type": "job_title", "text": "Desenvolvedor Frontend", "metadata": {"normalized_title": "desenvolvedor frontend", "frequency": 3}, "embedding": [0.1, 0.1, 0.1, 0.1]},
            {"chunk_id": "backend_pleno", "chunk_type": "job_title", "text": "Engenheiro Backend", "metadata": {"normalized_title": "engenheiro backend", "frequency": 2}, "embedding": [0.9, 0.9, 0.9, 0.9]},
        ]
    )
    monkeypatch.setattr(
        JobTitleClusteringEngine,
        '_run_kmeans',
        lambda self, embeddings, k=None, k_range=None: (np.zeros(len(embeddings), dtype=int), types.SimpleNamespace(inertia_=0.0)),
    )
    config = ClusteringConfig(
        method='dbscan',
        eps=0.4,
        min_samples=1,
        category_overrides={
            "frontend": {"keywords": ["frontend"], "method": "kmeans", "k_range": (1, 1)},
        },
    )
    engine = JobTitleClusteringEngine(config)
    payload = engine.run()
    assert any(entry["category"] == "frontend" for entry in payload["summary"])
    assert payload["metrics"]["category_breakdown"]["frontend"]["method"] == "kmeans"


def test_career_progression_detector_builds_edges(tmp_path):
    clusters = {
        "clusters": {
            "1": {
                "titles": [
                    {"text": "Desenvolvedor Júnior"},
                    {"text": "Desenvolvedor Pleno"},
                    {"text": "Desenvolvedor Sênior"},
                ],
                "representative": {"text": "Desenvolvedor Pleno"},
            }
        }
    }
    path = tmp_path / "clusters.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(clusters, handle)
    from scripts.career_progression_detector import CareerProgressionDetector, ProgressionConfig

    config = ProgressionConfig(cluster_results_path=path, min_confidence=0.05)
    detector = CareerProgressionDetector(config)
    payload = detector.run()
    assert payload["progressions"]
    assert payload["statistics"]["total_transitions"] >= 2
    assert "validation" in payload


def test_orchestrator_runs_full_pipeline(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    entries = [
        {"title": "Dev Júnior", "company": "Empresa", "posted_at": "2024-01-01T00:00:00"},
        {"title": "Dev Pleno", "company": "Empresa", "posted_at": "2024-01-01T00:00:00"},
        {"title": "Dev Sênior", "company": "Empresa", "posted_at": "2024-01-01T00:00:00"},
    ]
    with dataset.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")
    workdir = tmp_path / "work"
    from scripts.orchestrate_brazilian_clustering_pipeline import BrazilianClusteringOrchestrator, PipelineConfig

    config = PipelineConfig(data_sources=[dataset], working_dir=workdir, min_frequency=1, parallelism=2)
    orchestrator = BrazilianClusteringOrchestrator(config)
    state = orchestrator.run()
    assert "mapping" in state
    monitor_module = sys.modules["scripts.monitor_progress"]
    assert any(event["stage"] == "pipeline" for event in monitor_module._events)


def test_validate_clustering_quality_generates_report(tmp_path):
    clusters = {
        "method": "dbscan",
        "clusters": {
            "1": {
                "titles": [
                    {"chunk_id": "engenheiro", "text": "Engenheiro", "metadata": {"normalized_title": "engenheiro", "frequency": 2, "sources": {"a": 2}}},
                    {"chunk_id": "dev", "text": "Dev", "metadata": {"normalized_title": "dev", "frequency": 1, "sources": {"a": 1}}}
                ],
                "representative": {"text": "Engenheiro", "metadata": {"normalized_title": "engenheiro"}},
                "frequency": 3,
            },
            "2": {
                "titles": [
                    {"chunk_id": "analista", "text": "Analista", "metadata": {"normalized_title": "analista", "frequency": 2, "sources": {"a": 2}}},
                    {"chunk_id": "cientista", "text": "Cientista", "metadata": {"normalized_title": "cientista", "frequency": 1, "sources": {"a": 1}}}
                ],
                "representative": {"text": "Analista", "metadata": {"normalized_title": "analista"}},
                "frequency": 3,
            }
        },
    }
    cluster_path = tmp_path / "clusters.json"
    with cluster_path.open("w", encoding="utf-8") as handle:
        json.dump(clusters, handle)
    store = sys.modules["scripts.pgvector_store"].PgVectorStore()
    store.upsert_chunks(
        [
            {"chunk_id": "engenheiro", "chunk_type": "job_title", "text": "Engenheiro", "metadata": {"normalized_title": "engenheiro", "frequency": 2, "sources": {"a": 2}}, "embedding": [0.1, 0.2, 0.3, 0.4]},
            {"chunk_id": "dev", "chunk_type": "job_title", "text": "Dev", "metadata": {"normalized_title": "dev", "frequency": 1, "sources": {"a": 1}}, "embedding": [0.2, 0.3, 0.4, 0.5]},
            {"chunk_id": "analista", "chunk_type": "job_title", "text": "Analista", "metadata": {"normalized_title": "analista", "frequency": 2, "sources": {"a": 2}}, "embedding": [0.3, 0.4, 0.5, 0.6]},
            {"chunk_id": "cientista", "chunk_type": "job_title", "text": "Cientista", "metadata": {"normalized_title": "cientista", "frequency": 1, "sources": {"a": 1}}, "embedding": [0.4, 0.5, 0.6, 0.7]},
        ]
    )
    report_path = tmp_path / "report.json"
    from scripts.validate_clustering_quality import ClusteringQualityValidator, ValidationConfig

    config = ValidationConfig(clusters_path=cluster_path, report_path=report_path)
    validator = ClusteringQualityValidator(config)
    report = validator.run()
    assert report_path.exists()
    assert report["cluster_metrics"]
    assert "cluster_statistics" in report


def test_eco_occupation_mapper_creates_review_queue(tmp_path):
    clusters = {
        "clusters": {
            "200": {
                "representative": {"text": "Desenvolvedor Frontend Júnior"},
                "frequency": 2,
                "sources": {"gupy": 2},
                "titles": [
                    {"text": "Frontend Dev Jr", "metadata": {"frequency": 2}},
                    {"text": "Front-end Developer", "metadata": {"frequency": 1}},
                ],
            }
        }
    }
    clusters_path = tmp_path / "clusters.json"
    with clusters_path.open("w", encoding="utf-8") as handle:
        json.dump(clusters, handle)
    from scripts.eco_occupation_mapper import EcoOccupationMapper, OccupationMapperConfig

    config = OccupationMapperConfig(clusters_path=clusters_path, category="ENGINEERING")
    mapper = EcoOccupationMapper(config)
    payload = mapper.run()
    assert payload["review_queue"]
    occupation = payload["occupations"][0]
    assert occupation["skill_requirements"]
    assert occupation["metadata"]["review_required"] is True
