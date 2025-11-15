"""Static configuration describing how canonical items map to regulation rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Sequence
from typing import Literal


LayerName = str
LayerKind = Literal["security", "dangerous_goods", "customs", "airline"]


@dataclass(frozen=True, slots=True)
class RuleSelector:
    """Declarative description of how to fetch a rule for a canonical key."""

    scope: str
    code: str
    reason_codes: tuple[str, ...] = ()
    item_category: str | None = None
    item_name_contains: tuple[str, ...] = ()
    ext_contains: tuple[tuple[str, str], ...] = ()
    layer: LayerName | None = None
    layer_kind: LayerKind | None = None
    applies_to_carry_on: bool = True
    applies_to_checked: bool = True
    requires_security_country: tuple[str, ...] = ()
    requires_rescreening: bool = False
    badges: tuple[str, ...] = ()
    max_rules: int | None = None

    def matches_ext(self, ext_payload: Mapping[str, object] | None) -> bool:
        if not self.ext_contains:
            return True
        if not ext_payload:
            return False
        for key, expected in self.ext_contains:
            value = ext_payload.get(key)
            if value != expected:
                return False
        return True


DEFAULT_LAYER_BY_SCOPE: dict[str, LayerName] = {
    "international": "international",
    "country": "country_security",
    "airline": "airline",
}


CANONICAL_RULE_SELECTORS: dict[str, Sequence[RuleSelector]] = {
    "cosmetics_liquid": (
        RuleSelector(
            scope="country",
            code="KR",
            item_category="restricted_liquids",
            reason_codes=("SEC_KR_LAGS",),
            layer_kind="security",
            applies_to_checked=False,
            requires_security_country=("KR",),
            badges=("100ml", "1L zip bag"),
        ),
    ),
    "aerosol": (
        RuleSelector(
            scope="country",
            code="KR",
            item_category="restricted_liquids",
            reason_codes=("SEC_KR_AEROSOL",),
            layer_kind="security",
            applies_to_checked=False,
            requires_security_country=("KR",),
            badges=("100ml", "Pressure cap"),
        ),
        RuleSelector(
            scope="country",
            code="US_TSA",
            item_name_contains=("Hair Spray",),
            reason_codes=("SEC_US_AEROSOL",),
            layer_kind="security",
            applies_to_checked=False,
            requires_security_country=("US",),
            badges=("3-1-1",),
        ),
        RuleSelector(
            scope="country",
            code="US_PACKSAFE_MD",
            item_name_contains=("Aerosols, Flammable",),
            reason_codes=("DG_US_AEROSOL_FLAMMABLE",),
            layer_kind="dangerous_goods",
        ),
        RuleSelector(
            scope="country",
            code="US_PACKSAFE_MD",
            item_name_contains=("Aerosols, Nonflammable",),
            reason_codes=("DG_US_AEROSOL_NONFLAM",),
            layer_kind="dangerous_goods",
        ),
    ),
    "alcohol_beverage": (
        RuleSelector(
            scope="international",
            code="IATA",
            item_name_contains=("Alcoholic beverages",),
            reason_codes=("DG_IATA_ALCOHOL",),
            layer_kind="dangerous_goods",
            badges=("≤5L",),
        ),
        RuleSelector(
            scope="country",
            code="US_PACKSAFE_MD",
            item_name_contains=("Alcoholic Beverages under 140 Proof",),
            reason_codes=("DG_US_PACKSAFE_ALC",),
            layer_kind="dangerous_goods",
        ),
    ),
    "lithium_ion_battery_spare": (
        RuleSelector(
            scope="international",
            code="IATA",
            item_name_contains=("Spare/loose batteries",),
            reason_codes=("DG_IATA_SPARE_LIION",),
            layer_kind="dangerous_goods",
            badges=("Terminal cover",),
        ),
        RuleSelector(
            scope="country",
            code="KR",
            item_category="hazardous_materials",
            ext_contains=(("item", "lithium_battery_spares"),),
            reason_codes=("SEC_KR_SPARE_LIION",),
            layer_kind="security",
            requires_security_country=("KR",),
        ),
        RuleSelector(
            scope="country",
            code="US_PACKSAFE_MD",
            item_name_contains=("Batteries, Lithium",),
            reason_codes=("DG_US_PACKSAFE_LIION",),
            layer_kind="dangerous_goods",
        ),
    ),
    "lithium_ion_battery_installed": (
        RuleSelector(
            scope="international",
            code="IATA",
            item_name_contains=("Fuel cells powering portable electronic devices",),
            reason_codes=("DG_IATA_INSTALLED_LIION",),
            layer_kind="dangerous_goods",
        ),
        RuleSelector(
            scope="country",
            code="US_PACKSAFE_MD",
            item_name_contains=("Portable Electronic Devices, Containing Batteries",),
            reason_codes=("DG_US_PACKSAFE_PED",),
            layer_kind="dangerous_goods",
        ),
    ),
    "dry_ice": (
        RuleSelector(
            scope="international",
            code="IATA",
            item_name_contains=("Dry ice",),
            reason_codes=("DG_IATA_DRYICE",),
            layer_kind="dangerous_goods",
            badges=("≤2.5kg",),
        ),
        RuleSelector(
            scope="country",
            code="US_PACKSAFE_MD",
            item_name_contains=("Dry Ice",),
            reason_codes=("DG_US_PACKSAFE_DRYICE",),
            layer_kind="dangerous_goods",
        ),
    ),
    "e_cigarette_device": (
        RuleSelector(
            scope="international",
            code="IATA",
            item_name_contains=("Electronic cigarettes",),
            reason_codes=("DG_IATA_ECIG",),
            layer_kind="dangerous_goods",
        ),
        RuleSelector(
            scope="country",
            code="US_PACKSAFE_MD",
            item_name_contains=("Electronic Cigarettes, Vaping Devices",),
            reason_codes=("DG_US_PACKSAFE_ECIG",),
            layer_kind="dangerous_goods",
        ),
    ),
    "lighter": (
        RuleSelector(
            scope="international",
            code="IATA",
            item_name_contains=("Hair-styling equipment with hydrocarbon gas cartridge",),
            reason_codes=("DG_IATA_LIGHTER",),
            layer_kind="dangerous_goods",
        ),
        RuleSelector(
            scope="country",
            code="US_TSA",
            item_name_contains=("Lighters",),
            reason_codes=("SEC_US_LIGHTER",),
            layer_kind="security",
            applies_to_checked=False,
            requires_security_country=("US",),
        ),
    ),
    "knife": (
        RuleSelector(
            scope="country",
            code="KR",
            item_category="prohibited",
            reason_codes=("SEC_KR_KNIFE",),
            layer_kind="security",
            applies_to_checked=False,
            requires_security_country=("KR",),
            badges=("Declare at counter",),
        ),
        RuleSelector(
            scope="country",
            code="US_TSA",
            item_name_contains=("Knives",),
            reason_codes=("SEC_US_KNIFE",),
            layer_kind="security",
            applies_to_checked=False,
            requires_security_country=("US",),
        ),
    ),
}


def get_selectors(canonical: str) -> Sequence[RuleSelector]:
    return CANONICAL_RULE_SELECTORS.get(canonical, ())


def build_airline_selectors(airline_codes: Iterable[str]) -> list[RuleSelector]:
    selectors: list[RuleSelector] = []
    for code in airline_codes:
        upper = code.upper()
        selectors.append(
            RuleSelector(
                scope="airline",
                code=upper,
                item_category="carry_on",
                reason_codes=(f"AIR_{upper}_CARRYON_LIMIT",),
                layer_kind="airline",
                applies_to_checked=False,
            )
        )
        selectors.append(
            RuleSelector(
                scope="airline",
                code=upper,
                item_category="checked",
                reason_codes=(f"AIR_{upper}_CHECKED_ALLOW",),
                layer_kind="airline",
                applies_to_carry_on=False,
            )
        )
    return selectors


__all__ = [
    "RuleSelector",
    "CANONICAL_RULE_SELECTORS",
    "DEFAULT_LAYER_BY_SCOPE",
    "build_airline_selectors",
    "get_selectors",
]

