from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import requests

from app.core.cache import cached_json
from app.core.config import settings


logger = logging.getLogger(__name__)


class MeteostatClient:
    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self.base_url = settings.meteostat_base_url.rstrip("/")
        self.timeout = settings.meteostat_timeout_sec
        self.api_key = settings.meteostat_api_key
        parsed = urlparse(self.base_url)
        self.host_header = parsed.netloc

    def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("meteostat_api_key_missing")

        headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.host_header,
        }
        try:
            resp = self.session.get(
                f"{self.base_url}{path}",
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            payload = resp.json()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response else "?"
            logger.warning("Meteostat HTTP error %s: %s", status, exc)
            raise
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Meteostat request failed: %s", exc)
            raise
        return payload

    def point_normals(
        self,
        lat: float,
        lon: float,
        *,
        alt: float | None = None,
        units: str = "metric",
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"lat": lat, "lon": lon, "units": units}
        if alt is not None:
            params["alt"] = round(alt)

        cache_key = f"meteostat:point:{lat:.3f}:{lon:.3f}:{params.get('alt','-')}:{units}"

        def loader() -> dict[str, Any]:
            return self._request("/point/normals", params)

        payload = cached_json(cache_key, ttl_seconds=60 * 60 * 24, loader=loader)
        data = payload.get("data") if isinstance(payload, dict) else None
        if not data:
            return []
        return data


__all__ = ["MeteostatClient"]

