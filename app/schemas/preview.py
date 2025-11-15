from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.decision import (
    DutyFreeInfo,
    ItemParams,
    ItineraryInfo,
    RuleEngineRequest,
    RuleEngineResponse,
    SegmentInfo,
    TipEntry,
)


class PreviewRequest(BaseModel):
    label: str
    locale: str | None = None
    req_id: str | None = None
    itinerary: ItineraryInfo
    segments: list[SegmentInfo] = Field(default_factory=list)
    item_params: ItemParams = Field(default_factory=ItemParams)
    duty_free: DutyFreeInfo = Field(default_factory=DutyFreeInfo)


class ResolvedInfo(BaseModel):
    label: str
    canonical: str | None = None
    locale: str | None = None


class NarrationCard(BaseModel):
    status_label: str
    short_reason: str


class NarrationPayload(BaseModel):
    title: str
    carry_on_card: NarrationCard
    checked_card: NarrationCard
    bullets: list[str]
    badges: list[str]
    footnote: str | None = None
    sources: list[str] = Field(default_factory=list)


class PreviewResponse(BaseModel):
    state: Literal["complete", "needs_review"] = "complete"
    resolved: ResolvedInfo
    engine: RuleEngineResponse | None = None
    narration: NarrationPayload | None = None
    ai_tips: list[TipEntry] = Field(default_factory=list)


def make_rule_request(
    canonical: str,
    req_id: str,
    preview: PreviewRequest,
) -> RuleEngineRequest:
    return RuleEngineRequest(
        canonical=canonical,
        req_id=req_id,
        itinerary=preview.itinerary,
        segments=preview.segments,
        item_params=preview.item_params,
        duty_free=preview.duty_free,
    )

