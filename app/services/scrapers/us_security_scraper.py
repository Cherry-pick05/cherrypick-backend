"""Scraper for United States security (TSA) and customs (CBP) regulations."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag

from app.services.scrapers.country_base import CountryScraper


logger = logging.getLogger(__name__)


class USSecurityScraper(CountryScraper):
    """Security and customs scraper for United States (US)."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("US", **kwargs)

    def scrape_country_regulations(self, country_code: str | None = None) -> List[Dict[str, Any]]:
        if country_code and country_code.upper() != self.country_code:
            raise ValueError(f"지원되지 않는 국가 코드입니다: {country_code}")

        rules: List[Dict[str, Any]] = []
        try:
            security_soup = self.get_section("security", requires_js=True, wait_selector="article")
            rules.extend(self._scrape_security(security_soup))
        except Exception as exc:  # pragma: no cover - network errors
            logger.error("미국 TSA 규정 스크래핑 실패", exc_info=exc)

        try:
            customs_soup = self.get_section("customs")
            rules.extend(self._scrape_customs(customs_soup))
        except Exception as exc:  # pragma: no cover - network errors
            logger.error("미국 CBP 규정 스크래핑 실패", exc_info=exc)

        return rules

    # ------------------------------------------------------------------
    def _scrape_security(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        rules: List[Dict[str, Any]] = []
        items = soup.select("article, div.search-result-item")
        if not items:
            items = soup.select("li")

        for item in items:
            text = self.clean_text(item.get_text(" "))
            if not text:
                continue

            rule = self._classify_security_text(text)
            if rule:
                rules.append(rule)

        return rules

    def _classify_security_text(self, text: str) -> Optional[Dict[str, Any]]:
        lowered = text.lower()
        constraints: Dict[str, Any] = {"description": text}
        severity = "warn"

        if "not allowed" in lowered or "prohibited" in lowered:
            severity = "block"
            constraints["allowed_in_cabin"] = False
            constraints["allowed_in_checked"] = False
        else:
            if "carry-on bag" in lowered or "cabin" in lowered:
                constraints["allowed_in_cabin"] = "allowed" in lowered or "yes" in lowered
            if "checked bag" in lowered:
                constraints["allowed_in_checked"] = "allowed" in lowered or "yes" in lowered

        if "liquid" in lowered:
            constraints.setdefault("item", "liquids")
            constraints.setdefault("max_container_ml", 100)
            constraints.setdefault("max_total_ml", 1000)
        elif "battery" in lowered:
            constraints.setdefault("item", "lithium_battery")
            constraints.setdefault("terminal_protection_required", True)

        return self.normalizer.build_rule(
            "security_check",
            constraints,
            severity=severity,
            notes=text[:200],
        )

    def _scrape_customs(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        rules: List[Dict[str, Any]] = []
        for section in soup.find_all(["section", "article", "div"]):
            heading = self._find_heading(section)
            list_node = section.find("ul")
            if not heading or not list_node:
                continue

            title = self.clean_text(heading.get_text(" "))
            items = [self.clean_text(li.get_text(" ")) for li in list_node.find_all("li")]
            if not items:
                continue

            severity = "warn" if any(keyword in item.lower() for keyword in ["must declare", "prohibited", "restricted"]) else "info"
            constraints: Dict[str, Any] = {
                "title": title,
                "items": items,
            }

            duty_info = self._extract_duty_limits(items)
            if duty_info:
                constraints.update(duty_info)

            rules.append(
                self.normalizer.build_rule(
                    "customs",
                    constraints,
                    severity=severity,
                    notes=title,
                )
            )

        return rules

    def _extract_duty_limits(self, items: List[str]) -> Dict[str, Any]:
        limits: Dict[str, Any] = {}
        for item in items:
            lowered = item.lower()
            numbers = self.extract_numbers(item)
            if "alcohol" in lowered and numbers:
                limits["alcohol_limit_l"] = self.normalizer.volume_to_liters(numbers[0], unit="l")
            if "tobacco" in lowered and numbers:
                limits["tobacco_limit_units"] = int(numbers[0])
            if "gift" in lowered and numbers:
                limits["duty_free_allowance_usd"] = numbers[0]
        return limits

    def _find_heading(self, section: Tag) -> Optional[Tag]:
        for level in ["h2", "h3", "h4"]:
            node = section.find(level)
            if node:
                return node
        return None

