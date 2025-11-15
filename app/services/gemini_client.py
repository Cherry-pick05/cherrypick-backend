"""Thin wrapper around the Gemini API with basic circuit breaking."""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Tuple

import google.generativeai as genai
from google.generativeai import types as genai_types

from app.core.config import settings


class GeminiClientError(RuntimeError):
    """Base exception for Gemini client failures."""


class GeminiCircuitOpenError(GeminiClientError):
    """Raised when the circuit breaker is open."""


class GeminiClient:
    def __init__(self, api_key: str, model_name: str, timeout: float) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required")

        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model_name)
        self._model_name = model_name
        self._timeout = timeout
        self._lock = threading.Lock()
        self._failure_count = 0
        self._circuit_open_until = 0.0

    def generate_json(
        self,
        prompt: str,
        *,
        temperature: float,
        max_output_tokens: int,
    ) -> Tuple[str, Dict[str, Any]]:
        if not prompt:
            raise ValueError("Prompt must not be empty")

        now = time.monotonic()
        with self._lock:
            if now < self._circuit_open_until:
                raise GeminiCircuitOpenError("Gemini circuit is open due to recent failures")

        try:
            response = self._model.generate_content(
                prompt,
                generation_config=genai_types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    response_mime_type="application/json",
                ),
                request_options={"timeout": self._timeout},
            )
        except Exception as exc:  # pragma: no cover - network failures
            self._record_failure(exc)
            raise GeminiClientError(str(exc)) from exc

        self._record_success()
        usage = getattr(response, "usage_metadata", None)
        payload = response.text or ""
        model_info = {
            "name": self._model_name,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
        }
        if usage:
            model_info["usage"] = {
                "prompt_tokens": getattr(usage, "prompt_token_count", None),
                "candidates_tokens": getattr(usage, "candidates_token_count", None),
                "total_tokens": getattr(usage, "total_token_count", None),
            }
        return payload, model_info

    def _record_failure(self, exc: Exception) -> None:
        with self._lock:
            self._failure_count += 1
            if self._failure_count >= 3:
                self._circuit_open_until = time.monotonic() + 30

    def _record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._circuit_open_until = 0.0


_CLIENT: GeminiClient | None = None


def get_gemini_client() -> GeminiClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = GeminiClient(
            api_key=settings.gemini_api_key or "",
            model_name=settings.gemini_model,
            timeout=settings.llm_classifier_timeout_sec,
        )
    return _CLIENT

