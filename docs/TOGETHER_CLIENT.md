Together AI Client – Usage and Monitoring

Overview
- Stage‑1 enrichment uses Together Chat Completions with a single pass to extract a strict JSON profile.
- Default model (env): `TOGETHER_MODEL_STAGE1=Qwen/Qwen2.5-32B-Instruct`
- Env keys are read from the repo root `.env` (local) or Secret Manager (prod).

Environment
```
TOGETHER_API_KEY=your_key
TOGETHER_MODEL_STAGE1=Qwen/Qwen2.5-32B-Instruct
MAX_ESTIMATED_COST_USD=5.00
```

Client (Python)
```
from scripts.together_client import TogetherAIClient

client = TogetherAIClient()
messages = [
  {"role": "system", "content": "Return ONLY strict JSON with this schema: {...}"},
  {"role": "user", "content": "...resume text..."},
]
content = await client.chat_completion(messages, temperature=0.1, max_tokens=1500)
```

Monitoring & Guardrails
- Retries with exponential backoff; sliding‑window rate limiter; circuit breaker with auto‑close.
- Cost guardrail via `MAX_ESTIMATED_COST_USD` and optional estimated token arguments.
- Metrics snapshot (`get_metrics()`):
  - `calls_total`, `errors_total`, `breaker_trips`, `latency_ms_ema`, `rate_limit_per_min`, `model`.

Integration Test
- A live integration test is provided and skipped when `TOGETHER_API_KEY` is missing:
  - `tests/test_together_integration.py`

Prompting Tips
- Low temperature (0.1–0.2), tight schema instruction, no code fences.
- Include a minimal valid example; require all keys to be present.
- Post‑validate/repair downstream for extra robustness.

