"""
Configuration validation helpers for Cloud Run worker deployments.

Provides lightweight connectivity checks against Together AI endpoints to
confirm model availability and authentication before launching workloads.
"""

from __future__ import annotations

import asyncio
import logging
from time import perf_counter
from typing import Any, Callable, Dict, Iterable, List, Optional

import aiohttp

from .config import Config

SessionFactory = Callable[..., "aiohttp.ClientSession"]


class ConfigValidator:
    """Validate configuration semantics and Together AI connectivity."""

    def __init__(
        self,
        config: Config,
        *,
        session_factory: Optional[SessionFactory] = None,
        logger: Optional[logging.Logger] = None
    ) -> None:
        self._config = config
        self._session_factory = session_factory or aiohttp.ClientSession
        self._logger = logger or logging.getLogger(__name__)

        base_url = (self._config.together_ai_base_url.rstrip("/") or "https://api.together.xyz/v1")
        self._models_url = f"{base_url}/models"
        self._chat_url = f"{base_url}/chat/completions"

    async def validate_connectivity(self) -> Dict[str, Any]:
        """Validate configuration and perform Together AI connectivity probes."""
        try:
            self._config.validate()
        except ValueError as exc:
            message = str(exc)
            self._logger.error("Configuration validation failed: %s", message)
            return {
                "status": "invalid-config",
                "errors": [message],
                "checks": {}
            }

        headers = {
            "Authorization": f"Bearer {self._config.together_ai_api_key}",
            "Content-Type": "application/json"
        }

        checks: Dict[str, Dict[str, Any]] = {}
        errors: List[str] = []

        try:
            async with self._session_factory(headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as session:
                models_check = await self._check_models(session)
                models = models_check.pop("models", [])
                checks["together_api"] = models_check

                if models_check["status"] == "healthy":
                    checks["model_availability"] = self._evaluate_model_availability(models)
                    checks["chat_completion"] = await self._check_chat_completion(session)
                else:
                    checks["model_availability"] = {
                        "status": "unknown",
                        "message": "Model availability skipped due to API failure."
                    }
                    checks["chat_completion"] = {
                        "status": "unavailable",
                        "message": "Skipped because Together API is unavailable."
                    }
        except Exception as exc:  # noqa: BLE001 - propagate diagnostics
            message = str(exc)
            self._logger.exception("Connectivity validation failed: %s", message)
            errors.append(message)
            checks.setdefault(
                "together_api",
                {
                    "status": "unavailable",
                    "message": message
                }
            )
            checks.setdefault(
                "model_availability",
                {
                    "status": "unknown",
                    "message": "Model availability could not be determined."
                }
            )
            checks.setdefault(
                "chat_completion",
                {
                    "status": "unavailable",
                    "message": "Chat completion probe skipped."
                }
            )

        overall_status = self._derive_status(checks.values(), errors)
        return {
            "status": overall_status,
            "errors": errors,
            "checks": checks
        }

    async def _check_models(self, session: "aiohttp.ClientSession") -> Dict[str, Any]:
        started = perf_counter()
        try:
            async with session.get(self._models_url) as response:
                latency = (perf_counter() - started) * 1000.0
                payload = await self._safe_json(response)
                if 200 <= response.status < 300:
                    data = payload.get("data", [])
                    return {
                        "status": "healthy",
                        "latencyMs": round(latency, 2),
                        "models": data
                    }

                message = self._format_error("List models failed", response.status, payload)
                self._logger.warning("%s", message)
                return {
                    "status": "unavailable",
                    "latencyMs": round(latency, 2),
                    "message": message,
                    "models": []
                }
        except Exception as exc:  # noqa: BLE001
            message = f"List models request failed: {exc}"
            self._logger.exception("%s", message)
            return {
                "status": "unavailable",
                "message": message,
                "models": []
            }

    async def _check_chat_completion(self, session: "aiohttp.ClientSession") -> Dict[str, Any]:
        payload = {
            "model": self._config.together_ai_model,
            "messages": [
                {"role": "system", "content": "diagnostic check"},
                {"role": "user", "content": "respond with ok"}
            ],
            "max_tokens": 4,
            "temperature": 0.0
        }
        started = perf_counter()

        try:
            async with session.post(self._chat_url, json=payload) as response:
                latency = (perf_counter() - started) * 1000.0
                data = await self._safe_json(response)
                if 200 <= response.status < 300 and data.get("choices"):
                    return {
                        "status": "healthy",
                        "latencyMs": round(latency, 2)
                    }

                message = self._format_error("Chat completion failed", response.status, data)
                self._logger.warning("%s", message)
                return {
                    "status": "degraded",
                    "latencyMs": round(latency, 2),
                    "message": message
                }
        except Exception as exc:  # noqa: BLE001
            message = f"Chat completion probe failed: {exc}"
            self._logger.exception("%s", message)
            return {
                "status": "unavailable",
                "message": message
            }

    def _evaluate_model_availability(self, models: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        target = self._config.together_ai_model
        available = any(entry.get("id") == target for entry in models)
        if available:
            return {
                "status": "healthy",
                "model": target
            }

        message = f"Model '{target}' not returned by Together API."
        self._logger.warning("%s", message)
        return {
            "status": "unavailable",
            "model": target,
            "message": message
        }

    @staticmethod
    def _derive_status(checks: Iterable[Dict[str, Any]], errors: List[str]) -> str:
        if errors:
            return "unhealthy"

        for check in checks:
            if check.get("status") not in {"healthy", "disabled"}:
                return "unhealthy"
        return "healthy"

    @staticmethod
    async def _safe_json(response: "aiohttp.ClientResponse") -> Dict[str, Any]:
        try:
            data = await response.json()
            if isinstance(data, dict):
                return data
            return {}
        except Exception:  # noqa: BLE001
            text = await response.text()
            return {"raw": text}

    @staticmethod
    def _format_error(prefix: str, status: int, payload: Dict[str, Any]) -> str:
        detail = payload.get("error") or payload.get("message") or payload.get("raw")
        return f"{prefix} (status={status}): {detail}"

    def validate_connectivity_sync(self) -> Dict[str, Any]:
        """Synchronous wrapper for environments that prefer blocking calls."""
        return asyncio.run(self.validate_connectivity())
