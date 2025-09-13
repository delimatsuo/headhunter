import os
import sys
import pathlib
import pytest


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    # Ensure project root on sys.path for package imports
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    # Clear relevant env vars before each test
    keys = [
        "TOGETHER_API_KEY",
        "TOGETHER_MODEL_STAGE1",
        "REGION",
        "EMBEDDING_PROVIDER",
        "RERANK_PROVIDER",
        "GOOGLE_CLOUD_PROJECT",
    ]
    for k in keys:
        monkeypatch.delenv(k, raising=False)
    yield


def test_valid_defaults_with_testing(monkeypatch):
    from cloud_run_worker.config import Config

    monkeypatch.setenv("REGION", "us-central1")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setenv("RERANK_PROVIDER", "together")

    cfg = Config(testing=True)
    # Should not raise on validate
    cfg.validate()

    assert cfg.together_ai_model
    assert cfg.region == "us-central1"
    assert cfg.embedding_provider == "gemini"
    assert cfg.rerank_provider == "together"


def test_region_must_be_us_central1(monkeypatch):
    from cloud_run_worker.config import Config

    monkeypatch.setenv("REGION", "us-east1")
    cfg = Config(testing=True)
    with pytest.raises(ValueError):
        cfg.validate()


@pytest.mark.parametrize("provider", ["gemini", "vertex", "local"])
def test_embedding_provider_allowed(monkeypatch, provider):
    from cloud_run_worker.config import Config

    monkeypatch.setenv("REGION", "us-central1")
    monkeypatch.setenv("EMBEDDING_PROVIDER", provider)
    cfg = Config(testing=True)
    cfg.validate()  # should not raise
    assert cfg.embedding_provider == provider


def test_embedding_provider_invalid(monkeypatch):
    from cloud_run_worker.config import Config

    monkeypatch.setenv("REGION", "us-central1")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "bogus")
    cfg = Config(testing=True)
    with pytest.raises(ValueError):
        cfg.validate()


def test_rerank_provider_must_be_together(monkeypatch):
    from cloud_run_worker.config import Config

    monkeypatch.setenv("REGION", "us-central1")
    monkeypatch.setenv("RERANK_PROVIDER", "together")
    cfg = Config(testing=True)
    cfg.validate()  # ok

    monkeypatch.setenv("RERANK_PROVIDER", "other")
    cfg = Config(testing=True)
    with pytest.raises(ValueError):
        cfg.validate()


def test_api_key_required_when_not_testing(monkeypatch):
    from cloud_run_worker.config import Config

    # No TOGETHER_API_KEY set and not testing -> should error in constructor
    with pytest.raises(ValueError):
        Config(testing=False)


def test_stage1_model_from_env(monkeypatch):
    from cloud_run_worker.config import Config

    monkeypatch.setenv("REGION", "us-central1")
    monkeypatch.setenv("TOGETHER_MODEL_STAGE1", "Qwen/Qwen2.5-32B-Instruct")
    cfg = Config(testing=True)
    assert cfg.together_ai_model == "Qwen/Qwen2.5-32B-Instruct"


