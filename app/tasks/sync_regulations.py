"""Command-line entry point for crawling and syncing regulation data."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List

from app.db.session import SessionLocal
from app.services.regulation_crawler import RegulationCrawler
from app.services.regulation_sources import REGULATION_SOURCES


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync regulation data into the database")
    parser.add_argument(
        "--scope",
        choices=["airline", "country", "international", "all"],
        default="all",
        help="Which scope of regulations to crawl",
    )
    parser.add_argument(
        "--code",
        action="append",
        help="Filter specific codes (airline code, country code, or parser key)",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Do not store results in the database (just output JSON)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the crawled results as JSON",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    persist = not args.no_persist
    db = SessionLocal() if persist else None
    crawler = RegulationCrawler(db=db)

    try:
        results: Dict[str, List[Dict]] | Dict[str, Dict] | Dict[str, Dict[str, List[Dict]]] = {}

        if args.scope in {"airline", "all"}:
            airline_codes = _resolve_codes(args.code, "airline") if args.scope == "airline" else list(REGULATION_SOURCES["airline"].keys())
            results_airline: Dict[str, List[Dict]] = {}
            for code in airline_codes:
                logger.info("크롤링: 항공사 %s", code)
                results_airline[code] = crawler.crawl_airline_regulations(code, persist=persist)
            results["airline"] = results_airline

        if args.scope in {"country", "all"}:
            country_codes = _resolve_codes(args.code, "country") if args.scope == "country" else list(REGULATION_SOURCES["country"].keys())
            results_country: Dict[str, List[Dict]] = {}
            for code in country_codes:
                logger.info("크롤링: 국가 %s", code)
                results_country[code] = crawler.crawl_country_regulations(code, persist=persist)
            results["country"] = results_country

        if args.scope in {"international", "all"}:
            intl_results = crawler.crawl_international_regulations()
            if args.scope == "international" and args.code:
                filtered = {code: intl_results.get(code, []) for code in args.code if code in intl_results}
                if not filtered:
                    logger.warning("유효한 국제 규정 코드가 없습니다: %s", args.code)
                results["international"] = filtered or intl_results
            else:
                results["international"] = intl_results

        if args.output:
            args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("크롤링 결과를 저장했습니다: %s", args.output)
        else:
            print(json.dumps(results, ensure_ascii=False, indent=2))
    finally:
        if db:
            db.close()


def _resolve_codes(codes: List[str] | None, scope: str) -> List[str]:
    if not codes:
        return list(REGULATION_SOURCES[scope].keys())
    resolved = [code.upper() for code in codes if code.upper() in REGULATION_SOURCES[scope]]
    if not resolved:
        raise ValueError(f"유효한 {scope} 코드가 없습니다: {codes}")
    return resolved


if __name__ == "__main__":
    main()
