"""Scraper for TSA "What Can I Bring" list.

This module fetches the TSA alphabetical list of items and converts it into the
project's regulation JSON format. Each entry captures the carry-on / checked bag
permissions along with descriptive notes.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)

TSA_URL = "https://www.tsa.gov/travel/security-screening/whatcanibring/all-list"


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def _parse_permission(text: str) -> tuple[bool | None, str]:
    cleaned = _normalize_whitespace(text)
    lowered = cleaned.lower()
    if lowered.startswith("yes"):
        return True, cleaned
    if lowered.startswith("no"):
        return False, cleaned
    return None, cleaned


def fetch_tsa_items() -> list[dict[str, Any]]:
    """Fetch and parse the TSA item table."""

    logger.info("Fetching TSA 'What Can I Bring' list from %s", TSA_URL)
    response = requests.get(TSA_URL, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    table = soup.find("table")
    if not table:
        raise RuntimeError("Could not locate TSA items table on the page")

    body = table.find("tbody") or table
    items: list[dict[str, Any]] = []

    for row in body.find_all("tr"):
        columns = row.find_all("td")
        if len(columns) < 3:
            continue

        item_cell, carry_on_cell, checked_cell = columns[:3]

        # Extract item name and description.
        item_link = item_cell.find("a")
        item_name = _normalize_whitespace(item_link.get_text(strip=True) if item_link else item_cell.get_text(strip=True))
        item_url = item_link["href"] if item_link and item_link.has_attr("href") else None

        description_parts = []
        for elem in item_cell.contents:
            if getattr(elem, "name", None) == "br":
                description_parts.append("\n")
            elif isinstance(elem, str):
                description_parts.append(elem)
            elif hasattr(elem, "get_text"):
                description_parts.append(elem.get_text(" ", strip=True))
        description = _normalize_whitespace(" ".join(description_parts))

        carry_allowed, carry_text = _parse_permission(carry_on_cell.get_text(" ", strip=True))
        checked_allowed, checked_text = _parse_permission(checked_cell.get_text(" ", strip=True))

        constraints: dict[str, Any] = {
            "carry_on_allowed": carry_allowed,
            "carry_on_notes": carry_text,
            "checked_allowed": checked_allowed,
            "checked_notes": checked_text,
        }

        if item_url:
            constraints["reference"] = item_url

        if description and description.lower() != item_name.lower():
            constraints["description"] = description

        items.append(
            {
                "item_name": item_name,
                "item_category": "tsa_restriction",
                "constraints": constraints,
                "severity": "warn" if carry_allowed or checked_allowed else "block",
            }
        )

    logger.info("Parsed %d TSA items", len(items))
    return items


def build_tsa_regulation() -> dict[str, Any]:
    """Return the regulation JSON structure for TSA items."""

    rules = fetch_tsa_items()
    return {
        "scope": "country",
        "code": "US",
        "name": "TSA What Can I Bring",
        "rules": rules,
    }


def main() -> None:
    data = build_tsa_regulation()
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
