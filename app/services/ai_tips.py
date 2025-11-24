"""Rule-based + LLM-backed travel tips."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence
from app.schemas.decision import RuleEngineRequest, RuleEngineResponse, TipEntry
from app.services.llm_tips import fetch_llm_tips

TipPredicate = Callable[[RuleEngineRequest, RuleEngineResponse], bool]
TipBuilder = Callable[[RuleEngineRequest, RuleEngineResponse], str]


LIQUID_KEYS: set[str] = {
    "cosmetics_liquid",
    "medicine_liquid",
    "food_liquid",
    "hand_sanitizer_alcohol",
    "perfume",
    "alcohol_beverage",
    "duty_free_liquids_steb",
    "spray_paint",
}
BATTERY_SPARE_KEYS: set[str] = {
    "lithium_ion_battery_spare",
    "lithium_metal_battery_spare",
}


@dataclass(slots=True)
class TipRule:
    id: str
    tags: Sequence[str]
    relevance: float
    predicate: TipPredicate
    builder: TipBuilder


def generate_ai_tips(
    request: RuleEngineRequest,
    response: RuleEngineResponse,
    *,
    label: str | None = None,
    locale: str | None = None,
    limit: int = 4,
) -> list[TipEntry]:
    """Return up to `limit` tips by merging essential rules + LLM assistance."""

    essential = _select_essential_tips(request, response)
    essential = _prioritize_and_clip(essential, limit)
    remaining = max(0, limit - len(essential))

    llm_tips: list[TipEntry] = []
    if remaining:
        llm_tips = fetch_llm_tips(
            request,
            response,
            label=label,
            locale=locale,
            limit=remaining,
            locked_tip_ids=[tip.id for tip in essential],
        )

    return essential + llm_tips


def _select_essential_tips(
    request: RuleEngineRequest,
    response: RuleEngineResponse,
) -> list[TipEntry]:
    tips: list[TipEntry] = []
    seen: set[str] = set()
    for rule in TIP_RULES:
        if rule.id in seen:
            continue
        if not rule.predicate(request, response):
            continue
        text = rule.builder(request, response).strip()
        if not text:
            continue
        tips.append(
            TipEntry(
                id=rule.id,
                text=text,
                tags=list(rule.tags),
                relevance=rule.relevance,
            )
        )
        seen.add(rule.id)
    return tips


def _prioritize_and_clip(tips: Sequence[TipEntry], limit: int) -> list[TipEntry]:
    if not tips:
        return []
    ordered = sorted(tips, key=lambda tip: (-tip.relevance, tip.id))
    selected: list[TipEntry] = []
    used_tags: set[str] = set()
    for tip in ordered:
        if tip.tags and set(tip.tags).issubset(used_tags):
            continue
        selected.append(tip)
        used_tags.update(tip.tags)
        if len(selected) >= limit:
            break
    return selected


def _carry_conditions(response: RuleEngineResponse) -> dict:
    return response.conditions.get("carry_on", {})


def _common_conditions(response: RuleEngineResponse) -> dict:
    return response.conditions.get("common", {})


def _carry_status(response: RuleEngineResponse) -> str:
    return response.decision.carry_on.status


def _checked_status(response: RuleEngineResponse) -> str:
    return response.decision.checked.status


def _has_badge(badges: Iterable[str], keyword: str) -> bool:
    keyword = keyword.lower()
    return any(keyword in badge.lower() for badge in badges)


def _max_container_limit(response: RuleEngineResponse) -> int | None:
    carry_value = _carry_conditions(response).get("max_container_ml")
    if carry_value:
        return carry_value
    return _common_conditions(response).get("max_container_ml")


def _split_volume_text(request: RuleEngineRequest, response: RuleEngineResponse) -> str:
    volume = request.item_params.volume_ml
    max_ml = _max_container_limit(response)
    if volume and max_ml:
        return f"{max_ml}ml 이하 빈 용기에 소분하면 기내 반입이 가능합니다."
    return "100ml 이하 빈 용기에 나눠 담으면 기내로 가져갈 수 있어요."


def _carry_limit_text(_req: RuleEngineRequest, response: RuleEngineResponse) -> str:
    badges = response.decision.carry_on.badges
    pieces = next((b for b in badges if b.endswith("pc")), "기내 수하물")
    weight = next((b for b in badges if b.endswith("kg")), "")
    size = next((b for b in badges if b.endswith("cm")), "")
    parts = [pieces]
    if weight:
        parts.append(weight)
    if size:
        parts.append(size)
    joined = " · ".join(parts)
    return f"기내 한도({joined})를 넘지 않게 짐을 나눠 담으세요."


def _aerosol_text(_req: RuleEngineRequest, _response: RuleEngineResponse) -> str:
    return "스프레이 버튼과 노즐은 캡을 씌워 충격이나 오작동을 막아주세요."


def _battery_text(_req: RuleEngineRequest, _response: RuleEngineResponse) -> str:
    return "스페어 배터리는 단자를 절연해 기내 휴대로만 보관하세요."


def _is_liquid_item(canonical: str) -> bool:
    return canonical in LIQUID_KEYS or canonical.startswith("aerosol")


def _is_aerosol_item(canonical: str) -> bool:
    return canonical.startswith("aerosol")


TIP_RULES: tuple[TipRule, ...] = (
    TipRule(
        id="tip.split_100ml",
        tags=("액체류", "소분"),
        relevance=0.96,
        predicate=lambda req, resp: _is_liquid_item(req.canonical)
        and _max_container_limit(resp) == 100
        and (req.item_params.volume_ml or 0) > 100,
        builder=_split_volume_text,
    ),
    TipRule(
        id="tip.zip_bag",
        tags=("보안절차",),
        relevance=0.9,
        predicate=lambda req, resp: _is_liquid_item(req.canonical)
        and _max_container_limit(resp) == 100
        and bool(_carry_conditions(resp).get("zip_bag_1l")),
        builder=lambda _req, _resp: "액체는 1L 투명 지퍼백에 넣어 보안대에서 한 번에 꺼내세요.",
    ),
    TipRule(
        id="tip.carry_limit",
        tags=("기내한도",),
        relevance=0.82,
        predicate=lambda _req, resp: _carry_status(resp) != "deny"
        and (
            _has_badge(resp.decision.carry_on.badges, "kg")
            or _has_badge(resp.decision.carry_on.badges, "pc")
            or _has_badge(resp.decision.carry_on.badges, "cm")
        ),
        builder=_carry_limit_text,
    ),
    TipRule(
        id="tip.aerosol_cap",
        tags=("에어로졸", "안전"),
        relevance=0.78,
        predicate=lambda req, resp: _is_aerosol_item(req.canonical)
        and any(
            status in {"allow", "limit"}
            for status in (_carry_status(resp), _checked_status(resp))
        ),
        builder=_aerosol_text,
    ),
    TipRule(
        id="tip.lithium_spare",
        tags=("배터리", "기내"),
        relevance=0.76,
        predicate=lambda req, resp: req.canonical in BATTERY_SPARE_KEYS
        and _carry_status(resp) != "deny",
        builder=_battery_text,
    ),
)

