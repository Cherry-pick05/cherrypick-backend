"""Normalization utilities for regulation data collected from various sources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional


VALID_SEVERITIES = {"info", "warn", "block"}
VALID_ROUTE_TYPES = {None, "domestic", "international"}
VALID_CABIN_CLASSES = {None, "economy", "business", "first", "prestige"}


@dataclass(slots=True)
class NormalizedRule:
    """Dataclass wrapper for a normalized rule entry."""

    item_category: str
    constraints: Dict[str, Any]
    severity: str = "info"
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "item_category": self.item_category,
            "constraints": self.constraints,
            "severity": self.severity,
        }
        if self.notes:
            data["notes"] = self.notes
        return data


class RegulationNormalizer:
    """Helper class that turns raw scraped fragments into the canonical schema."""

    def build_rule(
        self,
        item_category: str,
        raw_constraints: Mapping[str, Any] | None = None,
        *,
        severity: str = "info",
        notes: str | None = None,
        route_type: str | None = None,
        cabin_class: str | None = None,
        fare_class: str | None = None,
    ) -> Dict[str, Any]:
        constraints = dict(raw_constraints or {})

        severity = severity.lower()
        if severity not in VALID_SEVERITIES:
            raise ValueError(f"잘못된 severity 값입니다: {severity}")

        route_type = route_type.lower() if route_type else None
        if route_type not in VALID_ROUTE_TYPES:
            allowed = {value for value in VALID_ROUTE_TYPES if value is not None}
            raise ValueError(f"잘못된 route_type입니다: {route_type}, 허용 값: {allowed}")

        cabin_class = cabin_class.lower() if cabin_class else None
        if cabin_class not in VALID_CABIN_CLASSES:
            allowed = {value for value in VALID_CABIN_CLASSES if value is not None}
            raise ValueError(f"잘못된 cabin_class입니다: {cabin_class}, 허용 값: {allowed}")

        if route_type:
            constraints["route_type"] = route_type
        if cabin_class:
            constraints["cabin_class"] = cabin_class
        if fare_class:
            constraints["fare_class"] = fare_class.lower()

        return NormalizedRule(
            item_category=item_category,
            constraints=constraints,
            severity=severity,
            notes=notes,
        ).to_dict()

    # ------------------------------------------------------------------
    # Constraint manipulation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def merge_constraints(*parts: Mapping[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        for part in parts:
            for key, value in part.items():
                merged[key] = value
        return merged

    @staticmethod
    def ensure_numeric(value: Any) -> float:
        if value is None:
            raise ValueError("숫자 값이 필요합니다")
        if isinstance(value, (int, float)):
            return float(value)
        cleaned = str(value).replace(",", "").strip()
        return float(cleaned)

    @staticmethod
    def weight_to_kg(value: Any, unit: str | None = None) -> float:
        kg = RegulationNormalizer.ensure_numeric(value)
        unit = (unit or "kg").lower()
        if unit in {"g", "gram", "grams"}:
            kg = kg / 1000.0
        elif unit in {"lb", "lbs", "pound", "pounds"}:
            kg = kg * 0.45359237
        elif unit not in {"kg", "kilogram", "kilograms"}:
            raise ValueError(f"지원되지 않는 무게 단위입니다: {unit}")
        return round(kg, 3)

    @staticmethod
    def volume_to_liters(value: Any, unit: str | None = None) -> float:
        liters = RegulationNormalizer.ensure_numeric(value)
        unit = (unit or "l").lower()
        if unit in {"ml", "milliliter", "milliliters"}:
            liters = liters / 1000.0
        elif unit in {"g", "gram"}:  # approximate for water-equivalent substances
            liters = liters / 1000.0
        elif unit in {"oz", "fl oz"}:
            liters = liters * 0.0295735
        elif unit not in {"l", "liter", "liters"}:
            raise ValueError(f"지원되지 않는 부피 단위입니다: {unit}")
        return round(liters, 3)

    @staticmethod
    def dimensions_to_cm(length: Any, width: Any, height: Any, unit: str | None = None) -> Dict[str, float]:
        unit = (unit or "cm").lower()
        factor = 1.0
        if unit in {"mm", "millimeter", "millimeters"}:
            factor = 0.1
        elif unit in {"inch", "in", "inches"}:
            factor = 2.54
        elif unit not in {"cm", "centimeter", "centimeters"}:
            raise ValueError(f"지원되지 않는 길이 단위입니다: {unit}")

        def convert(value: Any) -> float:
            return round(RegulationNormalizer.ensure_numeric(value) * factor, 2)

        return {
            "length": convert(length),
            "width": convert(width),
            "height": convert(height),
        }

    @staticmethod
    def sum_dimensions(dimensions: Mapping[str, Any]) -> float:
        return round(
            RegulationNormalizer.ensure_numeric(dimensions.get("length", 0))
            + RegulationNormalizer.ensure_numeric(dimensions.get("width", 0))
            + RegulationNormalizer.ensure_numeric(dimensions.get("height", 0)),
            2,
        )

    @staticmethod
    def copy_constraints(base: Mapping[str, Any], overrides: Mapping[str, Any] | None = None) -> Dict[str, Any]:
        combined = dict(base)
        if overrides:
            combined.update(overrides)
        return combined

    @staticmethod
    def pick(keys: Iterable[str], source: Mapping[str, Any]) -> Dict[str, Any]:
        return {key: source[key] for key in keys if key in source}

    @staticmethod
    def clamp(value: float, minimum: float | None = None, maximum: float | None = None) -> float:
        result = value
        if minimum is not None:
            result = max(result, minimum)
        if maximum is not None:
            result = min(result, maximum)
        return result

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def validate_rule(rule: Mapping[str, Any]) -> None:
        if "item_category" not in rule:
            raise ValueError("item_category 필드가 필요합니다")
        if "constraints" not in rule or not isinstance(rule["constraints"], Mapping):
            raise ValueError("constraints 필드가 필요하며 객체여야 합니다")
        severity = rule.get("severity", "info")
        if severity not in VALID_SEVERITIES:
            raise ValueError(f"잘못된 severity 값입니다: {severity}")

    def normalize_rules(self, rules: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for rule in rules:
            self.validate_rule(rule)
            normalized.append(dict(rule))
        return normalized
