from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List

from app.core.config import settings
from app.services.gemini_client import (
    GeminiClientError,
    GeminiCircuitOpenError,
    get_gemini_client,
)


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RecommendationPromptContext:
    city: str | None
    country_code: str | None
    travel_window: str | None
    weather_summary: str | None
    temperature_c: float | None
    currency_code: str
    exchange_rate: float | None


def generate_recommendation_sections(context: RecommendationPromptContext) -> Dict[str, Any]:
    """Generate popular items, outfit tips, and shopping guide snippets."""
    if not settings.gemini_api_key:
        return _fallback_sections(context)

    prompt = _build_prompt(context)
    try:
        payload, _ = get_gemini_client().generate_json(
            prompt,
            temperature=0.6,
            max_output_tokens=512,
        )
        data = json.loads(payload)
    except (GeminiClientError, GeminiCircuitOpenError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("Gemini recommendation generation failed: %s", exc)
        return _fallback_sections(context)

    popular_items = _normalize_strings(data.get("popular_items"))
    outfit_tip = _as_str(data.get("outfit_tip"))
    shopping_guide = _as_str(data.get("shopping_guide"))

    if not popular_items or not outfit_tip or not shopping_guide:
        return _fallback_sections(context)
    return {
        "popular_items": popular_items,
        "outfit_tip": outfit_tip,
        "shopping_guide": shopping_guide,
    }


def _build_prompt(context: RecommendationPromptContext) -> str:
    destination = context.city or (context.country_code or "the destination")
    weather_phrase = (
        f"{context.weather_summary} with around {context.temperature_c:.0f}°C"
        if context.weather_summary and context.temperature_c is not None
        else context.weather_summary
    )
    fx_line = (
        f"Exchange rate vs KRW for {context.currency_code}: {context.exchange_rate}"
        if context.exchange_rate
        else f"Currency code: {context.currency_code}"
    )
    return (
        "You are a concise Korean travel concierge. "
        "Provide practical guidance tailored to the traveller.\n"
        f"Destination: {destination}\n"
        f"Country code: {context.country_code}\n"
        f"Travel window: {context.travel_window}\n"
        f"Weather: {weather_phrase or 'N/A'}\n"
        f"{fx_line}\n"
        "Return strict JSON with keys popular_items (array of 2 strings), "
        "outfit_tip (string <=220 chars), shopping_guide (string <=220 chars). "
        "Use natural Korean sentences and do not include markdown."
    )


def _fallback_sections(context: RecommendationPromptContext) -> Dict[str, Any]:
    destination = context.city or (context.country_code or "여행지")
    temperature = (
        f"{context.temperature_c:.0f}℃" if context.temperature_c is not None else ""
    )
    weather = context.weather_summary or ""
    travel_window = context.travel_window or "여행 기간"
    popular_items = [
        f"{destination} 한정 기념품",
        f"{destination} 현지 간식 또는 음료",
    ]
    outfit_tip = (
        f"{travel_window} 동안 {weather}{' / ' if weather and temperature else ''}{temperature} "
        "예보가 예상되니 레이어드 가능한 기본 의류와 편한 신발을 준비하세요."
    ).strip()
    shopping_guide = (
        f"{destination}에서 인기 있는 쇼핑존을 미리 확인하고, "
        f"{context.currency_code} 환율을 비교해 면세와 시내 매장을 번갈아 둘러보세요."
    )
    return {
        "popular_items": popular_items,
        "outfit_tip": outfit_tip,
        "shopping_guide": shopping_guide,
    }


def _normalize_strings(value: Any) -> List[str]:
    if isinstance(value, list):
        result = []
        for entry in value:
            text = _as_str(entry)
            if text:
                result.append(text)
        return result[:2]
    text = _as_str(value)
    return [text] if text else []


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    return str(value).strip() or None

