from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict

from app.db.models.trip import Trip
from app.schemas.recommendation import (
    ExchangeRateInfo,
    TripRecommendationResponse,
    WeatherInfo,
)
from app.services.exchange_client import KoreaEximClient
from app.services.recommendation_llm import (
    RecommendationPromptContext,
    generate_recommendation_sections,
)
from app.services.weather_client import WeatherClient


logger = logging.getLogger(__name__)

COUNTRY_TO_CURRENCY: Dict[str, str] = {
    "KR": "KRW",
    "US": "USD",
    "JP": "JPY",
    "CN": "CNY",
    "TW": "TWD",
    "HK": "HKD",
    "GB": "GBP",
    "DE": "EUR",
    "FR": "EUR",
    "ES": "EUR",
    "IT": "EUR",
    "VN": "VND",
    "TH": "THB",
    "SG": "SGD",
    "AU": "AUD",
    "NZ": "NZD",
    "CA": "CAD",
}


@dataclass(slots=True)
class RecommendationContext:
    trip: Trip
    currency_code: str
    travel_window: str | None


class RecommendationService:
    def __init__(self) -> None:
        self.weather_client = WeatherClient()
        self.fx_client = KoreaEximClient()

    def build(self, trip: Trip) -> TripRecommendationResponse:
        currency_code = self._currency_for_country(trip.country_code2)
        travel_window = self._window_label(trip.start_date, trip.end_date)
        weather_raw = self.weather_client.fetch_current(trip.city, trip.country_code2)
        exchange_raw = self.fx_client.fetch_rate(currency_code)
        sections = generate_recommendation_sections(
            RecommendationPromptContext(
                city=trip.city,
                country_code=trip.country_code2,
                travel_window=travel_window,
                weather_summary=(weather_raw or {}).get("summary"),
                temperature_c=(weather_raw or {}).get("temperature_c"),
                currency_code=currency_code,
                exchange_rate=(exchange_raw or {}).get("rate"),
            )
        )

        return TripRecommendationResponse(
            trip_id=trip.trip_id,
            city=trip.city,
            country_code=trip.country_code2,
            weather=self._build_weather(weather_raw),
            exchange_rate=self._build_exchange(exchange_raw),
            popular_items=sections.get("popular_items", []),
            outfit_tip=sections.get("outfit_tip"),
            shopping_guide=sections.get("shopping_guide"),
        )

    def _build_weather(self, data: Dict[str, Any] | None) -> WeatherInfo | None:
        if not data:
            return None
        return WeatherInfo(
            summary=data.get("summary"),
            temperature_c=data.get("temperature_c"),
            feels_like_c=data.get("feels_like_c"),
            humidity=data.get("humidity"),
            icon=data.get("icon"),
        )

    def _build_exchange(self, data: Dict[str, Any] | None) -> ExchangeRateInfo | None:
        if not data:
            return None
        return ExchangeRateInfo(
            currency_code=data.get("currency_code"),
            currency_name=data.get("currency_name"),
            base_currency=data.get("base", "KRW"),
            rate=data.get("rate"),
            last_updated=data.get("date"),
        )

    def _currency_for_country(self, country_code: str | None) -> str:
        if not country_code:
            return "USD"
        upper = country_code.upper()
        return COUNTRY_TO_CURRENCY.get(upper, "USD")

    def _window_label(self, start: date | None, end: date | None) -> str | None:
        if start and end:
            return f"{start.isoformat()} ~ {end.isoformat()}"
        if start:
            return f"{start.isoformat()} 출발"
        if end:
            return f"{end.isoformat()} 귀국"
        return None

