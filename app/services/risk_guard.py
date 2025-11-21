"""LLM 응답 검증 및 규칙 레이어 병합 가드."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy.orm import Session

from app.schemas.decision import DecisionStatus, ItemParams, RuleEngineRequest, RuleEngineResponse
from app.schemas.preview import PreviewRequest, make_rule_request
from app.services.classifier_data import get_benign_keys, get_risk_keys
from app.services.rule_engine import RuleEngine, STATUS_ORDER

_REQUIRED_PARAM_MAP: dict[str, tuple[str, ...]] = {
    # aerosols / liquids / alcohol
    "aerosol_toiletry": ("volume_ml",),
    "aerosol_non_toiletry": ("volume_ml",),
    "spray_paint": ("volume_ml",),
    "bear_spray_capsaicin": ("volume_ml",),
    "compressed_gas_spray": ("volume_ml",),
    "cosmetics_liquid": ("volume_ml",),
    "perfume": ("volume_ml",),
    "nail_polish": ("volume_ml",),
    "nail_polish_remover_acetone": ("volume_ml",),
    "hand_sanitizer_alcohol": ("volume_ml",),
    "medicine_liquid": ("volume_ml",),
    "food_liquid": ("volume_ml",),
    "alcohol_beverage": ("volume_ml", "abv_percent"),
    "duty_free_liquids_steb": ("volume_ml",),
    # batteries
    "lithium_battery_spare": ("wh", "count"),
    "lithium_battery_installed": ("wh",),
    "power_bank": ("wh", "count"),
    "smart_luggage_battery": ("wh",),
    "e_bike_scooter_battery": ("wh", "count"),
    "button_cell_battery": ("wh", "count"),
    "ni_mh_nicd_battery": ("wh", "count"),
    "wet_cell_battery": ("wh", "count"),
    "wheelchair_battery": ("wh",),
    "heat_tool_soldering_iron": ("wh",),
    "power_tool_battery": ("wh", "count"),
    # dry ice
    "dry_ice": ("weight_kg",),
    # blades / tools
    "knife": ("blade_length_cm",),
    "scissors": ("blade_length_cm",),
    "multi_tool": ("blade_length_cm",),
    # cylinders / gas
    "co2_cartridge_small": ("count",),
    "oxygen_cylinder_medical": ("count",),
    "scuba_tank": ("count",),
    "camping_gas_canister": ("count",),
}

RISK_KEYS = set(get_risk_keys())
BENIGN_KEYS = set(get_benign_keys())


class LLMDecisionSlot(BaseModel):
    status: DecisionStatus
    badges: list[str] = Field(default_factory=list)


class LLMSignals(BaseModel):
    matched_terms: list[str] = Field(default_factory=list)
    confidence: float
    notes: str | None = None

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        if not (0.0 <= value <= 1.0):
            raise ValueError("confidence must be between 0 and 1")
        return value

    @field_validator("matched_terms")
    @classmethod
    def validate_terms(cls, value: list[str]) -> list[str]:
        if not (2 <= len(value) <= 4):
            raise ValueError("matched_terms must contain 2-4 entries")
        cleaned: list[str] = []
        for token in value:
            if not isinstance(token, str):
                raise ValueError("matched_terms entries must be strings")
            stripped = token.strip()
            if not stripped:
                raise ValueError("matched_terms entries must not be empty")
            cleaned.append(stripped)
        return cleaned


class LLMDecisionPayload(BaseModel):
    canonical: str
    params: ItemParams = Field(default_factory=ItemParams)
    carry_on: LLMDecisionSlot
    checked: LLMDecisionSlot
    needs_review: bool = False
    signals: LLMSignals
    model_info: Dict[str, Any] | None = None

    @field_validator("canonical")
    @classmethod
    def validate_canonical(cls, value: str) -> str:
        allowed = RISK_KEYS | BENIGN_KEYS
        if value not in allowed:
            raise ValueError(f"canonical must be one of {sorted(allowed)}")
        return value

class LLMResponseValidationError(RuntimeError):
    """Raised when the LLM JSON payload fails schema validation."""


def parse_llm_payload(response_text: str) -> LLMDecisionPayload:
    """Parse & validate raw LLM JSON 문자열을 구조화된 페이로드로 변환."""

    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise LLMResponseValidationError("LLM output is not valid JSON") from exc

    try:
        return LLMDecisionPayload.model_validate(payload)
    except ValidationError as exc:  # pragma: no cover - pydantic formatting
        raise LLMResponseValidationError(f"LLM payload validation failed: {exc}") from exc


@dataclass(slots=True)
class MergeOutcome:
    engine: RuleEngineResponse
    engine_request: RuleEngineRequest
    conflict: bool
    conflict_slots: Dict[str, Dict[str, DecisionStatus]]
    missing_params: tuple[str, ...]

def merge_layers(
    llm_payload: LLMDecisionPayload,
    preview_req: PreviewRequest,
    *,
    req_id: str,
    db: Session,
) -> MergeOutcome:
    """LLM 초안과 결정적 규칙 레이어 결과를 병합하고 충돌 여부를 판단."""

    engine = RuleEngine(db)
    engine_req = make_rule_request(
        llm_payload.canonical,
        req_id,
        preview_req,
        item_params=llm_payload.params,
    )
    engine_response = engine.evaluate(engine_req)

    conflicts = _detect_conflicts(llm_payload, engine_response)
    missing = _detect_missing_params(llm_payload)
    return MergeOutcome(
        engine=engine_response,
        engine_request=engine_req,
        conflict=bool(conflicts),
        conflict_slots=conflicts,
        missing_params=missing,
    )


def _detect_conflicts(
    llm_payload: LLMDecisionPayload,
    engine_response: RuleEngineResponse,
) -> Dict[str, Dict[str, DecisionStatus]]:
    conflicts: Dict[str, Dict[str, DecisionStatus]] = {}
    llm_status = {
        "carry_on": llm_payload.carry_on.status,
        "checked": llm_payload.checked.status,
    }
    engine_status = {
        "carry_on": engine_response.decision.carry_on.status,
        "checked": engine_response.decision.checked.status,
    }
    for slot, llm_value in llm_status.items():
        final_value = engine_status[slot]
        if _is_more_restrictive(final_value, llm_value):
            conflicts[slot] = {"llm": llm_value, "final": final_value}
    return conflicts


def _is_more_restrictive(final_status: DecisionStatus, drafted_status: DecisionStatus) -> bool:
    return STATUS_ORDER[final_status] > STATUS_ORDER[drafted_status]


def _detect_missing_params(payload: LLMDecisionPayload) -> tuple[str, ...]:
    if payload.canonical in BENIGN_KEYS:
        return ()
    required = _REQUIRED_PARAM_MAP.get(payload.canonical, ())
    missing: list[str] = []
    for key in required:
        value = getattr(payload.params, key, None)
        if value is None:
            missing.append(key)
    return tuple(missing)

