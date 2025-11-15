"""Configuration for regulation data sources.

This module centralises the list of official URLs and documents that must be
scraped or parsed in order to collect regulation data. Each entry maps to a
specific scraper implementation which is responsible for turning the remote
content into the standard regulation schema.
"""

from __future__ import annotations

from typing import Literal, TypedDict


class UrlConfig(TypedDict, total=False):
    """URLs used by a scraper.

    The keys are intentionally loose so that each scraper can decide which
    endpoints it needs. Additional keys can be added when new scrapers require
    them. All values should be absolute URLs.
    """

    carry_on: str
    checked: str
    dangerous_goods: str
    faq: str
    json: str
    landing: str
    pdfs: list[str]
    security: str
    customs: str
    liquids_rule: str
    hazardous: str
    references: list[str]


class SourceConfig(TypedDict, total=False):
    """High-level configuration for a single regulation source."""

    name: str
    urls: UrlConfig
    scraper: str
    content_type: Literal["static", "dynamic", "pdf"]
    notes: str


REGULATION_SOURCES: dict[str, dict[str, SourceConfig]] = {
    "airline": {
        "KE": {
            "name": "Korean Air",
            "scraper": "KoreanAirScraper",
            "content_type": "dynamic",
            "urls": {
                "carry_on": "https://www.koreanair.com/contents/plan-your-travel/baggage/carry-on-baggage",
                "checked": "https://www.koreanair.com/contents/plan-your-travel/baggage/checked-baggage/free-baggage",
                "dangerous_goods": "https://www.koreanair.com/contents/plan-your-travel/baggage/prohibited-items",
                "references": [
                    "https://www.koreanair.com/contents/plan-your-travel/baggage",
                ],
            },
            "notes": "Requires rendering of dynamic tables that expand by cabin class.",
        },
        "TW": {
            "name": "T'way Air",
            "scraper": "TwayAirScraper",
            "content_type": "static",
            "urls": {
                "carry_on": "https://www.twayair.com/app/serviceInfo/contents/1148",
                "checked": "https://www.twayair.com/app/serviceInfo/contents/1148",
                "dangerous_goods": "https://www.twayair.com/app/serviceInfo/contents/1148",
            },
            "notes": "Single-page layout with anchor sections for different baggage topics.",
        },
    },
    "country": {
        "KR": {
            "name": "Republic of Korea",
            "scraper": "KRSecurityScraper",
            "content_type": "static",
            "urls": {
                "security": "https://www.airport.kr/ap_en/1433/subview.do",
                "customs": "https://www.customs.go.kr/kcs/ad/TaxFreeLimitInOutline.do",
                "references": [
                    "https://www.airport.kr/ap_en/1433/subview.do",
                ],
            },
            "notes": "Separate data sections for security screening and customs allowances.",
        },
        "US": {
            "name": "United States",
            "scraper": "USSecurityScraper",
            "content_type": "static",
            "urls": {
                "security": "https://www.tsa.gov/travel/security-screening/whatcanibring/all-list",
                "customs": "https://www.cbp.gov/travel/us-citizens/know-before-you-go",
                "liquids_rule": "https://www.tsa.gov/travel/security-screening/liquids-aerosols-gels-rule?utm_source=chatgpt.com",
                "hazardous": "https://www.faa.gov/hazmat/packsafe/lithium-batteries?utm_source=chatgpt.com",
                "references": [
                    "https://www.tsa.gov/travel/security-screening/whatcanibring/all-list",
                    "https://www.tsa.gov/travel/security-screening/liquids-aerosols-gels-rule?utm_source=chatgpt.com",
                    "https://www.faa.gov/hazmat/packsafe/lithium-batteries?utm_source=chatgpt.com",
                ],
            },
            "notes": "TSA provides item-level guidance; CBP lists import restrictions and duty limits.",
        },
        "JP": {
            "name": "Japan",
            "scraper": "JPSecurityScraper",
            "content_type": "static",
            "urls": {
                "security": "https://www.cab.mlit.go.jp/english/aviation/security/list_of_items.html",
                "customs": "https://www.customs.go.jp/english/summary/passenger.htm",
                "liquids_rule": "https://www.narita-airport.jp/ko/airportguide/security/liquid/",
                "dangerous_goods": "https://www.narita-airport.jp/ko/airportguide/security/master-sheet/#3.%ED%9D%A1%EC%97%B0%EC%9A%A9%20%EB%9D%BC%EC%9D%B4%ED%84%B0",
                "pdfs": [
                    "https://www.mlit.go.jp/common/001425422.pdf",
                    "https://www.mlit.go.jp/koku/03_information/13_motikomiseigen/poster.pdf",
                ],
                "references": [
                    "https://www.narita-airport.jp/ko/airportguide/security/liquid/",
                    "https://www.narita-airport.jp/ko/airportguide/security/master-sheet/#3.%ED%9D%A1%EC%97%B0%EC%9A%A9%20%EB%9D%BC%EC%9D%B4%ED%84%B0",
                    "https://www.narita-airport.jp/ko/airportguide/security/master-sheet/#4.%EB%8F%84%EA%B2%80%EB%A5%98",
                    "https://www.mlit.go.jp/common/001425422.pdf",
                    "https://www.mlit.go.jp/koku/03_information/13_motikomiseigen/poster.pdf",
                ],
            },
            "notes": "Customs information is provided in English with detailed tables per category.",
        },
    },
    "international": {
        "ICAO": {
            "name": "ICAO Technical Instructions",
            "scraper": "ICAOPDFParser",
            "content_type": "pdf",
            "urls": {
                "pdfs": [
                    "https://www.icao.int/safety/DangerousGoods/PublishingImages/technical-instructions.pdf",
                ]
            },
            "notes": "Core reference for dangerous goods rules covering lithium batteries, dry ice, etc.",
        },
        "IATA": {
            "name": "IATA Dangerous Goods Regulations",
            "scraper": "IATAPDFParser",
            "content_type": "pdf",
            "urls": {
                "pdfs": [
                    "https://www.iata.org/contentassets/6fea26dd84d24b26a7a1fd5788561d6e/dgr-67-en-2.3.a.pdf",
                ]
            },
            "notes": "Supplemental guidance; access may require member authentication for latest editions.",
        },
    },
}


def get_source(scope: str, code: str) -> SourceConfig | None:
    """Return a specific source configuration.

    Args:
        scope: Top-level scope key ("airline", "country", or "international").
        code: Source identifier within the scope.

    Returns:
        The matching configuration, or ``None`` if not registered.
    """

    return REGULATION_SOURCES.get(scope, {}).get(code)


def list_sources(scope: str) -> dict[str, SourceConfig]:
    """Return all sources for a given scope."""

    return REGULATION_SOURCES.get(scope, {}).copy()

