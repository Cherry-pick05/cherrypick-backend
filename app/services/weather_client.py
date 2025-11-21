from __future__ import annotations

import logging
from typing import Any, Dict

import requests

from app.core.config import settings


logger = logging.getLogger(__name__)


class WeatherClient:
    """Lightweight wrapper around OpenWeather current weather API."""

    def __init__(self) -> None:
        self.base_url = settings.weather_api_base_url.rstrip("/")

    def fetch_current(self, city: str | None, country_code: str | None) -> Dict[str, Any] | None:
        """Return normalized weather info or None if unavailable."""
        if not settings.weather_api_key:
            logger.debug("Weather API key missing, skipping weather lookup")
            return None
        query = city or country_code
        if not query:
            return None
        if city and country_code:
            query = f"{city},{country_code}"
        params = {
            "q": query,
            "appid": settings.weather_api_key,
            "units": settings.weather_units,
            "lang": settings.weather_lang,
        }
        try:
            resp = requests.get(
                f"{self.base_url}/weather",
                params=params,
                timeout=settings.weather_timeout_sec,
            )
            resp.raise_for_status()
            payload = resp.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Failed to fetch weather data: %s", exc)
            return None

        weather_entries = payload.get("weather") or []
        weather_entry = weather_entries[0] if weather_entries else {}
        main_block = payload.get("main") or {}

        return {
            "summary": weather_entry.get("description"),
            "icon": weather_entry.get("icon"),
            "temperature_c": main_block.get("temp"),
            "feels_like_c": main_block.get("feels_like"),
            "humidity": main_block.get("humidity"),
        }

