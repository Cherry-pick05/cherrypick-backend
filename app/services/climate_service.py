from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, timedelta
from statistics import mean
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.deps import DeviceAuthContext
from app.schemas.climate import (
    ClimateMonthlyBreakdown,
    ClimatePeriod,
    ClimatePointMeta,
    ClimateRecentResponse,
    ClimateSummary,
    InputSummary,
)
from app.services.airlabs_airport_client import AirLabsAirportClient, AirportCoordinates
from app.services.meteostat_client import MeteostatClient
from app.services.trip_service import TripService


class TripClimateService:
    def __init__(
        self,
        db: Session,
        auth: DeviceAuthContext,
        *,
        airlabs_client: AirLabsAirportClient | None = None,
        meteostat_client: MeteostatClient | None = None,
    ) -> None:
        self.trip_service = TripService(db, auth)
        self.airlabs_client = airlabs_client or AirLabsAirportClient()
        self.meteostat_client = meteostat_client or MeteostatClient()

    def get_trip_climate(self, trip_id: int, years: int, agg: str) -> ClimateRecentResponse:
        if years < 1 or years > 5:
            raise HTTPException(status_code=400, detail="invalid_years_range")
        if agg not in {"weighted", "simple"}:
            raise HTTPException(status_code=400, detail="invalid_aggregation")

        trip = self.trip_service.get_trip_detail(trip_id)
        if not trip.start_date or not trip.end_date:
            raise HTTPException(status_code=409, detail="trip_duration_required")
        if not trip.itinerary.to_airport:
            raise HTTPException(status_code=422, detail="destination_missing")

        coords = self._resolve_airport_coordinates(trip.itinerary.to_airport)
        if not coords:
            raise HTTPException(status_code=422, detail="destination_coordinates_unavailable")

        months_meta = self._extract_months(trip.start_date, trip.end_date)

        normals = self._fetch_point_normals(coords)
        breakdown = self._build_breakdown(normals, months_meta.months)
        if not breakdown:
            raise HTTPException(status_code=503, detail="meteostat_no_data")

        summary = _aggregate_breakdown(breakdown, months_meta, agg)
        basis = _infer_normals_basis(normals)

        return ClimateRecentResponse(
            trip_id=trip.trip_id,
            input=InputSummary(
                latitude=coords.latitude,
                longitude=coords.longitude,
                start=str(trip.start_date),
                end=str(trip.end_date),
                years=years,
                aggregation=agg,
            ),
            point=ClimatePointMeta(
                latitude=coords.latitude,
                longitude=coords.longitude,
                altitude_m=coords.altitude_m,
            ),
            period=months_meta,
            basis=basis,
            recent_stats=summary,
            months_breakdown=breakdown,
            used_years=_extract_used_years(normals),
            degraded=False,
            source=[f"Meteostat Point Normals ({coords.latitude:.2f},{coords.longitude:.2f})"],
            generated_at=datetime.now(tz=UTC),
        )

    def _resolve_airport_coordinates(self, iata_code: str) -> AirportCoordinates | None:
        return self.airlabs_client.get_coordinates(iata_code)

    def _fetch_point_normals(
        self,
        coords: AirportCoordinates,
    ) -> list[dict[str, Any]]:
        try:
            return self.meteostat_client.point_normals(
                coords.latitude,
                coords.longitude,
                alt=coords.altitude_m,
            )
        except RuntimeError as exc:
            if "meteostat_api_key_missing" in str(exc):
                raise HTTPException(status_code=503, detail="meteostat_api_key_missing") from exc
            raise HTTPException(status_code=503, detail="meteostat_unavailable") from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=503, detail="meteostat_unavailable") from exc

    def _build_breakdown(self, normals: list[dict[str, Any]], target_months: list[int]):
        month_map = {int(entry.get("month")): entry for entry in normals if entry.get("month") is not None}
        breakdown: list[ClimateMonthlyBreakdown] = []
        for month in target_months:
            entry = month_map.get(month)
            if not entry:
                continue
            breakdown.append(
                ClimateMonthlyBreakdown(
                    month=month,
                    t_mean_c=_safe_float(entry.get("tavg")),
                    t_min_c=_safe_float(entry.get("tmin")),
                    t_max_c=_safe_float(entry.get("tmax")),
                    precip_sum_mm=_safe_float(entry.get("prcp")),
                )
            )
        return breakdown

    def _extract_months(self, start: date, end: date) -> ClimatePeriod:
        if end < start:
            raise HTTPException(status_code=400, detail="invalid_date_range")
        months: list[int] = []
        days_per_month: dict[int, int] = {}
        cursor = start
        while cursor <= end:
            month = cursor.month
            if month not in months:
                months.append(month)
            month_end_day = calendar.monthrange(cursor.year, month)[1]
            segment_end = date(cursor.year, month, month_end_day)
            if segment_end > end:
                segment_end = end
            days = (segment_end - cursor).days + 1
            days_per_month[month] = days_per_month.get(month, 0) + days
            cursor = segment_end + timedelta(days=1)
        total_days = sum(days_per_month.values())
        return ClimatePeriod(months=months, days_per_month=days_per_month, total_days=total_days)


def _aggregate_breakdown(breakdown: list[ClimateMonthlyBreakdown], period: ClimatePeriod, agg: str) -> ClimateSummary:
    if not breakdown:
        raise HTTPException(status_code=503, detail="meteostat_no_data")

    weighted = agg == "weighted"
    weights = period.days_per_month

    def reducer(field: str, *, sum_mode: bool = False) -> float | None:
        values = [(getattr(item, field), item.month) for item in breakdown if getattr(item, field) is not None]
        if not values:
            return None
        if weighted:
            total_weight = sum(weights.get(month, 0) for _, month in values)
            if total_weight == 0:
                return None
            acc = 0.0
            for value, month in values:
                weight = weights.get(month, 0)
                if sum_mode:
                    month_days = calendar.monthrange(2000, month)[1]
                    weight = weight / month_days if month_days else 0
                acc += float(value) * weight
            return acc / total_weight if not sum_mode else acc
        return mean(float(value) for value, _ in values)

    return ClimateSummary(
        t_mean_c=reducer("t_mean_c"),
        t_min_c=reducer("t_min_c"),
        t_max_c=reducer("t_max_c"),
        precip_sum_mm=reducer("precip_sum_mm", sum_mode=True),
    )


def _infer_normals_basis(normals: list[dict[str, Any]]) -> str:
    if normals:
        first = normals[0]
        start = first.get("start")
        end = first.get("end")
        if start and end:
            return f"point-normals({start}-{end})"
    return "point-normals(default)"


def _extract_used_years(normals: list[dict[str, Any]]) -> list[int]:
    if not normals:
        return []
    first = normals[0]
    start = _safe_int(first.get("start"))
    end = _safe_int(first.get("end"))
    years = []
    if start is not None:
        years.append(start)
    if end is not None and end != start:
        years.append(end)
    return years


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = ["TripClimateService"]

