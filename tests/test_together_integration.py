import os
import json
import pytest

from scripts.together_client import TogetherAIClient


pytestmark = pytest.mark.asyncio


async def test_together_client_strict_json_integration():
    """
    Live integration test (skips without TOGETHER_API_KEY).
    Sends a tiny strict-JSON request and validates the response shape.
    """
    if not os.getenv("TOGETHER_API_KEY"):
        pytest.skip("TOGETHER_API_KEY not set; skipping live integration test")

    client = TogetherAIClient()

    messages = [
        {
            "role": "system",
            "content": (
                "You return ONLY strict JSON (no code fences). Use exactly this schema: "
                '{"ok": true, "model": "<string>"}. Do not include any extra keys.'
            ),
        },
        {
            "role": "user",
            "content": "Acknowledge readiness and include your model field.",
        },
    ]

    content = await client.chat_completion(
        messages,
        max_tokens=128,
        temperature=0.1,
        top_p=0.2,
        estimated_input_tokens=300,
        estimated_output_tokens=100,
    )

    data = json.loads(content)
    assert isinstance(data, dict)
    assert data.get("ok") is True
    assert isinstance(data.get("model"), str)

    metrics = client.get_metrics()
    assert metrics["calls_total"] >= 1
