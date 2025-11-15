"""Pydantic schemas for the rule-engine API surface."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, constr


class ItemParams(BaseModel):
    volume_ml: float | None = None
    wh: float | None = None
    count: int | None = None
    abv_percent: float | None = None
    weight_kg: float | None = None


class ItineraryInfo(BaseModel):
    origin: constr(strip_whitespace=True, min_length=3) = Field(..., alias="from")  # type: ignore[valid-type]
    destination: constr(strip_whitespace=True, min_length=3) = Field(..., alias="to")  # type: ignore[valid-type]
    via: list[str] = Field(default_factory=list)
    rescreening: bool = False

    class Config:
        populate_by_name = True


class SegmentInfo(BaseModel):
    leg: str
    operating: constr(strip_whitespace=True, min_length=2)  # type: ignore[valid-type]
    cabin_class: str | None = None


class DutyFreeInfo(BaseModel):
    is_df: bool = False
    steb_sealed: bool = False


class RuleEngineRequest(BaseModel):
    canonical: str
    req_id: str | None = None
    item_params: ItemParams = Field(default_factory=ItemParams)
    itinerary: ItineraryInfo
    segments: list[SegmentInfo] = Field(default_factory=list)
    duty_free: DutyFreeInfo = Field(default_factory=DutyFreeInfo)


DecisionStatus = Literal["allow", "limit", "deny"]


class DecisionSlot(BaseModel):
    status: DecisionStatus
    badges: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)


class DecisionPayload(BaseModel):
    carry_on: DecisionSlot
    checked: DecisionSlot


class SourceEntry(BaseModel):
    layer: str
    code: str


class TraceEntry(BaseModel):
    rule_id: int | None = None
    layer: str
    code: str
    item_category: str | None = None
    effect: Dict[str, DecisionStatus | None]
    applied: bool
    reason_codes: list[str] = Field(default_factory=list)
    constraints_used: Dict[str, Any] = Field(default_factory=dict)


class TipEntry(BaseModel):
    id: str
    text: str
    tags: list[str] = Field(default_factory=list)
    relevance: float = 0.5


class RuleEngineResponse(BaseModel):
    req_id: str
    canonical: str
    decision: DecisionPayload
    conditions: Dict[str, Any]
    sources: list[SourceEntry]
    trace: list[TraceEntry]
    ai_tips: list[TipEntry] = Field(default_factory=list)


