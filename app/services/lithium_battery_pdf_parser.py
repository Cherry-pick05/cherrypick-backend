"""PDF parser for 'Lithium Batteries in Baggage' document.

This helper extracts every table from the PDF and emits them as JSON so that
they can be post-processed into regulation rules.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pdfplumber


logger = logging.getLogger(__name__)

DEFAULT_PDF_PATH = Path("docs/Lithium Batteries in Baggage.pdf")


def extract_tables(pdf_path: Path = DEFAULT_PDF_PATH) -> list[dict[str, Any]]:
    """Extract tables from the provided PDF.

    Returns a list where each element contains the page number and the table
    contents (rows represented as lists of cells).
    """

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    tables: list[dict[str, Any]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            page_tables = page.extract_tables() or []
            logger.debug("Page %s: extracted %s tables", page_index, len(page_tables))

            for table_index, table in enumerate(page_tables, start=1):
                cleaned_rows = [
                    [cell.strip() if isinstance(cell, str) else cell for cell in (row or [])]
                    for row in table
                ]

                tables.append(
                    {
                        "page": page_index,
                        "table_index": table_index,
                        "rows": cleaned_rows,
                    }
                )

    return tables


def build_raw_json(pdf_path: Path = DEFAULT_PDF_PATH) -> dict[str, Any]:
    tables = extract_tables(pdf_path)
    return {
        "source": str(pdf_path),
        "tables": tables,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    data = build_raw_json()
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
