from __future__ import annotations

import logging
from datetime import date
from typing import Any

import requests

from app.core.cache import cached_json
from app.core.config import settings

logger = logging.getLogger(__name__)


class FrankfurterClient:
    """Fetch exchange rates from Frankfurter API (ECB reference rates)."""

    def __init__(self, session: requests.Session | None = None) -> None:
        self.base_url = settings.frankfurter_api_base_url
        self.timeout = settings.frankfurter_timeout_sec
        self.session = session or requests.Session()

    def fetch_latest(
        self, base: str, symbols: list[str] | None = None
    ) -> dict[str, Any] | None:
        """
        Fetch latest exchange rates.

        Args:
            base: Base currency code (ISO 4217, e.g., "USD", "EUR")
            symbols: List of target currency codes. If None, returns all available currencies.

        Returns:
            {
                "date": "YYYY-MM-DD",
                "base": "USD",
                "rates": {"KRW": 1385.12, "JPY": 154.4},
                "source": "ECB via Frankfurter"
            } or None if error
        """
        symbols_param = ",".join(symbols) if symbols else None
        cache_key = self._cache_key_latest(base, symbols_param)

        def loader() -> dict[str, Any] | None:
            params = {"base": base.upper()}
            if symbols_param:
                params["symbols"] = symbols_param

            try:
                resp = self.session.get(
                    f"{self.base_url}/v1/latest",
                    params=params,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()

                return {
                    "as_of": data.get("date"),
                    "base": data.get("base", base.upper()),
                    "rates": data.get("rates", {}),
                    "source": "ECB via Frankfurter",
                }
            except requests.RequestException as exc:
                logger.warning("Failed to fetch latest rates from Frankfurter: %s", exc)
                return None
            except (ValueError, KeyError) as exc:
                logger.warning("Invalid response from Frankfurter: %s", exc)
                return None

        result = cached_json(cache_key, settings.fx_cache_ttl_latest_sec, loader)
        return result

    def fetch_historical(
        self, target_date: date, base: str, symbols: list[str] | None = None
    ) -> dict[str, Any] | None:
        """
        Fetch historical exchange rates for a specific date.

        Args:
            target_date: Date to fetch rates for (YYYY-MM-DD)
            base: Base currency code (ISO 4217)
            symbols: List of target currency codes. If None, returns all available currencies.

        Returns:
            Same format as fetch_latest() or None if error
        """
        date_str = target_date.strftime("%Y-%m-%d")
        symbols_param = ",".join(symbols) if symbols else None
        cache_key = self._cache_key_historical(date_str, base, symbols_param)

        def loader() -> dict[str, Any] | None:
            params = {"base": base.upper()}
            if symbols_param:
                params["symbols"] = symbols_param

            try:
                resp = self.session.get(
                    f"{self.base_url}/v1/{date_str}",
                    params=params,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()

                return {
                    "as_of": data.get("date"),
                    "base": data.get("base", base.upper()),
                    "rates": data.get("rates", {}),
                    "source": "ECB via Frankfurter",
                }
            except requests.RequestException as exc:
                logger.warning(
                    "Failed to fetch historical rates from Frankfurter for %s: %s",
                    date_str,
                    exc,
                )
                return None
            except (ValueError, KeyError) as exc:
                logger.warning("Invalid response from Frankfurter: %s", exc)
                return None

        result = cached_json(cache_key, settings.fx_cache_ttl_historical_sec, loader)
        return result

    def get_currencies(self) -> dict[str, str] | None:
        """
        Get list of supported currency codes and names.

        Returns:
            {"USD": "United States Dollar", "KRW": "South Korean Won", ...} or None if error
        """
        cache_key = "fx:currencies"

        def loader() -> dict[str, str] | None:
            try:
                resp = self.session.get(
                    f"{self.base_url}/v1/currencies",
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                # Frankfurter returns currencies directly as a dict: {"USD": "United States Dollar", ...}
                return data if isinstance(data, dict) else {}
            except requests.RequestException as exc:
                logger.warning("Failed to fetch currencies from Frankfurter: %s", exc)
                return None
            except (ValueError, KeyError) as exc:
                logger.warning("Invalid currencies response from Frankfurter: %s", exc)
                return None

        result = cached_json(cache_key, 60 * 60 * 24, loader)  # 24 hours cache
        return result

    def _cache_key_latest(self, base: str, symbols: str | None) -> str:
        if symbols:
            return f"fx:latest:{base.upper()}:{symbols.upper()}"
        return f"fx:latest:{base.upper()}:all"

    def _cache_key_historical(self, date_str: str, base: str, symbols: str | None) -> str:
        if symbols:
            return f"fx:date:{date_str}:{base.upper()}:{symbols.upper()}"
        return f"fx:date:{date_str}:{base.upper()}:all"

