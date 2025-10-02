import os
import json
import sys
import importlib
import asyncio

# Ensure repository root is on sys.path for 'scripts.*' imports
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.eco_title_normalizer import normalize_title_ptbr


def test_normalizer_basic_cases():
    cases = {
        "Dev Sr. (a)": "dev senior",
        "Eng. de Dados - Pl": "engenheiro de dados pleno",
        "Analista Júnior (o/a) - BI": "analista junior bi",
        "Desenvolvedor(a) Front-end": "desenvolvedor front end",
        "": "",
    }
    for src, expected_contains in cases.items():
        out = normalize_title_ptbr(src)
        assert isinstance(out, str)
        for token in expected_contains.split():
            assert token in out


def test_schema_validator_env_precedence(monkeypatch):
    mod = importlib.import_module('scripts.validate_and_deploy_eco_schema')
    # PG_UNIX_SOCKET should take precedence
    monkeypatch.setenv('PG_UNIX_SOCKET', '/cloudsql/proj:region:inst')
    monkeypatch.setenv('PGVECTOR_HOST', 'pgvector-host')
    monkeypatch.setenv('PGHOST', 'pg-host')
    cfg = mod._load_db_env_from_pgvector()  # type: ignore
    assert cfg['PGHOST'] == '/cloudsql/proj:region:inst'
    assert cfg['USE_UNIX_SOCKET'] == '1'
    assert cfg['RESOLVED_SOURCE'] == 'unix_socket'


def test_schema_validator_runs_json(monkeypatch):
    # Avoid real DB connections
    mod = importlib.import_module('scripts.validate_and_deploy_eco_schema')
    monkeypatch.setattr(mod, '_connect', lambda: None)  # type: ignore
    rep = mod.run_validation(deploy_if_missing=False)
    d = rep.to_dict()
    assert 'ok' in d and isinstance(d['sections'], list)


def test_dataset_discovery_local_validation(tmp_path, monkeypatch):
    from scripts import discover_brazilian_job_dataset as discovery

    data_dir = tmp_path / 'eco_raw' / '20240101' / 'awesome_spider'
    data_dir.mkdir(parents=True)
    sample = {
        'job_title': 'Engenheiro de Dados',
        'normalized_title': 'engenheiro de dados',
        'source_url': 'https://example.com/job/123',
    }
    with open(data_dir / 'batch.jsonl', 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(sample) + '\n')

    monkeypatch.chdir(tmp_path)
    report_path = tmp_path / 'report.json'
    monkeypatch.setenv('ECO_DATASET_DISCOVERY_REPORT', str(report_path))
    discovery.REPORT_PATH = str(report_path)
    monkeypatch.setattr(discovery, '_client', lambda: (None, Exception('no gcs')))
    import types
    fake_google = types.ModuleType('google')
    fake_cloud = types.ModuleType('google.cloud')
    fake_google.cloud = fake_cloud
    monkeypatch.setitem(sys.modules, 'google', fake_google)
    monkeypatch.setitem(sys.modules, 'google.cloud', fake_cloud)

    rc = discovery.main()
    assert rc != 0  # missing SDKs still raise warnings

    with open(report_path, encoding='utf-8') as fh:
        report = json.load(fh)
    local = report['local_files']
    assert local['errors'] == []
    assert local['checked_lines'] > 0


def test_validate_eco_apis_warns_without_ts_runtime(monkeypatch):
    from scripts import validate_eco_apis as api_validator

    monkeypatch.setattr(api_validator.shutil, 'which', lambda name: None)

    result = api_validator.try_node_harness()
    assert result['ran'] is False
    assert result['status'] == 'warn'
    assert result['ok'] is True


def test_pgvector_similarity_query_uses_array_cast(monkeypatch):
    import scripts.validate_pgvector_eco_compatibility as pgvector

    executed = []

    class DummyConn:
        async def fetchval(self, query, *args):
            executed.append(('fetchval', query))
            if "pg_extension" in query:
                return True
            if "information_schema.tables" in query:
                return 4
            if "proname='similarity_search'" in query:
                return True
            if "proname='array_to_vector'" in query:
                return True
            return True

        async def fetch(self, query, *args):
            executed.append(('fetch', query))
            return []

        async def execute(self, query, *args):
            executed.append(('execute', query))
            return None

    class DummyContext:
        async def __aenter__(self):
            return DummyConn()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummyStore:
        def get_connection(self):
            return DummyContext()

    async def fake_validate_embeddings():
        return {'name': 'embedding_provider', 'ok': True, 'dim': 768}

    import types

    fake_store_module = types.ModuleType('scripts.pgvector_store')

    async def fake_create_pgvector_store(pool_size=10):  # pragma: no cover - simple stub
        return DummyStore()

    fake_store_module.create_pgvector_store = fake_create_pgvector_store
    monkeypatch.setitem(sys.modules, 'scripts.pgvector_store', fake_store_module)
    monkeypatch.setitem(sys.modules, 'pgvector_store', fake_store_module)

    fake_validator_module = types.ModuleType('scripts.validate_pgvector_deployment')
    fake_validator_module.validate_embeddings = fake_validate_embeddings
    monkeypatch.setitem(sys.modules, 'scripts.validate_pgvector_deployment', fake_validator_module)

    monkeypatch.setattr(pgvector, 'validate_embeddings', fake_validate_embeddings, raising=False)

    report = asyncio.run(pgvector.main_async())
    assert report['ok'] is True
    fetch_queries = [q for kind, q in executed if kind == 'fetch']
    assert any('array_to_vector($1::float8[])' in q for q in fetch_queries)
