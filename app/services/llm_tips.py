"""LLM-backed contextual travel tips generation."""

from __future__ import annotations

import json
import logging
from typing import Iterable, Sequence

from pydantic import BaseModel, Field, ValidationError

try:  # pragma: no cover - optional during unit tests without env deps
    from app.core.config import settings
except Exception:  # pylint: disable=broad-except
    settings = None  # type: ignore[assignment]
from app.schemas.decision import RuleEngineRequest, RuleEngineResponse, TipEntry
try:  # pragma: no cover - optional dependency during unit tests
    from app.services.gemini_client import (
        GeminiCircuitOpenError,
        GeminiClientError,
        get_gemini_client,
    )
except Exception:  # pylint: disable=broad-except
    GeminiCircuitOpenError = GeminiClientError = RuntimeError  # type: ignore
    get_gemini_client = None  # type: ignore

logger = logging.getLogger(__name__)

_BANNED_SUBSTRINGS: tuple[str, ...] = (
    "bomb",
    "explosive",
    "suicide",
    "kill",
    "fuck",
    "shit",
)

_LIQUID_CANONICALS: set[str] = {
    "cosmetics_liquid",
    "medicine_liquid",
    "food_liquid",
    "hand_sanitizer_alcohol",
    "perfume",
    "alcohol_beverage",
    "duty_free_liquids_steb",
    "spray_paint",
}


class LLMTipEntry(BaseModel):
    text: str = Field(min_length=1, max_length=160)
    tags: list[str] = Field(default_factory=list)
    relevance: float = Field(default=0.7)


class LLMTipPayload(BaseModel):
    tips: list[LLMTipEntry] = Field(default_factory=list)


def fetch_llm_tips(
    request: RuleEngineRequest,
    response: RuleEngineResponse,
    *,
    label: str | None,
    locale: str | None,
    limit: int,
    locked_tip_ids: Sequence[str] | None = None,
) -> list[TipEntry]:
    """Return up to `limit` LLM-generated contextual tips."""

    if (
        limit <= 0
        or settings is None
        or not settings.llm_tips_enabled
        or not settings.gemini_api_key
        or get_gemini_client is None
    ):
        return []

    locale_value = locale or (settings.supported_locales[0] if settings.supported_locales else "ko-KR")
    hints = _build_hints(request, response)

    prompt = _build_prompt(
        request,
        response,
        label=label,
        locale=locale_value,
        limit=limit,
        locked_tip_ids=locked_tip_ids or (),
        hints=hints,
    )

    model_name = settings.llm_tips_model or settings.gemini_model
    timeout = settings.llm_tips_timeout_sec
    temperature = settings.llm_tips_temperature
    max_tokens = settings.llm_tips_max_tokens
    try:
        raw_text, _ = get_gemini_client(
            model_name=model_name,
            timeout=timeout,
        ).generate_json(
            prompt,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
    except (GeminiClientError, GeminiCircuitOpenError) as exc:  # pragma: no cover - network path
        logger.warning("LLM tips generation failed: %s", exc)
        return []

    try:
        payload = LLMTipPayload.model_validate_json(raw_text or "{}")
    except ValidationError as exc:
        logger.warning("LLM tips payload invalid: %s", exc)
        return []

    sanitized = _sanitize_entries(payload.tips, hints)
    tips: list[TipEntry] = []
    for idx, entry in enumerate(sanitized[:limit]):
        tips.append(
            TipEntry(
                id=f"tip.llm_{idx + 1}",
                text=entry.text.strip(),
                tags=entry.tags[:3],
                relevance=_clamp(entry.relevance, 0.3, 0.95),
            )
        )
    return tips


def _build_prompt(
    request: RuleEngineRequest,
    response: RuleEngineResponse,
    *,
    label: str | None,
    locale: str,
    limit: int,
    locked_tip_ids: Sequence[str],
    hints: dict[str, bool],
) -> str:
    itinerary = request.itinerary.model_dump(by_alias=True)
    decision = {
        "carry_on": response.decision.carry_on.model_dump(),
        "checked": response.decision.checked.model_dump(),
    }
    context = {
        "label": label or request.canonical,
        "canonical": request.canonical,
        "itinerary": itinerary,
        "segments": [segment.model_dump() for segment in request.segments],
        "carry_on": decision["carry_on"],
        "checked": decision["checked"],
        "badges": {
            "carry_on": response.decision.carry_on.badges,
            "checked": response.decision.checked.badges,
        },
        "conditions": response.conditions,
        "duty_free": request.duty_free.model_dump(),
        "item_params": request.item_params.model_dump(exclude_none=True),
        "locked_tip_ids": list(locked_tip_ids),
        "hints": hints,
    }
    context_json = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
    return f"""
System:
You are an airline baggage assistant who writes short Korean travel tips.
- Respond in the locale "{locale}" (fall back to Korean if unsure).
- Reflect the provided decision exactly. Never contradict statuses, badges or conditions.
- EssentialTips listed in locked_tip_ids already cover the core regulations. Do not repeat them.
- If guidance is already satisfied by EssentialTips, skip it instead of rephrasing.
- If hints.has_liquid_limits is false, do NOT mention 액체/액체류/liquid/100ml guidance.

User Input (JSON):
{context_json}

Task:
- Provide contextual advice that helps the traveler follow the rules above.
- Only suggest safe, lawful actions relevant to the given item.
- Avoid numeric rules unless they appear in the input context.
- Mention at most {limit} tips. Each tip must be ≤80 characters.

Output JSON schema:
{{"tips":[{{"text":"string","tags":["string"],"relevance":0.7}}]}}
"""


def _sanitize_entries(entries: Iterable[LLMTipEntry], hints: dict[str, bool]) -> list[LLMTipEntry]:
    def _violates_hints(text_lower: str, hints: dict[str, bool]) -> bool:
        liquid_banned = not hints.get("is_liquid_item") and not hints.get("has_liquid_limits")
        if liquid_banned and any(
            keyword in text_lower for keyword in ("액체", "액체류", "liquid", "100ml", "1l", "지퍼백")
        ):
            return True
        return False

    sanitized: list[LLMTipEntry] = []
    for entry in entries:
        text = entry.text.strip()
        if not text:
            continue
        if any(banned in text.lower() for banned in _BANNED_SUBSTRINGS):
            continue
        text_lower = text.lower()
        if _violates_hints(text_lower, hints):
            continue
        tags = [_clean_tag(tag) for tag in entry.tags[:3] if _clean_tag(tag)]
        sanitized.append(
            LLMTipEntry(text=text[:80], tags=tags, relevance=_clamp(entry.relevance, 0.0, 1.0))
        )
    return sanitized


def _clean_tag(tag: str) -> str:
    cleaned = tag.strip()
    return cleaned[:24] if cleaned else ""


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _build_hints(request: RuleEngineRequest, response: RuleEngineResponse) -> dict[str, bool]:
    carry = response.conditions.get("carry_on", {})
    common = response.conditions.get("common", {})
    has_liquid_limits = bool(
        carry.get("max_container_ml")
        or common.get("max_container_ml")
        or carry.get("zip_bag_1l")
    )
    is_liquid_item = _is_liquid_canonical(request.canonical)
    return {
        "has_liquid_limits": has_liquid_limits,
        "is_liquid_item": is_liquid_item,
    }


def _is_liquid_canonical(canonical: str) -> bool:
    return canonical in _LIQUID_CANONICALS or canonical.startswith("aerosol")


