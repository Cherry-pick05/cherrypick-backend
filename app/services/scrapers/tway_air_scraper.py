"""Scraper for T'way Air baggage regulations."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterable, List, Optional

from bs4 import BeautifulSoup, Tag

from app.services.scrapers.airline_base import AirlineScraper


logger = logging.getLogger(__name__)


class TwayAirScraper(AirlineScraper):
    """Scraper implementation for T'way Air (TW)."""

    PIECE_PATTERN = re.compile(r"(\d+)\s*(?:개|pcs?|피스)", re.IGNORECASE)
    WEIGHT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(kg|킬로|g|그램|lbs?)", re.IGNORECASE)
    DIM_PATTERN = re.compile(r"(\d+)\s*[x×]\s*(\d+)\s*[x×]\s*(\d+)")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("TW", **kwargs)

    def scrape_airline_regulations(self, airline_code: str | None = None) -> List[Dict[str, Any]]:
        if airline_code and airline_code.upper() != self.airline_code:
            raise ValueError(f"지원되지 않는 항공사 코드입니다: {airline_code}")

        rules: List[Dict[str, Any]] = []
        try:
            carry_on_soup = self.get_section("carry_on", requires_js=False)
            rules.extend(self._parse_section(carry_on_soup, category="carry_on", keywords=["기내", "cabin"]))
        except Exception as exc:  # pragma: no cover - network errors
            logger.error("티웨이 기내 수하물 스크래핑 실패", exc_info=exc)

        try:
            checked_soup = self.get_section("checked", requires_js=False)
            rules.extend(self._parse_section(checked_soup, category="checked", keywords=["위탁", "checked"]))
        except Exception as exc:  # pragma: no cover - network errors
            logger.error("티웨이 위탁 수하물 스크래핑 실패", exc_info=exc)

        try:
            dangerous_soup = self.get_section("dangerous_goods", requires_js=False)
            rules.extend(self._parse_dangerous_goods(dangerous_soup))
        except Exception as exc:  # pragma: no cover - network errors
            logger.error("티웨이 위험물 스크래핑 실패", exc_info=exc)

        return rules

    # ------------------------------------------------------------------
    def _parse_section(self, soup: BeautifulSoup, *, category: str, keywords: Iterable[str]) -> List[Dict[str, Any]]:
        rules: List[Dict[str, Any]] = []
        for block in soup.find_all(["section", "article", "div"]):
            heading_tag = self._find_heading(block)
            if not heading_tag:
                continue
            heading = self.clean_text(heading_tag.get_text(" "))
            if not self._matches_keywords(heading, keywords):
                continue

            text = self.clean_text(block.get_text(" "))
            constraints = self._infer_constraints(text, category)
            if not constraints:
                continue

            route_type = self.infer_route_type(text) or self.infer_route_type(heading)
            cabin_class = self.infer_cabin_class(text) or self.infer_cabin_class(heading)

            rule = self.normalizer.build_rule(
                category,
                constraints,
                severity="warn",
                notes=heading,
                route_type=route_type,
                cabin_class=cabin_class,
            )
            rules.append(rule)

        return rules

    def _parse_dangerous_goods(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        rules: List[Dict[str, Any]] = []
        for item in soup.select("li"):
            text = self.clean_text(item.get_text(" "))
            if not text:
                continue

            severity = "warn"
            constraints: Dict[str, Any] = {"description": text}
            if "배터리" in text:
                constraints.update({
                    "item": "lithium_battery",
                    "allow_spare_in_checked": False,
                    "terminal_protection_required": True,
                })
                severity = "block" if "금지" in text else "warn"
            elif "에어로졸" in text:
                constraints.update({"item": "aerosol", "max_container_ml": 500})

            rules.append(
                self.normalizer.build_rule(
                    "hazardous_materials",
                    constraints,
                    severity=severity,
                    notes=text,
                )
            )

        return rules

    # ------------------------------------------------------------------
    def _find_heading(self, block: Tag) -> Optional[Tag]:
        for level in ["h1", "h2", "h3", "h4"]:
            heading = block.find(level)
            if heading:
                return heading
        return None

    @staticmethod
    def _matches_keywords(text: str, keywords: Iterable[str]) -> bool:
        lowered = text.lower()
        return any(keyword.lower() in lowered for keyword in keywords)

    def _infer_constraints(self, text: str, category: str) -> Dict[str, Any]:
        constraints: Dict[str, Any] = {}

        pieces = self._extract_pieces(text)
        if pieces is not None:
            constraints["max_pieces"] = pieces

        weight = self._extract_weight(text)
        if weight is not None:
            constraints["max_weight_kg"] = weight

        dimensions = self._extract_dimensions(text)
        if dimensions:
            constraints["max_size_cm"] = dimensions
            constraints["max_total_cm"] = self.normalizer.sum_dimensions(dimensions)

        if category == "checked" and "초과" in text:
            fee = self._extract_fee(text)
            if fee is not None:
                constraints["overweight_fee_per_kg"] = fee

        return constraints

    def _extract_pieces(self, text: str) -> Optional[int]:
        match = self.PIECE_PATTERN.search(text)
        if not match:
            return None
        return int(match.group(1))

    def _extract_weight(self, text: str) -> Optional[float]:
        match = self.WEIGHT_PATTERN.search(text)
        if not match:
            return None
        value, unit = match.groups()
        return self.normalizer.weight_to_kg(value, unit)

    def _extract_dimensions(self, text: str) -> Optional[Dict[str, float]]:
        match = self.DIM_PATTERN.search(text)
        if match:
            length, width, height = match.groups()
            return self.normalizer.dimensions_to_cm(length, width, height, unit="cm")

        numbers = [number for number in self.extract_numbers(text) if number >= 10]
        if len(numbers) >= 3:
            length, width, height = numbers[:3]
            return {
                "length": length,
                "width": width,
                "height": height,
            }
        return None

    def _extract_fee(self, text: str) -> Optional[float]:
        match = re.search(r"(\d+(?:,\d+)*)\s*(?:KRW|원)", text)
        if not match:
            return None
        amount = float(match.group(1).replace(",", ""))
        return amount

