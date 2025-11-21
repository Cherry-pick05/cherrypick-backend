from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List

import requests

from app.core.config import settings


logger = logging.getLogger(__name__)


class KoreaEximClient:
    """Fetch exchange rates from the Korea Eximbank open API."""

    def __init__(self) -> None:
        self.base_url = settings.koreaexim_api_base_url

    def fetch_rate(self, currency_code: str, *, target_date: date | None = None) -> Dict[str, Any] | None:
        if not settings.koreaexim_api_key:
            logger.debug("KoreaExim API key missing, skipping FX lookup")
            return None
        if not currency_code:
            return None
        searchdate = (target_date or date.today()).strftime("%Y%m%d")
        params = {
            "authkey": settings.koreaexim_api_key,
            "searchdate": searchdate,
            "data": settings.koreaexim_default_data,
        }
        try:
            resp = requests.get(
                self.base_url,
                params=params,
                timeout=settings.exchange_timeout_sec,
            )
            resp.raise_for_status()
            payload = resp.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Failed to fetch exchange rate: %s", exc)
            return None

        if not isinstance(payload, list):
            logger.debug("Unexpected KoreaExim payload: %s", payload)
            return None

        upper_code = currency_code.upper()
        entry = self._match_currency(payload, upper_code)
        if not entry:
            logger.debug("Currency %s not found in KoreaExim response", upper_code)
            return None
        rate_str = entry.get("deal_bas_r")
        try:
            rate = float(rate_str.replace(",", "")) if rate_str else None
        except (ValueError, AttributeError):
            rate = None
        return {
            "currency_code": upper_code,
            "currency_name": entry.get("cur_nm"),
            "rate": rate,
            "base": "KRW",
            "date": target_date or date.today(),
        }

    def _match_currency(self, rows: List[Dict[str, Any]], code: str) -> Dict[str, Any] | None:
        for row in rows:
            cur_unit = (row.get("cur_unit") or "").upper()
            if cur_unit.startswith(code):
                return row
        return None

