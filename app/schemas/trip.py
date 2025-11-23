from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, constr, model_validator

from app.schemas.checklist import BagItemStatus

class TripSegmentInput(BaseModel):
    leg: constr(strip_whitespace=True, min_length=7)  # type: ignore[valid-type]
    operating: constr(strip_whitespace=True, min_length=2, max_length=8) | None = None  # type: ignore[valid-type]
    cabin_class: constr(strip_whitespace=True, min_length=2, max_length=32) | None = None  # type: ignore[valid-type]


class TripSegmentOutput(TripSegmentInput):
    segment_id: int | None = None
    segment_order: int
    direction: Literal["outbound", "return"] | None = None
    departure_airport: str | None = None
    arrival_airport: str | None = None
    departure_country: str | None = None
    arrival_country: str | None = None
    departure_date: date | None = None


class ItinerarySnapshot(BaseModel):
    from_airport: str | None = Field(None, alias="from")
    via_airports: list[str] = Field(default_factory=list, alias="via")
    to_airport: str | None = Field(None, alias="to")
    route_type: Literal["domestic", "international"] | None = None
    segments: list[TripSegmentOutput] = Field(default_factory=list)

    class Config:
        populate_by_name = True


class TripStats(BaseModel):
    items_scanned: int = 0
    last_activity_at: datetime | None = None


class TripBase(BaseModel):
    title: str | None = None
    from_airport: str | None = None
    to_airport: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    tags: list[str] = Field(default_factory=list)
    note: str | None = None


class TripCreate(TripBase):
    via_airports: list[str] = Field(default_factory=list)
    segments: list[TripSegmentInput] = Field(default_factory=list)


class TripUpdate(BaseModel):
    title: str | None = None
    from_airport: str | None = None
    to_airport: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    via_airports: list[str] | None = None
    segments: list[TripSegmentInput] | None = None
    tags: list[str] | None = None
    note: str | None = None
    active: bool | None = None
    archived_at: datetime | None = None


class TripDetail(BaseModel):
    trip_id: int
    title: str | None = None
    note: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    active: bool
    needs_duration: bool
    tags: list[str] = Field(default_factory=list)
    itinerary: ItinerarySnapshot
    stats: TripStats
    created_at: datetime | None = None
    updated_at: datetime | None = None
    archived_at: datetime | None = None


class TripListItem(BaseModel):
    trip_id: int
    title: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    from_airport: str | None = None
    to_airport: str | None = None
    active: bool
    needs_duration: bool
    archived_at: datetime | None = None


class TripListResponse(BaseModel):
    items: list[TripListItem]
    next_offset: int | None = None
    has_more: bool = False


class TripItemListItem(BaseModel):
    item_id: int
    bag_id: int
    bag_name: str
    title: str | None = None
    status: BagItemStatus
    quantity: int
    note: str | None = None
    regulation_match_id: int | None = None
    raw_label: str | None = None
    norm_label: str | None = None
    canonical_key: str | None = None
    preview_snapshot: dict | None = None
    updated_at: datetime | None = None


class TripItemsListResponse(BaseModel):
    items: list[TripItemListItem]
    next_offset: int | None = None
    has_more: bool = False


class TripDurationUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def _validate_dates(self) -> "TripDurationUpdate":
        if self.start_date is None and self.end_date is None:
            raise ValueError("at_least_one_field_required")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("invalid_date_range")
        return self


class TripDurationStatus(BaseModel):
    trip_id: int
    start_date: date | None = None
    end_date: date | None = None
    needs_duration: bool

