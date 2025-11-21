"""LLM 호출을 통해 위험물 분류/파라미터/판정 초안을 동시에 생성."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import settings
from app.schemas.preview import PreviewRequest
from app.services.classifier_data import get_benign_keys, get_risk_keys
from app.services.dict_classifier import normalize_label
from app.services.gemini_client import (
    GeminiCircuitOpenError,
    GeminiClientError,
    get_gemini_client,
)
from app.services.risk_guard import LLMDecisionPayload, LLMResponseValidationError, parse_llm_payload

logger = logging.getLogger(__name__)

_DETERMINISTIC_TEMP_CAP = 0.05
RISK_KEYS = get_risk_keys()
BENIGN_KEYS = get_benign_keys()


class LLMDecisionError(RuntimeError):
    """Raised when the decision-specific LLM call fails or returns invalid JSON."""


def fetch_llm_decision(preview: PreviewRequest) -> LLMDecisionPayload:
    """Call Gemini once to obtain canonical + params + draft decision."""

    prompt = _build_prompt(preview)
    temperature = min(max(settings.llm_classifier_temperature, 0.0), _DETERMINISTIC_TEMP_CAP)

    try:
        response_text, model_info = get_gemini_client().generate_json(
            prompt,
            temperature=temperature,
            max_output_tokens=settings.llm_classifier_max_tokens,
        )
    except (GeminiClientError, GeminiCircuitOpenError) as exc:  # pragma: no cover - network path
        raise LLMDecisionError(str(exc)) from exc

    try:
        payload = parse_llm_payload(response_text)
    except LLMResponseValidationError as exc:
        logger.warning("LLM payload invalid, attempting auto-fix: %s", exc)
        fixed_text = _repair_matched_terms(response_text, preview)
        if fixed_text is None:
            raise LLMDecisionError(str(exc)) from exc
        try:
            payload = parse_llm_payload(fixed_text)
        except LLMResponseValidationError as exc2:
            raise LLMDecisionError(str(exc2)) from exc2

    if model_info:
        payload.model_info = {**(payload.model_info or {}), **model_info}
    return payload
def _repair_matched_terms(response_text: str, preview: PreviewRequest) -> str | None:
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        return None
    signals = data.get("signals")
    if not isinstance(signals, dict):
        return None
    terms = signals.get("matched_terms")
    if not isinstance(terms, list):
        terms = []
    cleaned = [token.strip() for token in terms if isinstance(token, str) and token.strip()]
    if len(cleaned) >= 2:
        return None
    extra_terms: list[str] = []
    candidates = [preview.label, normalize_label(preview.label)]
    for value in candidates:
        if not value:
            continue
        for token in value.split():
            token = token.strip()
            if not token or token in cleaned or token in extra_terms:
                continue
            extra_terms.append(token)
            if len(cleaned) + len(extra_terms) >= 2:
                break
        if len(cleaned) + len(extra_terms) >= 2:
            break
    if len(cleaned) + len(extra_terms) < 2 and preview.label:
        word = preview.label.strip()
        if len(word) > 1:
            midpoint = max(1, len(word) // 2)
            part_a = word[:midpoint]
            part_b = word[midpoint:]
            for part in (part_a, part_b):
                token = part.strip()
                if token and token not in cleaned and token not in extra_terms:
                    extra_terms.append(token)
                if len(cleaned) + len(extra_terms) >= 2:
                    break
    merged = (cleaned + extra_terms)[:4]
    if len(merged) < 2:
        return None
    signals["matched_terms"] = merged
    return json.dumps(data, ensure_ascii=False)


def _build_prompt(preview: PreviewRequest) -> str:
    risk_list = ", ".join(f'"{key}"' for key in RISK_KEYS)
    benign_list = ", ".join(f'"{key}"' for key in BENIGN_KEYS)
    itinerary = preview.itinerary.model_dump(by_alias=True)
    segments = [segment.model_dump() for segment in preview.segments]
    input_payload: dict[str, Any] = {
        "label": preview.label,
        "normalized_label": normalize_label(preview.label),
        "locale": preview.locale or "unknown",
        "itinerary": itinerary,
        "segments": segments,
        "item_params": preview.item_params.model_dump(),
        "duty_free": preview.duty_free.model_dump(),
    }
    input_json = json.dumps(input_payload, ensure_ascii=False)

    return f"""
System:
You are a strict airline baggage classifier. Output VALID JSON only (no prose, no code fences).
Hard rules:
- canonical must be in ALLOWED_KEYS. If the item is clearly non-risky, choose one of BENIGN_KEYS (default: benign_general).
- Never guess numeric params. If not provided, set null.
- signals.matched_terms must contain 2-4 tokens taken from label/normalized_label even when canonical=benign_general.
- status values must be one of "allow", "limit", "deny".
- badges should justify the decision using short labels (e.g., "100ml", "carry-on only").
- needs_review should default to false unless you are certain human review is required.

How to decide:
- Liquids/aerosols/perfume/hand_sanitizer/duty_free → carry_on.limit (100ml/1L bag), checked.allow.
- Alcohol beverages → carry_on.limit (LAGs), checked.limit (duty or volume caps).
- Spare lithium/power banks → carry_on.allow (or limit), checked.deny.
- Installed batteries/large electronics → carry_on.allow, checked.allow (unless prohibited).
- Blades/knives → carry_on.deny, checked.allow or limit.
- Everyday benign items (clothes, books, solid toiletries, umbrellas, toys without batteries) → choose the closest BENIGN_KEYS entry and set both carry_on/checked to allow.

Output schema:
{{
  "canonical": "string",
  "params": {{
    "volume_ml": number|null,
    "wh": number|null,
    "count": number|null,
    "abv_percent": number|null,
    "weight_kg": number|null,
    "blade_length_cm": number|null
  }},
  "carry_on": {{"status":"allow|limit|deny","badges":[string]}},
  "checked":  {{"status":"allow|limit|deny","badges":[string]}},
  "needs_review": boolean,
  "signals": {{"matched_terms":[string],"confidence": number,"notes":string|null}},
  "model_info": {{"name": string, "version": string}} | null
}}

ALLOWED_RISK_KEYS = [{risk_list}]
BENIGN_KEYS = [{benign_list}]
ALLOWED_KEYS = ALLOWED_RISK_KEYS + BENIGN_KEYS
INPUT = {input_json}
"""

