"""Base infrastructure for web scraping regulation data."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin

try:
    import requests
except ImportError:  # pragma: no cover - runtime guard for optional installs
    requests = None  # type: ignore

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - runtime guard for optional installs
    BeautifulSoup = None  # type: ignore

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - runtime guard for optional installs
    sync_playwright = None  # type: ignore


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PageRequest:
    """Parameters describing how to fetch a page."""

    url: str
    requires_js: bool = False
    wait_selector: Optional[str] = None
    wait_until: str = "networkidle"


class ScraperDependencyError(RuntimeError):
    """Raised when an optional dependency required for scraping is missing."""


class RegulationScraper:
    """Base class for scraping regulation data from the web."""

    def __init__(
        self,
        base_url: str,
        user_agent: Optional[str] = None,
        timeout: int = 15,
        delay_seconds: float = 1.0,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent or "Mozilla/5.0 (compatible; CherryPickBot/1.0)"
        self.timeout = timeout
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
        }

    # ------------------------------------------------------------------
    # Networking helpers
    # ------------------------------------------------------------------
    def resolve(self, path: str) -> str:
        """Resolve a relative path against the base URL."""

        if path.startswith("http://") or path.startswith("https://"):
            return path
        return urljoin(f"{self.base_url}/", path.lstrip("/"))

    def fetch_html(self, request: PageRequest) -> str:
        """Fetch a page as HTML, handling static or dynamic content."""

        last_exception: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(
                    "Fetching page",
                    extra={"url": request.url, "requires_js": request.requires_js, "attempt": attempt},
                )

                if request.requires_js:
                    return self._fetch_with_playwright(request)

                try:
                    return self._fetch_with_requests(request.url)
                except Exception as static_exc:
                    logger.debug("정적 요청 실패, 동적 시도", exc_info=static_exc)
                    if request.requires_js is False:
                        return self._fetch_with_playwright(request)
                    raise
            except Exception as exc:
                last_exception = exc
                if attempt >= self.max_retries:
                    logger.error("페이지 수집 실패 (최대 재시도 초과): %s", request.url, exc_info=exc)
                    break
                wait = self.backoff_factor * attempt
                logger.warning(
                    "페이지 수집 실패 (재시도 예정 %ss): %s",
                    wait,
                    request.url,
                    exc_info=exc,
                )
                time.sleep(wait)

        if last_exception:
            raise last_exception
        raise RuntimeError(f"Failed to fetch page: {request.url}")

    def _fetch_with_requests(self, url: str) -> str:
        if requests is None:
            raise ScraperDependencyError("requests 라이브러리가 필요합니다. pyproject.toml을 확인하세요.")

        response = requests.get(url, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        time.sleep(self.delay_seconds)
        return response.text

    def _fetch_with_playwright(self, request: PageRequest) -> str:
        if sync_playwright is None:
            raise ScraperDependencyError("playwright 라이브러리가 필요합니다. pyproject.toml을 확인하세요.")

        with sync_playwright() as p:  # type: ignore[operator]
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=self.user_agent)
            page.goto(request.url, timeout=self.timeout * 1000, wait_until=request.wait_until)
            if request.wait_selector:
                page.wait_for_selector(request.wait_selector, timeout=self.timeout * 1000)
            html = page.content()
            browser.close()
        time.sleep(self.delay_seconds)
        return html

    def get_soup(self, request: PageRequest) -> "BeautifulSoup":
        if BeautifulSoup is None:
            raise ScraperDependencyError("beautifulsoup4 라이브러리가 필요합니다. pyproject.toml을 확인하세요.")

        html = self.fetch_html(request)
        return BeautifulSoup(html, "lxml")

    def fetch_json(self, url: str) -> Any:
        if requests is None:
            raise ScraperDependencyError("requests 라이브러리가 필요합니다. pyproject.toml을 확인하세요.")

        response = requests.get(url, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        time.sleep(self.delay_seconds)
        return response.json()

    # ------------------------------------------------------------------
    # Text helpers
    # ------------------------------------------------------------------
    @staticmethod
    def clean_text(value: str) -> str:
        return " ".join(value.split())

    @staticmethod
    def extract_numbers(value: str) -> List[float]:
        numbers: List[float] = []
        current = ""
        for char in value:
            if char.isdigit() or char == ".":
                current += char
            else:
                if current:
                    try:
                        numbers.append(float(current))
                    except ValueError:
                        logger.debug("Failed to parse number", extra={"chunk": current})
                    current = ""
        if current:
            try:
                numbers.append(float(current))
            except ValueError:
                logger.debug("Failed to parse number", extra={"chunk": current})
        return numbers

    @staticmethod
    def text_matches(value: str, keywords: Iterable[str]) -> bool:
        lowered = value.lower()
        return any(keyword.lower() in lowered for keyword in keywords)

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------
    def scrape_airline_regulations(self, airline_code: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def scrape_country_regulations(self, country_code: str) -> List[Dict[str, Any]]:
        raise NotImplementedError


class ExampleAirlineScraper(RegulationScraper):
    """Example implementation demonstrating the base hooks."""

    def scrape_airline_regulations(self, airline_code: str) -> List[Dict[str, Any]]:
        url = self.resolve(f"/baggage/{airline_code}")
        soup = self.get_soup(PageRequest(url=url, requires_js=False))

        regulations: List[Dict[str, Any]] = []
        section = soup.find("div", class_="carry-on")
        if section:
            text = self.clean_text(section.get_text(" "))
            numbers = self.extract_numbers(text)
            regulations.append(
                {
                    "category": "carry_on",
                    "constraints": {
                        "max_weight_kg": numbers[0] if numbers else None,
                        "notes": text,
                    },
                    "severity": "warn",
                }
            )

        logger.info("%s 규정 스크래핑 완료", airline_code)
        return regulations


# 사용 예시:
"""
from app.services.regulation_scraper import ExampleAirlineScraper
from app.services.regulation_collector import RegulationCollector
from app.db.session import SessionLocal

# 스크래퍼 생성
scraper = ExampleAirlineScraper(
    base_url="https://example-airline.com"
)

# 규정 수집
regulations = scraper.scrape_airline_regulations("KE")

# DB에 저장
db = SessionLocal()
collector = RegulationCollector(db)

for reg in regulations:
    collector.save_regulation(
        scope="airline",
        code="KE",
        item_category=reg["category"],
        constraints=reg["constraints"],
        severity=reg.get("severity", "info")
    )
"""


