from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.climate import ClimateRecentResponse


class WeatherInfo(BaseModel):
    summary: str | None = None
    temperature_c: float | None = None
    feels_like_c: float | None = None
    humidity: int | None = None
    icon: str | None = None


class ExchangeRateInfo(BaseModel):
    currency_code: str
    currency_name: str | None = None
    base_currency: str = "KRW"
    rate: float | None = None
    last_updated: date | None = None


class TripRecommendationResponse(BaseModel):
    trip_id: int
    city: str | None = None
    country_code: str | None = None
    weather: WeatherInfo | None = None
    exchange_rate: ExchangeRateInfo | None = None
    popular_items: list[str] = Field(default_factory=list)
    outfit_tip: str | None = None
    shopping_guide: str | None = None


class RecommendationItem(BaseModel):
    key: str
    label: str
    priority: Literal["high", "medium", "low"]
    why: str


class TemperatureRange(BaseModel):
    min: float | None = None
    max: float | None = None
    mean: float | None = None


class RecommendationFacts(BaseModel):
    basis: Literal["forecast", "historical_normals", "heuristic"]
    date_span: list[str] = Field(default_factory=list)
    temp_c: TemperatureRange | None = None
    precip_mm: float | None = None
    pop: float | None = None
    condition: str | None = None


class OutfitRecommendationBody(BaseModel):
    title: str
    description: str
    items: list[RecommendationItem]
    facts: RecommendationFacts | None = None


class OutfitRecommendationResponse(BaseModel):
    trip_id: int
    climate: ClimateRecentResponse
    recommendation: OutfitRecommendationBody


class OutfitRecommendationRequest(BaseModel):
    years: int = Field(3, ge=1, le=5)
    aggregation: Literal["weighted", "simple"] = "weighted"
    locale: str = "ko-KR"

