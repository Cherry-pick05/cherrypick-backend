"""High-level crawler orchestrating airline, country, and PDF scrapers."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List

from sqlalchemy.orm import Session

from app.services.regulation_collector import RegulationCollector
from app.services.regulation_normalizer import RegulationNormalizer
from app.services.regulation_pdf_parser import ICAOPDFParser, IATAPDFParser, parse_pdf_with_parser
from app.services.regulation_sources import REGULATION_SOURCES
from app.services.scrapers import (
    JPSecurityScraper,
    KRSecurityScraper,
    KoreanAirScraper,
    TwayAirScraper,
    USSecurityScraper,
)

try:
    import requests
except ImportError:  # pragma: no cover - optional dependency guard
    requests = None  # type: ignore


logger = logging.getLogger(__name__)


class RegulationCrawler:
    """Coordinates scraping and optional persistence of regulation data."""

    AIRLINE_SCRAPERS = {
        "KE": KoreanAirScraper,
        "TW": TwayAirScraper,
    }

    COUNTRY_SCRAPERS = {
        "KR": KRSecurityScraper,
        "US": USSecurityScraper,
        "JP": JPSecurityScraper,
    }

    INTERNATIONAL_PARSERS = {
        "ICAO": ICAOPDFParser,
        "IATA": IATAPDFParser,
    }

    def __init__(
        self,
        db: Session | None = None,
        *,
        normalizer: RegulationNormalizer | None = None,
    ) -> None:
        self.db = db
        self.normalizer = normalizer or RegulationNormalizer()
        self.collector = RegulationCollector(db) if db else None

    # ------------------------------------------------------------------
    # Airline regulations
    # ------------------------------------------------------------------
    def crawl_airline_regulations(self, airline_code: str, *, persist: bool = False) -> List[Dict[str, Any]]:
        airline_code = airline_code.upper()
        scraper_cls = self.AIRLINE_SCRAPERS.get(airline_code)
        if not scraper_cls:
            raise ValueError(f"지원되지 않는 항공사 코드입니다: {airline_code}")

        scraper = scraper_cls(normalizer=self.normalizer)
        rules = scraper.scrape_airline_regulations(airline_code)
        self._validate_rules(rules)

        if persist:
            self._persist_rules("airline", airline_code, rules)

        return rules

    # ------------------------------------------------------------------
    # Country regulations
    # ------------------------------------------------------------------
    def crawl_country_regulations(self, country_code: str, *, persist: bool = False) -> List[Dict[str, Any]]:
        country_code = country_code.upper()
        scraper_cls = self.COUNTRY_SCRAPERS.get(country_code)
        if not scraper_cls:
            raise ValueError(f"지원되지 않는 국가 코드입니다: {country_code}")

        scraper = scraper_cls(normalizer=self.normalizer)
        rules = scraper.scrape_country_regulations(country_code)
        self._validate_rules(rules)

        if persist:
            self._persist_rules("country", country_code, rules)

        return rules

    # ------------------------------------------------------------------
    # International (PDF) regulations
    # ------------------------------------------------------------------
    def crawl_international_regulations(self) -> Dict[str, List[Dict[str, Any]]]:
        results: Dict[str, List[Dict[str, Any]]] = {}
        for code, parser_cls in self.INTERNATIONAL_PARSERS.items():
            config = REGULATION_SOURCES.get("international", {}).get(code)
            if not config:
                logger.warning("국제 규정 소스를 찾을 수 없습니다: %s", code)
                continue

            parser = parser_cls()
            urls = config.get("urls", {}).get("pdfs", [])
            parser_results: List[Dict[str, Any]] = []
            for pdf_url in urls:
                try:
                    data = self._parse_pdf_resource(parser, pdf_url)
                    self._validate_rules(data)
                    parser_results.extend(data)
                except FileNotFoundError:
                    logger.warning("PDF 파일을 찾을 수 없습니다: %s", pdf_url)
                except Exception as exc:  # pragma: no cover - network errors
                    logger.error("PDF 파싱 실패: %s", pdf_url, exc_info=exc)
            results[code] = parser_results
        return results

    # ------------------------------------------------------------------
    # Bulk orchestration
    # ------------------------------------------------------------------
    def crawl_all(self, *, persist: bool = False) -> Dict[str, Any]:
        output: Dict[str, Any] = {
            "airline": {},
            "country": {},
            "international": {},
        }

        for airline_code in REGULATION_SOURCES.get("airline", {}):
            output["airline"][airline_code] = self.crawl_airline_regulations(airline_code, persist=persist)

        for country_code in REGULATION_SOURCES.get("country", {}):
            output["country"][country_code] = self.crawl_country_regulations(country_code, persist=persist)

        output["international"] = self.crawl_international_regulations()

        return output

    # ------------------------------------------------------------------
    # Persistence helper
    # ------------------------------------------------------------------
    def _persist_rules(self, scope: str, code: str, rules: Iterable[Dict[str, Any]]) -> None:
        if not self.collector:
            logger.debug("DB 세션이 없어 규정 저장을 건너뜁니다")
            return

        if scope not in {"airline", "country"}:
            logger.info("scope %s 는 DB 저장을 지원하지 않습니다", scope)
            return

        for rule in rules:
            try:
                self.collector.save_regulation(
                    scope=scope,
                    code=code,
                    item_category=rule["item_category"],
                    constraints=rule["constraints"],
                    severity=rule.get("severity", "info"),
                    notes=rule.get("notes"),
                )
            except Exception as exc:  # pragma: no cover - db errors
                logger.error("규정 저장 실패: %s - %s", scope, code, exc_info=exc)

    # ------------------------------------------------------------------
    def _parse_pdf_resource(self, parser: Any, pdf_path: str) -> List[Dict[str, Any]]:
        if pdf_path.startswith("http://") or pdf_path.startswith("https://"):
            if requests is None:
                raise RuntimeError("requests 라이브러리가 필요합니다. pyproject.toml을 확인하세요.")
            response = requests.get(pdf_path, timeout=30)
            response.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(response.content)
                tmp_path = tmp.name
            try:
                return parse_pdf_with_parser(parser, tmp_path)
            finally:
                Path(tmp_path).unlink(missing_ok=True)

        return parse_pdf_with_parser(parser, pdf_path)

    def _validate_rules(self, rules: Iterable[Dict[str, Any]]) -> None:
        for rule in rules:
            try:
                self.normalizer.validate_rule(rule)
            except ValueError as exc:
                logger.error("규정 검증 실패: %s", rule, exc_info=exc)
                raise
