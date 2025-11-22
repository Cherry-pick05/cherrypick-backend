from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests

from app.core.cache import cached_json
from app.core.config import settings
from app.services.airport_lookup import get_airport_info


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AirportCoordinates:
    iata_code: str
    latitude: float
    longitude: float
    name: str | None = None
    altitude_m: float | None = None


class AirLabsAirportClient:
    """Resolve airport coordinates via AirLabs and cache the results."""

    def __init__(self, *, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self.base_url = settings.airlabs_api_base_url.rstrip("/")
        self.timeout = settings.airlabs_timeout_sec
        self.api_key = settings.airlabs_api_key

    def get_coordinates(self, iata_code: str) -> AirportCoordinates | None:
        code = (iata_code or "").strip().upper()
        if len(code) != 3:
            return None

        cache_key = f"airlabs:airport:{code}"

        def loader() -> dict[str, Any] | None:
            if not self.api_key:
                logger.debug("AirLabs API key missing, falling back to local directory")
                return None
            params = {
                "api_key": self.api_key,
                "iata_code": code,
                "_fields": "name,iata_code,icao_code,lat,lng",
            }
            try:
                resp = self.session.get(
                    f"{self.base_url}/airports",
                    params=params,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                payload = resp.json()
            except (requests.RequestException, ValueError) as exc:
                logger.warning("AirLabs airport lookup failed: %s", exc)
                return None

            data = payload.get("response")
            if isinstance(data, list):
                data = data[0] if data else None
            return data

        cached = cached_json(cache_key, ttl_seconds=60 * 60 * 24 * 7, loader=loader)  # 7 days
        if cached:
            lat = cached.get("lat")
            lng = cached.get("lng")
            if lat is not None and lng is not None:
                return AirportCoordinates(
                    iata_code=code,
                    latitude=float(lat),
                    longitude=float(lng),
                    name=cached.get("name"),
                    altitude_m=_safe_float(cached.get("alt")),
                )

        # fallback to local airport directory / airportsdata dataset
        info = get_airport_info(code)
        if not info:
            return None
        lat = info.get("latitude") or info.get("lat")
        lng = info.get("longitude") or info.get("lon") or info.get("lng")
        if lat is None or lng is None:
            return None
        return AirportCoordinates(
            iata_code=code,
            latitude=float(lat),
            longitude=float(lng),
            name=info.get("name_en"),
            altitude_m=_safe_float(info.get("elevation") or info.get("alt")),
        )


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["AirLabsAirportClient", "AirportCoordinates"]

