from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, constr

BagType = Literal["carry_on", "checked", "custom"]
BagItemStatus = Literal["todo", "packed"]


class BagBase(BaseModel):
    name: constr(strip_whitespace=True, min_length=1, max_length=120) | None = None  # type: ignore[valid-type]
    bag_type: BagType | None = None


class BagCreate(BagBase):
    name: constr(strip_whitespace=True, min_length=1, max_length=120)  # type: ignore[valid-type]
    bag_type: BagType = "custom"
    sort_order: int | None = Field(None, ge=0, le=10_000)
    is_default: bool = False


class BagUpdate(BagBase):
    sort_order: int | None = Field(None, ge=0, le=10_000)


class BagSummary(BaseModel):
    bag_id: int
    trip_id: int
    name: str
    bag_type: BagType
    is_default: bool
    sort_order: int
    total_items: int = 0
    packed_items: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BagListResponse(BaseModel):
    items: list[BagSummary]


class BagItemBase(BaseModel):
    title: constr(strip_whitespace=True, min_length=1, max_length=255) | None = None  # type: ignore[valid-type]
    quantity: int = Field(1, ge=1, le=1000)
    note: constr(strip_whitespace=True, max_length=2000) | None = None  # type: ignore[valid-type]
    status: BagItemStatus = "todo"


class BagItemUpdate(BaseModel):
    bag_id: int | None = None
    title: constr(strip_whitespace=True, min_length=1, max_length=255) | None = None  # type: ignore[valid-type]
    quantity: int | None = Field(None, ge=1, le=1000)
    note: constr(strip_whitespace=True, max_length=2000) | None = None  # type: ignore[valid-type]
    status: BagItemStatus | None = None


class BagItemDetail(BagItemBase):
    item_id: int
    bag_id: int
    trip_id: int
    regulation_match_id: int | None = None
    preview_snapshot: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BagItemsListResponse(BaseModel):
    items: list[BagItemDetail]
    next_offset: int | None = None
    has_more: bool = False


