from __future__ import annotations

import json
import logging
from typing import Any, Dict

from fastapi import HTTPException

from app.core.config import settings
from app.services.gemini_client import (
    GeminiClientError,
    GeminiCircuitOpenError,
    get_gemini_client,
)
from app.services.prompt_templates import SYSTEM_PROMPT_RECOMMENDATION


logger = logging.getLogger(__name__)


def generate_outfit_recommendation(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="llm_unavailable")

    prompt = _build_prompt(payload)
    try:
        response_text, _ = get_gemini_client().generate_json(
            prompt,
            temperature=0.5,
            max_output_tokens=768,
        )
        logger.info("Gemini raw response: %s", response_text)
    except (GeminiClientError, GeminiCircuitOpenError) as exc:
        logger.warning("Gemini outfit recommendation failed: %s", exc)
        raise HTTPException(status_code=503, detail="llm_unavailable") from exc

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        logger.warning("Gemini outfit recommendation invalid JSON: %s", exc)
        raise HTTPException(status_code=502, detail="llm_invalid_payload") from exc
    return data


def _build_prompt(payload: Dict[str, Any]) -> str:
    body = json.dumps(payload, ensure_ascii=False)
    return f"{SYSTEM_PROMPT_RECOMMENDATION}\n\nInput:\n{body}"


__all__ = ["generate_outfit_recommendation"]

