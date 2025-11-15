"""Shared helpers for airline regulation scrapers."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from bs4 import BeautifulSoup

from app.services.regulation_normalizer import RegulationNormalizer
from app.services.regulation_scraper import PageRequest, RegulationScraper
from app.services.regulation_sources import get_source


logger = logging.getLogger(__name__)


class AirlineScraper(RegulationScraper):
    """Base scraper for airline baggage rules."""

    airline_code: str

    def __init__(
        self,
        airline_code: str,
        *,
        normalizer: RegulationNormalizer | None = None,
        source_config: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.airline_code = airline_code.upper()
        config = source_config or get_source("airline", self.airline_code)
        if not config:
            raise ValueError(f"알 수 없는 항공사 코드입니다: {airline_code}")

        base_url = config.get("urls", {}).get("landing") or "https://www.koreanair.com"
        super().__init__(base_url=base_url, **kwargs)

        self.config = config
        self.normalizer = normalizer or RegulationNormalizer()

    # ------------------------------------------------------------------
    def _get_url(self, key: str) -> str:
        urls = self.config.get("urls", {})
        if key not in urls:
            raise KeyError(f"구성에서 '{key}' URL을 찾을 수 없습니다")
        return urls[key]

    def get_section(self, key: str, *, requires_js: bool = False, wait_selector: str | None = None) -> BeautifulSoup:
        url = self._get_url(key)
        request = PageRequest(url=url, requires_js=requires_js, wait_selector=wait_selector)
        return self.get_soup(request)

    # ------------------------------------------------------------------
    @staticmethod
    def infer_route_type(text: str) -> Optional[str]:
        lowered = text.lower()
        if "국내선" in lowered or "domestic" in lowered:
            return "domestic"
        if "국제선" in lowered or "international" in lowered:
            return "international"
        return None

    @staticmethod
    def infer_cabin_class(text: str) -> Optional[str]:
        lowered = text.lower()
        if any(keyword in lowered for keyword in ["이코노미", "economy", "일반석"]):
            return "economy"
        if any(keyword in lowered for keyword in ["프레스티지", "prestige"]):
            return "prestige"
        if any(keyword in lowered for keyword in ["비즈니스", "business"]):
            return "business"
        if any(keyword in lowered for keyword in ["일등석", "first"]):
            return "first"
        return None

