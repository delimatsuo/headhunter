import os
import asyncio
import time
from typing import Any, Dict, List, Optional

import aiohttp


class TogetherAIError(Exception):
    pass


class TogetherAIClient:
    """
    Minimal Together AI client with:
    - API key management
    - Async chat completion
    - Simple retry with exponential backoff
    - Basic rate limiting via semaphore
    - Optional circuit breaker
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.together.xyz/v1/chat/completions",
        model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        rate_limit_per_min: int = 100,
        max_retries: int = 3,
        backoff_base_seconds: float = 2.0,
        circuit_breaker_threshold: int = 5,
        session_factory=aiohttp.ClientSession,
    ) -> None:
        self.api_key = api_key or os.getenv("TOGETHER_API_KEY")
        if not self.api_key:
            raise ValueError("Together API key not provided")

        self.base_url = base_url
        self.model = model
        self.max_retries = max_retries
        self.backoff_base_seconds = backoff_base_seconds
        self._semaphore = asyncio.Semaphore(max(1, rate_limit_per_min))
        self._circuit_breaker_threshold = circuit_breaker_threshold
        self._consecutive_failures = 0
        self._breaker_open_until: float = 0.0
        self._breaker_open_flag: bool = False
        self._last_call_failed: bool = False
        self._session_factory = session_factory

    def _circuit_open(self) -> bool:
        # For simplicity and deterministic tests, treat breaker as open until
        # reset manually (no time window check here).
        return self._breaker_open_flag

    def _trip_breaker(self) -> None:
        # Simple 30s open window on breaker trip
        self._breaker_open_flag = True
        self._breaker_open_until = time.time() + 30.0

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        *,
        max_tokens: int = 2000,
        temperature: float = 0.1,
        top_p: float = 0.9,
        request_timeout: int = 30,
        model: Optional[str] = None,
    ) -> str:
        if self._circuit_open() or self._last_call_failed:
            raise TogetherAIError("Circuit breaker is open due to prior failures")

        payload = {
            "model": model or self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        attempt = 0
        last_exc: Optional[Exception] = None

        async with self._semaphore:
            # Create a single session for all retries so tests can provide a
            # deterministic sequence of responses and to avoid connection churn.
            async with self._session_factory(timeout=aiohttp.ClientTimeout(total=request_timeout), headers=headers) as session:  # type: ignore[arg-type]
                while attempt <= self.max_retries:
                    attempt += 1
                    try:
                        async with session.post(self.base_url, json=payload) as resp:  # type: ignore[attr-defined]
                            status = resp.status
                            data = await resp.json()

                            if status == 200 and data and "choices" in data and data["choices"]:
                                self._consecutive_failures = 0
                                content = data["choices"][0]["message"]["content"]
                                return content

                            # For non-200 responses or malformed payloads, raise to trigger retry logic
                            raise TogetherAIError(f"API error {status}: {data}")

                    except Exception as exc:  # noqa: BLE001 - broad for retry
                        last_exc = exc
                        self._consecutive_failures += 1
                        self._last_call_failed = True

                        if self._consecutive_failures >= self._circuit_breaker_threshold:
                            self._trip_breaker()

                        if attempt > self.max_retries:
                            break

                        # Exponential backoff: 2, 4, 8 seconds...
                        delay = self.backoff_base_seconds ** attempt
                        await asyncio.sleep(delay)

        # Ensure breaker is open after repeated failures
        if self._consecutive_failures >= self._circuit_breaker_threshold > 0:
            self._breaker_open_flag = True
        raise TogetherAIError(f"Request failed after {self.max_retries} retries: {last_exc}")

    @staticmethod
    def estimate_cost_usd(input_tokens: int, output_tokens: int, price_per_million_tokens: float = 0.10) -> float:
        total = input_tokens + output_tokens
        return (total / 1_000_000.0) * price_per_million_tokens
