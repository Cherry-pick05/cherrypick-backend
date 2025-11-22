from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.config import settings
from app.services.flight_lookup import FlightLookupError, FlightLookupService


class DummyResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:  # pragma: no cover - no-op
        return None

    def json(self) -> dict:
        return self._payload


class DummySession:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.captured = None

    def get(self, url: str, params: dict, timeout: float) -> DummyResponse:  # pragma: no cover
        self.captured = {"url": url, "params": params, "timeout": timeout}
        return DummyResponse(self.payload)


def test_flight_lookup_happy_path(monkeypatch):
    payload = {
        "response": {
            "flight_iata": "AA6",
            "flight_icao": "AAL6",
            "flight_number": "6",
            "airline_iata": "AA",
            "airline_icao": "AAL",
            "airline_name": "American Airlines",
            "dep_iata": "HNL",
            "dep_icao": "PHNL",
            "dep_time": "2025-11-21 18:39",
            "dep_time_ts": 1763786340,
            "dep_time_utc": "2025-11-22 04:39",
            "dep_terminal": "2",
            "dep_gate": "C1",
            "arr_iata": "DFW",
            "arr_icao": "KDFW",
            "arr_time": "2025-11-22 05:53",
            "arr_time_ts": 1763812380,
            "arr_time_utc": "2025-11-22 11:53",
            "arr_terminal": "A",
            "arr_gate": "A34",
            "duration": 434,
            "status": "en-route",
            "model": "Boeing 787-8",
            "aircraft_icao": "B788",
            "reg_number": "N803AL",
        }
    }
    session = DummySession(payload)

    # Stub airport lookup to avoid hitting DB/redis
    monkeypatch.setattr(
        "app.services.flight_lookup.get_airport_info",
        lambda code: {"name_en": f"Airport {code}", "city_en": "City", "country": "US"}
        if code
        else None,
    )

    service = FlightLookupService(api_key="dummy", session=session)
    result = service.lookup("AA6", "iata")

    assert result.flight_iata == "AA6"
    assert result.airline_iata == "AA"
    assert result.departure.airport_iata == "HNL"
    assert result.arrival.airport_iata == "DFW"
    assert result.departure.scheduled_time_utc == datetime(2025, 11, 22, 4, 39, tzinfo=UTC)
    assert result.segment_hint is not None
    assert result.segment_hint.leg == "HNL-DFW"


def test_flight_lookup_errors_on_missing_key():
    service = FlightLookupService(api_key=None)
    with pytest.raises(FlightLookupError) as exc:
        service.lookup("AA6", "iata")
    assert exc.value.code == "airlabs_api_key_missing"
    assert exc.value.status_code == 503

