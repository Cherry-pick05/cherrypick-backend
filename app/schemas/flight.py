from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, constr


class FlightLookupRequest(BaseModel):
    flight_code: constr(strip_whitespace=True, min_length=2, max_length=16)  # type: ignore[valid-type]
    code_type: Literal["iata", "icao"] = "iata"


class FlightEndpoint(BaseModel):
    airport_iata: str | None = None
    airport_icao: str | None = None
    airport_name: str | None = None
    city: str | None = None
    country: str | None = None
    terminal: str | None = None
    gate: str | None = None
    baggage: str | None = None
    scheduled_time_utc: datetime | None = None
    estimated_time_utc: datetime | None = None
    actual_time_utc: datetime | None = None
    scheduled_time_local: str | None = None
    estimated_time_local: str | None = None
    actual_time_local: str | None = None


class FlightSegmentSuggestion(BaseModel):
    leg: str | None = None
    departure_iata: str | None = None
    arrival_iata: str | None = None
    departure_time_utc: datetime | None = None
    arrival_time_utc: datetime | None = None


class FlightLookupResponse(BaseModel):
    flight_iata: str | None = None
    flight_icao: str | None = None
    flight_number: str | None = None
    airline_iata: str | None = None
    airline_icao: str | None = None
    airline_name: str | None = None
    status: str | None = None
    duration_minutes: int | None = None
    aircraft_model: str | None = None
    aircraft_icao: str | None = None
    registration_number: str | None = None
    departure: FlightEndpoint = Field(default_factory=FlightEndpoint)
    arrival: FlightEndpoint = Field(default_factory=FlightEndpoint)
    segment_hint: FlightSegmentSuggestion | None = None


