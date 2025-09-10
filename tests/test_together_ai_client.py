import asyncio
import json
import types

import pytest

from scripts.together_client import TogetherAIClient, TogetherAIError


class _FakeResponse:
    def __init__(self, status: int, data: dict):
        self.status = status
        self._data = data

    async def json(self):
        return self._data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    def __init__(self, *, headers=None, timeout=None, plan=None):
        # plan is a list of (status, data) to return on successive calls
        self._plan = list(plan or [])

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json=None):  # noqa: A003 - shadow ok in fake
        if self._plan:
            status, data = self._plan.pop(0)
        else:
            status, data = 200, {"choices": [{"message": {"content": "OK"}}]}
        return _FakeResponse(status, data)


def test_init_without_api_key(monkeypatch):
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    with pytest.raises(ValueError):
        TogetherAIClient(api_key=None)


def test_successful_chat_completion(monkeypatch):
    # Provide a dummy key
    monkeypatch.setenv("TOGETHER_API_KEY", "test_key")

    # Fake session returns a valid 200 response
    def session_factory(**kwargs):
        return _FakeSession(plan=[(200, {"choices": [{"message": {"content": "Hello world"}}]})])

    client = TogetherAIClient(session_factory=session_factory)

    async def run():
        out = await client.chat_completion([{"role": "user", "content": "Say hi"}])
        return out

    result = asyncio.run(run())
    assert result == "Hello world"


def test_retry_then_success(monkeypatch):
    monkeypatch.setenv("TOGETHER_API_KEY", "test_key")

    # First call 500, second call 200
    def session_factory(**kwargs):
        return _FakeSession(
            plan=[
                (500, {"error": "server"}),
                (200, {"choices": [{"message": {"content": "Recovered"}}]}),
            ]
        )

    client = TogetherAIClient(session_factory=session_factory, max_retries=2, backoff_base_seconds=0.0)

    async def run():
        out = await client.chat_completion([{"role": "user", "content": "Ping"}])
        return out

    result = asyncio.run(run())
    assert result == "Recovered"


def test_failure_raises_error(monkeypatch):
    monkeypatch.setenv("TOGETHER_API_KEY", "test_key")

    # Always fail
    def session_factory(**kwargs):
        return _FakeSession(plan=[(500, {"error": "server"})])

    client = TogetherAIClient(session_factory=session_factory, max_retries=0, backoff_base_seconds=0.0)

    async def run_fail():
        with pytest.raises(TogetherAIError):
            await client.chat_completion([{"role": "user", "content": "Ping"}])

    asyncio.run(run_fail())
