from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class InputSummary(BaseModel):
    latitude: float
    longitude: float
    start: str
    end: str
    years: int
    aggregation: str


class ClimatePointMeta(BaseModel):
    latitude: float
    longitude: float
    altitude_m: float | None = None


class ClimatePeriod(BaseModel):
    months: List[int]
    days_per_month: dict[int, int]
    total_days: int


class ClimateSummary(BaseModel):
    t_mean_c: float | None = None
    t_min_c: float | None = None
    t_max_c: float | None = None
    precip_sum_mm: float | None = None


class ClimateMonthlyBreakdown(BaseModel):
    month: int
    t_mean_c: float | None = None
    t_min_c: float | None = None
    t_max_c: float | None = None
    precip_sum_mm: float | None = None


class ClimateRecentResponse(BaseModel):
    trip_id: int
    input: InputSummary
    point: ClimatePointMeta
    period: ClimatePeriod
    basis: str
    recent_stats: ClimateSummary
    months_breakdown: list[ClimateMonthlyBreakdown]
    used_years: list[int] = Field(default_factory=list)
    degraded: bool = False
    source: list[str] = Field(default_factory=list)
    generated_at: datetime


