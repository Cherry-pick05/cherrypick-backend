from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


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

