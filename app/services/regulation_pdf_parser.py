"""Utilities for parsing regulation documents published as PDF files."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional

try:
    import pdfplumber
except ImportError:  # pragma: no cover - runtime guard for optional installs
    pdfplumber = None  # type: ignore


logger = logging.getLogger(__name__)


class PDFDependencyError(RuntimeError):
    """Raised when pdfplumber is not available."""


@dataclass(slots=True)
class PDFRule:
    """Structured representation of a rule extracted from a PDF."""

    item_category: str
    constraints: dict[str, Any]
    severity: str = "warn"
    notes: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "item_category": self.item_category,
            "constraints": self.constraints,
            "severity": self.severity,
        }
        if self.notes:
            data["notes"] = self.notes
        return data


class RegulationPDFParser:
    """Base class for parsing regulation information from PDF documents."""

    def __init__(self, language: str = "en") -> None:
        self.language = language

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------
    def _ensure_dependency(self) -> None:
        if pdfplumber is None:
            raise PDFDependencyError("pdfplumber 라이브러리가 필요합니다. pyproject.toml을 확인하세요.")

    def extract_text(self, pdf_path: str | Path) -> List[str]:
        """Return raw text for each page."""

        self._ensure_dependency()
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {path}")

        with pdfplumber.open(path) as pdf:  # type: ignore[union-attr]
            texts: List[str] = []
            for page in pdf.pages:
                text = page.extract_text() or ""
                texts.append(text)
        logger.debug("Extracted text from %s pages", len(texts))
        return texts

    def extract_tables(self, pdf_path: str | Path) -> List[list[list[str]]]:
        """Return all tables found within the PDF."""

        self._ensure_dependency()
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {path}")

        tables: List[list[list[str]]] = []
        with pdfplumber.open(path) as pdf:  # type: ignore[union-attr]
            for page in pdf.pages:
                extracted = page.extract_tables()
                if extracted:
                    tables.extend(extracted)
        logger.debug("Extracted %s tables", len(tables))
        return tables

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _contains_keywords(text: str, keywords: Iterable[str]) -> bool:
        lowered = text.lower()
        return any(keyword.lower() in lowered for keyword in keywords)

    @staticmethod
    def _find_numeric_values(text: str) -> List[float]:
        values: List[float] = []
        for part in re.findall(r"\d+(?:\.\d+)?", text):
            try:
                values.append(float(part))
            except ValueError:
                logger.debug("숫자 파싱 실패", extra={"chunk": part})
        return values

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def parse(self, pdf_path: str | Path) -> List[dict[str, Any]]:
        """Subclasses must implement parsing logic."""

        raise NotImplementedError


class ICAOPDFParser(RegulationPDFParser):
    """Parser for ICAO Technical Instructions dangerous goods guidance."""

    LITHIUM_KEYWORDS = ["lithium", "battery", "wh"]
    DRY_ICE_KEYWORDS = ["dry ice", "solid carbon dioxide"]

    def parse(self, pdf_path: str | Path) -> List[dict[str, Any]]:
        texts = self.extract_text(pdf_path)

        rules: List[PDFRule] = []

        for page in texts:
            normalized = page.replace("\n", " ")
            if self._contains_keywords(normalized, self.LITHIUM_KEYWORDS):
                numbers = self._find_numeric_values(normalized)
                max_wh = max((value for value in numbers if value >= 10), default=100.0)
                rules.append(
                    PDFRule(
                        item_category="hazardous_materials",
                        constraints={
                            "item": "lithium_battery",
                            "max_watt_hour": max_wh,
                            "allow_spare_in_checked": False,
                            "allow_spare_in_cabin": True,
                            "terminal_protection_required": True,
                        },
                        severity="block",
                        notes="ICAO guidance derived from Technical Instructions",
                    )
                )
            if self._contains_keywords(normalized, self.DRY_ICE_KEYWORDS):
                amounts = self._find_numeric_values(normalized)
                max_kg = max((value for value in amounts if value <= 10), default=2.5)
                rules.append(
                    PDFRule(
                        item_category="hazardous_materials",
                        constraints={
                            "item": "dry_ice",
                            "max_weight_kg": max_kg,
                            "packaging_requirements": ["ventilated", "crew_informed"],
                        },
                        severity="warn",
                        notes="Dry ice quantity limits for passenger baggage",
                    )
                )

        deduped = self._deduplicate_rules(rules)
        return [rule.to_dict() for rule in deduped]

    @staticmethod
    def _deduplicate_rules(rules: List[PDFRule]) -> List[PDFRule]:
        seen: set[tuple[str, str]] = set()
        deduped: List[PDFRule] = []
        for rule in rules:
            key = (rule.item_category, rule.constraints.get("item", ""))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(rule)
        return deduped


class IATAPDFParser(RegulationPDFParser):
    """Parser for IATA Dangerous Goods guidance documents."""

    ALCOHOL_KEYWORDS = ["alcohol", "%", "spirits"]
    AEROSOL_KEYWORDS = ["aerosol", "spray"]

    def parse(self, pdf_path: str | Path) -> List[dict[str, Any]]:
        texts = self.extract_text(pdf_path)

        rules: List[PDFRule] = []
        for page in texts:
            normalized = page.replace("\n", " ")
            if self._contains_keywords(normalized, self.ALCOHOL_KEYWORDS):
                percentages = self._find_numeric_values(normalized)
                max_abv = max((value for value in percentages if value <= 70), default=70)
                rules.append(
                    PDFRule(
                        item_category="hazardous_materials",
                        constraints={
                            "item": "alcohol",
                            "max_abv_percent": max_abv,
                            "carry_on_limit_l": 5,
                            "checked_limit_l": 5,
                        },
                        severity="warn",
                        notes="IATA DGR guidance for alcoholic beverages",
                    )
                )
            if self._contains_keywords(normalized, self.AEROSOL_KEYWORDS):
                quantities = self._find_numeric_values(normalized)
                max_volume = max((value for value in quantities if value <= 0.5), default=0.5)
                rules.append(
                    PDFRule(
                        item_category="hazardous_materials",
                        constraints={
                            "item": "aerosol",
                            "max_container_l": max_volume,
                            "safety_cap_required": True,
                        },
                        severity="warn",
                        notes="Aerosol carriage requirements",
                    )
                )

        deduped = ICAOPDFParser._deduplicate_rules(rules)
        return [rule.to_dict() for rule in deduped]


def parse_pdf_with_parser(parser: RegulationPDFParser, pdf_path: str | Path) -> List[dict[str, Any]]:
    """Helper function for ad-hoc parsing."""

    logger.info("Parsing PDF with %s", parser.__class__.__name__)
    return parser.parse(pdf_path)

