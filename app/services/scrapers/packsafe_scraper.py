"""Scraper for FAA PackSafe printable chart."""

from __future__ import annotations

import json
import logging
from typing import Any

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)

PACKSAFE_URL = "https://www.faa.gov/hazmat/packsafe/printable-chart"


def _clean(text: str) -> str:
    return " ".join(text.split())


def _parse_permission(cell_text: str) -> tuple[bool | None, str]:
    cleaned = _clean(cell_text)
    lowered = cleaned.lower()
    if lowered.startswith("✓") or lowered.startswith("yes"):
        return True, cleaned
    if lowered.startswith("✗") or lowered.startswith("no") or "not allowed" in lowered:
        return False, cleaned
    return None, cleaned


def fetch_packsafe_items() -> list[dict[str, Any]]:
    logger.info("Fetching FAA PackSafe chart from %s", PACKSAFE_URL)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3_1) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.faa.gov/hazmat/packsafe"
    }
    response = requests.get(PACKSAFE_URL, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    tables = soup.find_all("table")
    if not tables:
        raise RuntimeError("Could not locate PackSafe tables")

    items: list[dict[str, Any]] = []
    for table in tables:
        body = table.find("tbody") or table
        for row in body.find_all("tr"):
            columns = row.find_all("td")
            if len(columns) < 7:
                continue

            item_name = _clean(columns[0].get_text(" ", strip=True))
            example = _clean(columns[1].get_text(" ", strip=True)) or None

            carry_allowed, carry_details = _parse_permission(columns[4].get_text(" ", strip=True))
            checked_allowed, checked_details = _parse_permission(columns[6].get_text(" ", strip=True))

            constraints: dict[str, Any] = {
                "carry_on_allowed": carry_allowed,
                "carry_on_details": carry_details,
                "checked_allowed": checked_allowed,
                "checked_details": checked_details,
                "reference": PACKSAFE_URL,
            }

            if example:
                constraints["examples"] = example

            items.append(
                {
                    "item_name": item_name or "Unknown",
                    "item_category": "faa_packsafe",
                    "constraints": constraints,
                    "severity": "warn" if (carry_allowed or checked_allowed) else "block",
                }
            )

    logger.info("Parsed %d PackSafe items", len(items))
    return items


def build_packsafe_regulation() -> dict[str, Any]:
    return {
        "scope": "country",
        "code": "US",
        "name": "FAA PackSafe Printable Chart",
        "rules": fetch_packsafe_items(),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    data = build_packsafe_regulation()
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
