import json
import pathlib
import sys
from typing import Any, Dict, List, Optional, Tuple

import pytest


@pytest.fixture(autouse=True)
def _configure_sys_path(monkeypatch):
    """Ensure project root is importable for worker modules."""
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    # Clear environment mutations between tests
    keys = [
        "TOGETHER_API_KEY",
        "TOGETHER_MODEL_STAGE1",
        "TOGETHER_AI_BASE_URL",
        "REGION",
        "EMBEDDING_PROVIDER",
        "RERANK_PROVIDER",
        "GOOGLE_CLOUD_PROJECT",
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)
    yield


class _FakeResponse:
    def __init__(self, status: int, payload: Dict[str, Any]):
        self.status = status
        self._payload = payload

    async def json(self) -> Dict[str, Any]:
        return self._payload

    async def text(self) -> str:
        return json.dumps(self._payload)

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _RecordingSession:
    """
    Lightweight async session stand-in that feeds canned responses.
    Each call consumes the next queued (method, status, payload) tuple.
    """

    last_instance: Optional["_RecordingSession"] = None

    def __init__(self, responses: List[Tuple[str, int, Dict[str, Any]]], **_kwargs):
        self._queue = responses
        self.calls: List[Tuple[str, str]] = []
        _RecordingSession.last_instance = self

    async def __aenter__(self) -> "_RecordingSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    def _next(self, method: str, url: str) -> _FakeResponse:
        if not self._queue:
            raise AssertionError("No queued responses left for session")
        queued_method, status, payload = self._queue.pop(0)
        assert queued_method == method, f"Expected {queued_method} but received {method}"
        self.calls.append((method, url))
        return _FakeResponse(status, payload)

    def get(self, url: str, **_kwargs) -> _FakeResponse:
        return self._next("GET", url)

    def post(self, url: str, **_kwargs) -> _FakeResponse:
        return self._next("POST", url)


@pytest.mark.asyncio
async def test_validator_reports_healthy(monkeypatch):
    from cloud_run_worker.config import Config
    from cloud_run_worker.config_validator import ConfigValidator

    monkeypatch.setenv("REGION", "us-central1")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setenv("RERANK_PROVIDER", "together")
    config = Config(testing=True)

    model_id = config.together_ai_model
    responses = [
        (
            "GET",
            200,
            {
                "data": [
                    {"id": model_id},
                    {"id": "some/other-model"},
                ]
            },
        ),
        (
            "POST",
            200,
            {"choices": [{"message": {"content": "ok"}}]},
        ),
    ]

    validator = ConfigValidator(config, session_factory=lambda **kwargs: _RecordingSession(responses, **kwargs))
    result = await validator.validate_connectivity()

    assert result["status"] == "healthy"
    assert result["checks"]["together_api"]["status"] == "healthy"
    assert result["checks"]["model_availability"]["status"] == "healthy"
    assert result["checks"]["chat_completion"]["status"] == "healthy"
    assert len(_RecordingSession.last_instance.calls) == 2


@pytest.mark.asyncio
async def test_validator_handles_auth_failure(monkeypatch):
    from cloud_run_worker.config import Config
    from cloud_run_worker.config_validator import ConfigValidator

    monkeypatch.setenv("REGION", "us-central1")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setenv("RERANK_PROVIDER", "together")
    config = Config(testing=True)

    responses = [
        (
            "GET",
            401,
            {"error": {"message": "invalid api key"}},
        )
    ]

    validator = ConfigValidator(config, session_factory=lambda **kwargs: _RecordingSession(responses, **kwargs))
    result = await validator.validate_connectivity()

    assert result["status"] == "unhealthy"
    check = result["checks"]["together_api"]
    assert check["status"] == "unavailable"
    assert "401" in check["message"]


@pytest.mark.asyncio
async def test_validator_flags_invalid_config(monkeypatch):
    from cloud_run_worker.config import Config
    from cloud_run_worker.config_validator import ConfigValidator

    monkeypatch.setenv("REGION", "europe-west1")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setenv("RERANK_PROVIDER", "together")
    config = Config(testing=True)

    validator = ConfigValidator(config, session_factory=lambda **kwargs: _RecordingSession([], **kwargs))
    result = await validator.validate_connectivity()

    assert result["status"] == "invalid-config"
    assert result["errors"]
    assert "REGION" in result["errors"][0]
