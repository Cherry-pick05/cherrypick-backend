from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.deps import DeviceAuthContext
from app.schemas.climate import ClimateRecentResponse
from app.schemas.recommendation import (
    OutfitRecommendationBody,
    OutfitRecommendationRequest,
    OutfitRecommendationResponse,
)
from app.services.airport_lookup import get_airport_info
from app.services.outfit_llm import generate_outfit_recommendation
from app.services.trip_service import TripService
from app.services.climate_service import TripClimateService


@dataclass(slots=True)
class OutfitContext:
    locale: str
    years: int
    aggregation: str


class OutfitRecommendationService:
    def __init__(self, db: Session, auth: DeviceAuthContext) -> None:
        self.trip_service = TripService(db, auth)
        self.climate_service = TripClimateService(db, auth)

    def recommend(self, trip_id: int, payload: OutfitRecommendationRequest) -> OutfitRecommendationResponse:
        trip = self.trip_service.get_trip_detail(trip_id)
        climate = self.climate_service.get_trip_climate(trip_id, payload.years, payload.aggregation)

        llm_input = self._build_llm_input(trip, climate, payload.locale)
        raw_output = generate_outfit_recommendation(llm_input)
        recommendation = self._parse_output(raw_output)

        return OutfitRecommendationResponse(
            trip_id=trip.trip_id,
            climate=climate,
            recommendation=recommendation,
        )

    def _build_llm_input(self, trip, climate: ClimateRecentResponse, locale: str) -> Dict[str, Any]:
        city, country = self._resolve_region(trip)
        start = trip.start_date
        end = trip.end_date
        if not start or not end:
            raise HTTPException(status_code=409, detail="trip_duration_required")
        duration_days = (end - start).days + 1
        season = _season_of(start)
        summary = climate.recent_stats
        temp_range = {
            "min": summary.t_min_c,
            "max": summary.t_max_c,
            "mean": summary.t_mean_c,
        }

        daily_signal = []
        if summary.t_min_c is not None or summary.t_max_c is not None:
            daily_signal.append(
                {
                    "date": str(start),
                    "min_c": summary.t_min_c,
                    "max_c": summary.t_max_c,
                    "pop": None,
                    "uv_index": None,
                    "condition": "Historical normals",
                }
            )

        return {
            "locale": locale,
            "region": {"city": city, "country": country},
            "date_range": {"start": str(start), "days": duration_days},
            "basis": "historical_normals",
            "season": season,
            "daily_signal": daily_signal,
            "climate_summary": {
                "t_mean_c": summary.t_mean_c,
                "t_min_c": summary.t_min_c,
                "t_max_c": summary.t_max_c,
                "precip_sum_mm": summary.precip_sum_mm,
            },
            "home_region": {"city": "Seoul", "country": "KR", "seasonal_hint": "서울은 계절별 일교차가 커요"},
            "user_profile": {"cold_sensitive": False, "baggage_pref": "either"},
            "facts": {
                "basis": "historical_normals",
                "date_span": [str(start), str(end)],
                "temp_c": temp_range,
                "precip_mm": summary.precip_sum_mm,
                "pop": None,
                "condition": "Historical normals",
            },
        }

    def _parse_output(self, data: Dict[str, Any]) -> OutfitRecommendationBody:
        try:
            return OutfitRecommendationBody.model_validate(data)
        except Exception as exc:
            raise HTTPException(status_code=502, detail="llm_invalid_payload") from exc

    def _resolve_region(self, trip) -> tuple[str, str]:
        airport_code = trip.itinerary.to_airport
        info = get_airport_info(airport_code) if airport_code else None
        city = info.get("city_en") if info else airport_code or "Unknown"
        country = info.get("country_code") if info else trip.country_to or "Unknown"
        return city, country


def _season_of(day: date) -> str:
    month = day.month
    if month in {12, 1, 2}:
        return "winter"
    if month in {3, 4, 5}:
        return "spring"
    if month in {6, 7, 8}:
        return "summer"
    return "autumn"


__all__ = ["OutfitRecommendationService"]

