import json
import tempfile
from pathlib import Path
from unittest import mock

import asyncpg
import pytest
from fastapi.testclient import TestClient

from cloud_run_eco_service import main as eco_service
from scripts.validate_eco_performance_targets import ECOPerformanceValidator, load_dataset
from scripts.orchestrate_eco_search_integration import (
    ECODeploymentOrchestrator,
    OrchestratorConfig,
    parse_args,
)


@pytest.fixture(autouse=True)
def disable_startup_events():
    # Prevent FastAPI startup hooks from attempting real connections during tests
    eco_service.app.router.on_startup.clear()
    eco_service.app.router.on_shutdown.clear()
    eco_service.state.pg_pool = None
    eco_service.state.redis = None
    yield


def test_health_endpoint_returns_status():
    client = TestClient(eco_service.app)
    response = client.get('/health')
    assert response.status_code == 200
    body = response.json()
    assert 'service' in body and body['service'] == eco_service.settings.service_name


def test_metrics_endpoint_exposes_prometheus_text():
    client = TestClient(eco_service.app)
    response = client.get('/metrics')
    assert response.status_code == 200
    assert 'eco_service_requests_total' in response.text


def test_performance_validator_computes_expected_metrics(tmp_path: Path):
    dataset = {
        'queries': [
            {
                'id': 'q1',
                'text': 'engenheiro de software',
                'control_relevance': [3, 2, 0, 0],
                'treatment_relevance': [3, 2, 1, 0],
                'latency_ms_control': [110, 115, 112],
                'latency_ms_treatment': [118, 120, 122],
                'cache_hit_ratio': 0.72,
            },
            {
                'id': 'q2',
                'text': 'data scientist',
                'control_relevance': [2, 1, 0],
                'treatment_relevance': [3, 1, 0],
                'latency_ms_control': [140, 138],
                'latency_ms_treatment': [150, 152],
                'cache_hit_ratio': 0.81,
            },
        ]
    }
    dataset_file = tmp_path / 'dataset.json'
    dataset_file.write_text(json.dumps(dataset), encoding='utf-8')

    records = load_dataset(dataset_file)
    validator = ECOPerformanceValidator(target_ndcg_gain=(0.01, 0.15), max_latency_delta_ms=30)
    report = validator.generate_performance_report(records)

    assert report.dataset_size == 2
    assert report.ndcg_delta.count == 2
    assert report.latency_delta_ms.mean > 0
    assert report.cache_hit_ratio is not None
    assert 0 <= report.cache_hit_ratio.mean <= 1


def test_parse_args_creates_config(tmp_path: Path):
    args = [
        '--project-id', 'demo',
        '--region', 'europe-west1',
        '--service-name', 'eco-service',
        '--deployment-mode', 'rolling',
        '--db-instance', 'projects/demo/instances/eco-db',
        '--database-secret', 'eco-secret',
        '--dataset', str(tmp_path / 'data.json'),
        '--report', str(tmp_path / 'report.json'),
        '--health-timeout', '120',
    ]
    config = parse_args(args)
    assert config.project_id == 'demo'
    assert config.deployment_mode == 'rolling'
    assert config.dataset_path == tmp_path / 'data.json'
    assert config.report_path == tmp_path / 'report.json'
    assert config.health_timeout == 120


def test_orchestrator_generates_report(tmp_path: Path):
    config = OrchestratorConfig(
        project_id='demo',
        region='us-central1',
        service_name='eco',
        deployment_mode='blue-green',
        database_instance='projects/demo/instances/eco-db',
        database_secret='eco-secret',
        report_path=tmp_path / 'report.json',
    )
    orchestrator = ECODeploymentOrchestrator(config)

    with mock.patch.object(orchestrator, 'validate_database'), \
         mock.patch.object(orchestrator, 'deploy_cloud_run'), \
         mock.patch.object(orchestrator, 'enable_feature_flags'), \
         mock.patch.object(orchestrator, 'initialize_ab_testing'), \
         mock.patch.object(orchestrator, 'monitor_deployment'), \
         mock.patch.object(orchestrator, 'validate_performance_targets'):
        orchestrator.run()

    assert config.report_path.exists()
    payload = json.loads(config.report_path.read_text())
    assert payload['project_id'] == 'demo'
    assert len(payload['steps']) == 5  # validate, deploy, enable, initialize, monitor


class _DummyAcquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _DummyConnection:
    def __init__(self, value=None, raise_error=False):
        self._value = value
        self._raise_error = raise_error

    async def fetchval(self, query: str):
        if self._raise_error:
            raise asyncpg.PostgresError()  # type: ignore[call-arg]
        return self._value


class _DummyPool:
    def __init__(self, conn: _DummyConnection):
        self._conn = conn

    def acquire(self):
        return _DummyAcquire(self._conn)

    async def close(self):
        return None


class _DummyRedis:
    async def close(self):
        return None


@pytest.mark.asyncio
async def test_init_resources_detects_trgm_support(monkeypatch):
    async def fake_create_pool(*_args, **_kwargs):
        return _DummyPool(_DummyConnection(True))

    monkeypatch.setattr(eco_service.asyncpg, 'create_pool', fake_create_pool)
    monkeypatch.setattr(eco_service.redis, 'from_url', lambda *_args, **_kwargs: _DummyRedis())

    settings = eco_service.Settings(
        pg_dsn='postgres://example',
        redis_url='redis://localhost:6379',
    )
    state = eco_service.AppState(settings)
    await state.init_resources()
    assert state.supports_trgm is True
    await state.close()


@pytest.mark.asyncio
async def test_init_resources_handles_missing_trgm(monkeypatch):
    async def fake_create_pool(*_args, **_kwargs):
        return _DummyPool(_DummyConnection(value=False, raise_error=False))

    monkeypatch.setattr(eco_service.asyncpg, 'create_pool', fake_create_pool)
    monkeypatch.setattr(eco_service.redis, 'from_url', lambda *_args, **_kwargs: _DummyRedis())

    settings = eco_service.Settings(
        pg_dsn='postgres://example',
        redis_url='redis://localhost:6379',
    )
    state = eco_service.AppState(settings)
    await state.init_resources()
    assert state.supports_trgm is False
    await state.close()
