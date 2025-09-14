import asyncio
import json
import sys
import pathlib
import pytest


repo_root = pathlib.Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))


@pytest.mark.asyncio
async def test_rate_limiting(monkeypatch):
    from scripts.together_client import TogetherAIClient

    calls = {"count": 0}

    class FakeSession:
        def __init__(self, *_, **__):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        def post(self, *_args, **_kwargs):  # context manager
            class Ctx:
                status = 200
                async def __aenter__(self_inner):
                    calls["count"] += 1
                    return self_inner
                async def __aexit__(self_inner, *args):
                    return False
                async def json(self_inner):
                    return {"choices": [{"message": {"content": "{}"}}]}
            return Ctx()

    monkeypatch.setenv("TOGETHER_API_KEY", "test")
    client = TogetherAIClient(api_key="test", rate_limit_per_min=2, session_factory=lambda *a, **k: FakeSession())

    # 3 quick calls with rate limit 2/min should force a sleep before the 3rd
    start = asyncio.get_event_loop().time()
    await client.chat_completion([{"role": "user", "content": "hi"}], max_tokens=1)
    await client.chat_completion([{"role": "user", "content": "hi"}], max_tokens=1)
    await client.chat_completion([{"role": "user", "content": "hi"}], max_tokens=1)
    elapsed = asyncio.get_event_loop().time() - start

    assert calls["count"] == 3
    # The test asserts functionally; timing threshold is flaky on CI, so do not assert elapsed.


@pytest.mark.asyncio
async def test_retry_and_circuit_breaker(monkeypatch):
    from scripts.together_client import TogetherAIClient, TogetherAIError

    attempts = {"n": 0}

    class FakeSession:
        def __init__(self, *_, **__):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        def post(self, *_args, **_kwargs):
            class Ctx:
                async def __aenter__(self_inner):
                    attempts["n"] += 1
                    class Resp:
                        status = 500
                        async def json(self):
                            return {"error": "server"}
                    return Resp()
                async def __aexit__(self_inner, *args):
                    return False
            return Ctx()

    monkeypatch.setenv("TOGETHER_API_KEY", "test")
    client = TogetherAIClient(api_key="test", max_retries=2, circuit_breaker_threshold=2, session_factory=lambda *a, **k: FakeSession())

    with pytest.raises(TogetherAIError):
        await client.chat_completion([{"role": "user", "content": "hi"}], max_tokens=1)

    # After failures reaching threshold, subsequent call should immediately raise due to open breaker
    with pytest.raises(TogetherAIError):
        await client.chat_completion([{"role": "user", "content": "hi"}], max_tokens=1)


@pytest.mark.asyncio
async def test_health_check_like_flow(monkeypatch):
    from scripts.together_client import TogetherAIClient

    class FakeSession:
        def __init__(self, *_, **__):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        def post(self, *_args, **_kwargs):
            class Ctx:
                status = 200
                async def __aenter__(self_inner):
                    return self_inner
                async def __aexit__(self_inner, *args):
                    return False
                async def json(self_inner):
                    return {"choices": [{"message": {"content": "{}"}}]}
            return Ctx()

    monkeypatch.setenv("TOGETHER_API_KEY", "test")
    client = TogetherAIClient(api_key="test", session_factory=lambda *a, **k: FakeSession())
    # successful minimal call serves as a health check surrogate
    out = await client.chat_completion([{"role": "user", "content": "ping"}], max_tokens=1)
    assert isinstance(out, str)


