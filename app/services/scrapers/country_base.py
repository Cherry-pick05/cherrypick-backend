"""Shared helpers for country security/customs scrapers."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from bs4 import BeautifulSoup

from app.services.regulation_normalizer import RegulationNormalizer
from app.services.regulation_scraper import PageRequest, RegulationScraper
from app.services.regulation_sources import get_source


logger = logging.getLogger(__name__)


class CountryScraper(RegulationScraper):
    """Base scraper for country-level security and customs rules."""

    country_code: str

    def __init__(
        self,
        country_code: str,
        *,
        normalizer: RegulationNormalizer | None = None,
        source_config: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.country_code = country_code.upper()
        config = source_config or get_source("country", self.country_code)
        if not config:
            raise ValueError(f"알 수 없는 국가 코드입니다: {country_code}")

        base_url = config.get("urls", {}).get("landing") or config.get("urls", {}).get("security") or "https://example.com"
        super().__init__(base_url=base_url, **kwargs)

        self.config = config
        self.normalizer = normalizer or RegulationNormalizer()

    def _get_url(self, key: str) -> str:
        urls = self.config.get("urls", {})
        if key not in urls:
            raise KeyError(f"구성에서 '{key}' URL을 찾을 수 없습니다")
        return urls[key]

    def get_section(self, key: str, *, requires_js: bool = False, wait_selector: str | None = None) -> BeautifulSoup:
        url = self._get_url(key)
        request = PageRequest(url=url, requires_js=requires_js, wait_selector=wait_selector)
        return self.get_soup(request)

