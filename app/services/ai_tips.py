"""Rule-based generation of actionable travel tips."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from app.schemas.decision import RuleEngineRequest, RuleEngineResponse, TipEntry


TipPredicate = Callable[[RuleEngineRequest, RuleEngineResponse], bool]
TipBuilder = Callable[[RuleEngineRequest, RuleEngineResponse], str]


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
    limit: int = 4,
) -> list[TipEntry]:
    """Return up to `limit` tips that match the current item context."""

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
        if len(tips) >= limit:
            break
    return tips


def _carry_status(response: RuleEngineResponse) -> str:
    return response.decision.carry_on.status


def _checked_status(response: RuleEngineResponse) -> str:
    return response.decision.checked.status


def _has_badge(badges: Iterable[str], keyword: str) -> bool:
    keyword = keyword.lower()
    return any(keyword in badge.lower() for badge in badges)


def _tip_text(text: str) -> TipBuilder:
    return lambda _req, _resp: text


def _split_volume_text(request: RuleEngineRequest, response: RuleEngineResponse) -> str:
    volume = request.item_params.volume_ml
    max_ml = response.conditions.get("max_container_ml")
    if volume and max_ml:
        return f"{max_ml}ml 이하 빈 용기에 소분하면 기내 반입 가능해요."
    return "100ml 이하 빈 용기에 소분하면 기내로 가져갈 수 있어요."


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
    return f"기내 한도({joined})를 넘지 않게 짐을 분배하세요."


def _rescreen_text(request: RuleEngineRequest, _response: RuleEngineResponse) -> str:
    via = ", ".join(request.itinerary.via) or "경유지"
    return f"{via} 보안검색 재검이 있으니 액체와 전자제품을 가방 상단에 모아두세요."


def _leak_text(_req: RuleEngineRequest, _response: RuleEngineResponse) -> str:
    return "위탁 시 마개를 테이프로 감고 지퍼백 이중 포장으로 누수 위험을 줄이세요."


def _aerosol_text(_req: RuleEngineRequest, _response: RuleEngineResponse) -> str:
    return "스프레이 버튼을 풀리지 않게 캡을 씌우고 의류 사이에 넣어 충격을 줄이세요."


def _battery_text(_req: RuleEngineRequest, _response: RuleEngineResponse) -> str:
    return "스페어 배터리는 단자를 절연 테이프나 파우치로 감싸 기내 휴대로만 보관하세요."


TIP_RULES: tuple[TipRule, ...] = (
    TipRule(
        id="tip.split_100ml",
        tags=("액체류", "기내"),
        relevance=0.95,
        predicate=lambda req, resp: resp.conditions.get("max_container_ml") == 100
        and _carry_status(resp) != "deny"
        and (req.item_params.volume_ml or 0) > 100,
        builder=_split_volume_text,
    ),
    TipRule(
        id="tip.zip_bag",
        tags=("보안절차",),
        relevance=0.9,
        predicate=lambda _req, resp: resp.conditions.get("max_container_ml") == 100
        and resp.conditions.get("zip_bag_1l"),
        builder=_tip_text("액체는 1L 투명 지퍼백에 따로 넣어 보안대에서 한 번에 꺼낼 수 있게 하세요."),
    ),
    TipRule(
        id="tip.rescreen",
        tags=("경유", "보안절차"),
        relevance=0.85,
        predicate=lambda req, resp: req.itinerary.rescreening and _carry_status(resp) != "deny",
        builder=_rescreen_text,
    ),
    TipRule(
        id="tip.leak_checked",
        tags=("위탁",),
        relevance=0.8,
        predicate=lambda _req, resp: _checked_status(resp) != "deny",
        builder=_leak_text,
    ),
    TipRule(
        id="tip.carry_limit",
        tags=("기내",),
        relevance=0.78,
        predicate=lambda _req, resp: _carry_status(resp) != "deny"
        and (
            _has_badge(resp.decision.carry_on.badges, "kg")
            or _has_badge(resp.decision.carry_on.badges, "pc")
        ),
        builder=_carry_limit_text,
    ),
    TipRule(
        id="tip.aerosol_cap",
        tags=("에어로졸", "안전"),
        relevance=0.75,
        predicate=lambda req, resp: req.canonical.startswith("aerosol")
        and _checked_status(resp) != "deny",
        builder=_aerosol_text,
    ),
    TipRule(
        id="tip.lithium_spare",
        tags=("배터리", "기내"),
        relevance=0.75,
        predicate=lambda req, resp: req.canonical == "lithium_ion_battery_spare"
        and _carry_status(resp) != "deny",
        builder=_battery_text,
    ),
)

