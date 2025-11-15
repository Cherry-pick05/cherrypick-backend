"""Parse packsafe.md Markdown table into regulation JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PACKSAFE_MD_PATH = Path("docs/packsafe.md")


def _normalize(text: str) -> str:
    return " ".join(text.split()) if text else ""


def _parse_bool(symbol: str) -> bool | None:
    cleaned = symbol.strip().lower()
    if cleaned in {"✔", "✓", "yes", "y"}:
        return True
    if cleaned in {"✘", "✗", "x", "no", "n"}:
        return False
    return None


def parse_packsafe_markdown(md_path: Path = PACKSAFE_MD_PATH) -> list[dict[str, Any]]:
    if not md_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    lines = md_path.read_text(encoding="utf-8").splitlines()

    rules: list[dict[str, Any]] = []
    for line in lines:
        if not line.startswith("| ") or line.startswith("| :"):
            continue

        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 6:
            continue

        item, examples, carry_symbol, carry_details, checked_symbol, checked_details = cells[:6]

        carry_allowed = _parse_bool(carry_symbol)
        checked_allowed = _parse_bool(checked_symbol)

        constraints: dict[str, Any] = {
            "examples": _normalize(examples) or None,
            "carry_on_allowed": carry_allowed,
            "carry_on_details": _normalize(carry_details),
            "checked_allowed": checked_allowed,
            "checked_details": _normalize(checked_details),
        }

        constraints = {k: v for k, v in constraints.items() if v not in {None, ""}}

        rules.append(
            {
                "item_name": _normalize(item).strip("* "),
                "item_category": "faa_packsafe",
                "constraints": constraints,
                "severity": "warn" if (carry_allowed or checked_allowed) else "block",
            }
        )

    return rules


def build_packsafe_markdown_regulation(md_path: Path = PACKSAFE_MD_PATH) -> dict[str, Any]:
    return {
        "scope": "country",
        "code": "US_PACKSAFE_MD",
        "name": "FAA PackSafe (Markdown)",
        "rules": parse_packsafe_markdown(md_path),
    }


def main() -> None:
    data = build_packsafe_markdown_regulation()
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
