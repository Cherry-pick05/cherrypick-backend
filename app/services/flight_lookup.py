from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

import requests

from app.core.config import settings
from app.schemas.flight import FlightLookupResponse, FlightEndpoint, FlightSegmentSuggestion
from app.services.airport_lookup import get_airport_info


class FlightLookupError(Exception):
    """Raised when the flight lookup API fails."""

    def __init__(self, code: str, status_code: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class FlightLookupService:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = api_key or settings.airlabs_api_key
        self.base_url = (base_url or settings.airlabs_api_base_url).rstrip("/")
        self.timeout = settings.airlabs_timeout_sec
        self.session = session or requests.Session()

    def lookup(self, flight_code: str, code_type: Literal["iata", "icao"]) -> FlightLookupResponse:
        if not self.api_key:
            raise FlightLookupError("airlabs_api_key_missing", status_code=503)

        params: dict[str, Any] = {"api_key": self.api_key}
        key = "flight_iata" if code_type == "iata" else "flight_icao"
        params[key] = flight_code.strip().upper()

        try:
            response = self.session.get(
                f"{self.base_url}/flight",
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise FlightLookupError("airlabs_request_failed", status_code=502) from exc
        except ValueError as exc:
            raise FlightLookupError("airlabs_invalid_response", status_code=502) from exc

        data = payload.get("response")
        if not data:
            raise FlightLookupError("flight_not_found", status_code=404)

        return self._build_response(data)

    def _build_endpoint(self, data: dict[str, Any], prefix: str) -> FlightEndpoint:
        iata = self._safe_upper(data.get(f"{prefix}_iata"))
        icao = self._safe_upper(data.get(f"{prefix}_icao"))
        info = get_airport_info(iata) if iata else None
        return FlightEndpoint(
            airport_iata=iata,
            airport_icao=icao or (info.get("iata_code") if info else None),
            airport_name=(info.get("name_en") if info else data.get(f"{prefix}_name")),
            city=info.get("city_en") if info else data.get(f"{prefix}_city"),
            country=info.get("country") if info else data.get(f"{prefix}_country"),
            terminal=data.get(f"{prefix}_terminal"),
            gate=data.get(f"{prefix}_gate"),
            baggage=data.get(f"{prefix}_baggage"),
            scheduled_time_utc=self._to_datetime(data.get(f"{prefix}_time_ts"), data.get(f"{prefix}_time_utc")),
            estimated_time_utc=self._to_datetime(
                data.get(f"{prefix}_estimated_ts"), data.get(f"{prefix}_estimated")
            ),
            actual_time_utc=self._to_datetime(data.get(f"{prefix}_actual_ts"), data.get(f"{prefix}_actual")),
            scheduled_time_local=data.get(f"{prefix}_time"),
            estimated_time_local=data.get(f"{prefix}_estimated"),
            actual_time_local=data.get(f"{prefix}_actual"),
        )

    def _build_leg(self, dep: str | None, arr: str | None) -> str | None:
        if dep and arr:
            return f"{dep}-{arr}"
        return None

    def _safe_upper(self, value: Any) -> str | None:
        if not value:
            return None
        if isinstance(value, str):
            value = value.strip()
            return value.upper() if value else None
        return None

    def _to_datetime(self, ts: Any, fallback_str: Any) -> datetime | None:
        if isinstance(ts, (int, float)):
            try:
                return datetime.fromtimestamp(int(ts), tz=UTC)
            except (ValueError, OSError):
                pass
        if isinstance(fallback_str, str) and fallback_str:
            try:
                return datetime.strptime(fallback_str, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
            except ValueError:
                return None
        return None

    def _build_response(self, data: dict[str, Any]) -> FlightLookupResponse:
        dep_endpoint = self._endpoint_with_metadata(data, "dep")
        arr_endpoint = self._endpoint_with_metadata(data, "arr")
        return FlightLookupResponse(
            flight_iata=self._safe_upper(data.get("flight_iata")),
            flight_icao=self._safe_upper(data.get("flight_icao")),
            flight_number=data.get("flight_number"),
            airline_iata=self._safe_upper(data.get("airline_iata")),
            airline_icao=self._safe_upper(data.get("airline_icao")),
            airline_name=data.get("airline_name"),
            status=data.get("status"),
            duration_minutes=data.get("duration"),
            aircraft_model=data.get("model"),
            aircraft_icao=self._safe_upper(data.get("aircraft_icao")),
            registration_number=data.get("reg_number"),
            departure=dep_endpoint,
            arrival=arr_endpoint,
            segment_hint=self._build_segment_hint(dep_endpoint, arr_endpoint),
        )

    def _endpoint_with_metadata(self, data: dict[str, Any], prefix: str) -> FlightEndpoint:
        base = self._build_endpoint(data, prefix)
        if base.airport_iata:
            info = get_airport_info(base.airport_iata)
            if info:
                base.airport_name = base.airport_name or info.get("name_en")
                base.city = base.city or info.get("city_en")
                base.country = base.country or info.get("country")
        return base

    def _build_segment_hint(
        self,
        departure: FlightEndpoint,
        arrival: FlightEndpoint,
    ) -> FlightSegmentSuggestion | None:
        leg = self._build_leg(departure.airport_iata, arrival.airport_iata)
        if not leg:
            return None
        return FlightSegmentSuggestion(
            leg=leg,
            departure_iata=departure.airport_iata,
            arrival_iata=arrival.airport_iata,
            departure_time_utc=departure.scheduled_time_utc or departure.estimated_time_utc,
            arrival_time_utc=arrival.scheduled_time_utc or arrival.estimated_time_utc,
        )


