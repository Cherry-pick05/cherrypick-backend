"""Template-based narration builder for rule-engine outputs."""

from __future__ import annotations

from typing import Iterable

from app.schemas.decision import DecisionSlot, RuleEngineResponse
from app.schemas.preview import NarrationPayload, PreviewRequest
from app.services.item_classifier import ClassificationResult


STATUS_LABELS = {
    "allow": "허용",
    "limit": "조건부 허용",
    "deny": "금지",
}


def build_narration(
    preview: PreviewRequest,
    classification: ClassificationResult,
    engine: RuleEngineResponse,
) -> NarrationPayload:
    carry = engine.decision.carry_on
    checked = engine.decision.checked
    title = _title_for(classification, preview)
    carry_card = _card_for(carry, engine.conditions)
    checked_card = _card_for(checked, engine.conditions, checked=True)
    bullets = _build_bullets(engine)
    badges = sorted(set(carry.badges))
    sources = _summarize_sources(engine)
    footnote = "세관/검역 규정은 별도 적용될 수 있습니다."
    return NarrationPayload(
        title=title,
        carry_on_card=carry_card,
        checked_card=checked_card,
        bullets=bullets,
        badges=badges,
        footnote=footnote,
        sources=sources,
    )


def _title_for(classification: ClassificationResult, preview: PreviewRequest) -> str:
    label = preview.label.strip() or classification.raw_label
    volume = preview.item_params.volume_ml
    if volume:
        return f"{label} · {int(volume)}ml"
    return label


def _card_for(slot: DecisionSlot, conditions: dict[str, object], *, checked: bool = False):
    status_label = STATUS_LABELS.get(slot.status, slot.status)
    if slot.status == "deny":
        reason = "규정상 허용되지 않습니다."
    elif slot.status == "limit":
        if _is_lag_condition(conditions):
            reason = "100ml 이하 용기만 1L 지퍼백으로 반입"
        elif checked:
            reason = "위탁 가능(항공사·위험물 한도 내)"
        else:
            reason = "조건 충족 시 반입 가능"
    else:
        reason = "별도 제한 없이 허용됩니다."
    return {"status_label": status_label, "short_reason": reason}


def _is_lag_condition(conditions: dict[str, object]) -> bool:
    return conditions.get("max_container_ml") == 100 and conditions.get("zip_bag_1l") is True


def _build_bullets(engine: RuleEngineResponse) -> list[str]:
    bullets: list[str] = []
    conditions = engine.conditions
    if _is_lag_condition(conditions):
        bullets.append("보안: 100ml 이하만, 1L 지퍼백 1개 필요")
    if "md_per_container_ml" in conditions or "md_total_ml" in conditions:
        per_ml = int(conditions.get("md_per_container_ml", 0))
        total_ml = int(conditions.get("md_total_ml", 0))
        parts = []
        if per_ml:
            parts.append(f"용기 {per_ml}ml 이하")
        if total_ml:
            parts.append(f"총 {total_ml}ml 한도")
        bullets.append("에어로졸: " + ", ".join(parts))
    carry_badges = engine.decision.carry_on.badges
    carry_parts = [b for b in carry_badges if b.endswith(("pc", "kg", "cm"))]
    if carry_parts:
        bullets.append("기내 한도: " + " · ".join(carry_parts))
    return bullets[:3]


def _summarize_sources(engine: RuleEngineResponse) -> list[str]:
    entries: list[str] = []
    for source in engine.sources[:3]:
        label = _layer_label(source.layer)
        entries.append(f"{label}/{source.code}")
    return entries


def _layer_label(layer: str) -> str:
    mapping = {
        "country_security": "보안",
        "dangerous_goods": "위험물",
        "airline": "항공사",
        "international": "국제",
    }
    return mapping.get(layer, layer)

