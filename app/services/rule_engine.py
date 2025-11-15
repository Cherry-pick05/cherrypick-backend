"""Deterministic regulation rule engine."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterable, List, Literal, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.regulation import Applicability, ConstraintsQuant, ItemRule, RuleSet
from app.schemas.decision import (
    DecisionPayload,
    DecisionSlot,
    RuleEngineRequest,
    RuleEngineResponse,
    SourceEntry,
    TraceEntry,
)
from app.services.airport_lookup import get_country_code, get_region_bucket
from app.services.rule_engine_config import (
    DEFAULT_LAYER_BY_SCOPE,
    RuleSelector,
    build_airline_selectors,
    get_selectors,
)

DecisionStatus = Literal["allow", "limit", "deny"]


# Ordered severity for carry-on / checked determination
STATUS_ORDER: dict[str, int] = {"deny": 3, "limit": 2, "allow": 1}
MIN_CONDITION_KEYS = {
    "max_container_ml",
    "max_total_bag_l",
    "max_wh",
    "max_count",
    "max_weight_kg",
}
BOOL_CONDITION_KEYS = {
    "airline_approval",
    "steb_required",
    "zip_bag_1l",
}


@dataclass(slots=True)
class RuleRecord:
    selector: RuleSelector
    rule_set: RuleSet
    item_rule: ItemRule
    applicability: Applicability
    constraint: ConstraintsQuant


class ItineraryContext:
    def __init__(self, payload: RuleEngineRequest):
        self.origin = payload.itinerary.origin.upper()
        self.destination = payload.itinerary.destination.upper()
        self.via = [code.upper() for code in payload.itinerary.via]
        self.rescreening = payload.itinerary.rescreening

        self.origin_country = get_country_code(self.origin)
        self.destination_country = get_country_code(self.destination)
        self.via_countries = [get_country_code(code) for code in self.via]
        self.countries = [c for c in [self.origin_country, *self.via_countries, self.destination_country] if c]

        self.route_type = self._derive_route_type()
        self.region_path = self._derive_regions()
        self.security_airports = [self.origin]
        if self.rescreening:
            self.security_airports.extend(self.via)
        self.security_countries: list[str] = []
        for airport in self.security_airports:
            iso = get_country_code(airport)
            if iso:
                self.security_countries.append(iso)
        self._security_country_set = {code.upper() for code in self.security_countries}

        self.cabin_classes = {
            seg.cabin_class.lower()
            for seg in payload.segments
            if seg.cabin_class
        }
        self.airlines = sorted({seg.operating.upper() for seg in payload.segments if seg.operating})
        self.duty_free = payload.duty_free
        self.item_params = payload.item_params

    def _derive_route_type(self) -> str:
        if not self.origin_country or not self.destination_country:
            return "international"
        return "domestic" if self.origin_country == self.destination_country else "international"

    def _derive_regions(self) -> list[str]:
        regions = []
        for code in [self.origin, *self.via, self.destination]:
            bucket = get_region_bucket(code)
            if bucket and bucket not in regions:
                regions.append(bucket)
        return regions or ["international_non_americas"]

    def matches_route(self, rule_route: str | None) -> bool:
        if not rule_route:
            return True
        return rule_route == self.route_type

    def matches_region(self, region: str | None) -> bool:
        if not region:
            return True
        return region in self.region_path

    def matches_cabin(self, cabin: str | None) -> bool:
        if not cabin:
            return True
        return cabin.lower() in self.cabin_classes

    def has_security_country(self, iso_code: str) -> bool:
        if not iso_code:
            return False
        return iso_code.upper() in self._security_country_set

    def should_enforce_steb(self, layer_kind: str | None) -> bool:
        return bool(self.duty_free.is_df and self.rescreening and layer_kind == "security")


@dataclass(slots=True)
class RuleEffect:
    selector: RuleSelector
    record: RuleRecord
    carry_status: DecisionStatus | None
    checked_status: DecisionStatus | None
    carry_badges: set[str]
    checked_badges: set[str]
    reason_codes: set[str]
    constraints_used: dict[str, Any]
    expose_conditions: bool = True

    @property
    def layer(self) -> str:
        return self.selector.layer or DEFAULT_LAYER_BY_SCOPE.get(self.record.rule_set.scope, self.record.rule_set.scope)


class DecisionAccumulator:
    def __init__(self, req_id: str, canonical: str):
        self.req_id = req_id
        self.canonical = canonical
        self.carry_status: DecisionStatus = "allow"
        self.checked_status: DecisionStatus = "allow"
        self.carry_badges: set[str] = set()
        self.checked_badges: set[str] = set()
        self.carry_reasons: list[str] = []
        self.checked_reasons: list[str] = []
        self.conditions: dict[str, Any] = {}
        self.sources: list[SourceEntry] = []
        self.trace: list[TraceEntry] = []

    def apply(self, effect: RuleEffect) -> None:
        if effect.carry_status:
            self.carry_status = self._merge_status(self.carry_status, effect.carry_status)
            self.carry_badges.update(effect.carry_badges)
            self._extend_unique(self.carry_reasons, effect.reason_codes)
        if effect.checked_status:
            self.checked_status = self._merge_status(self.checked_status, effect.checked_status)
            self.checked_badges.update(effect.checked_badges)
            self._extend_unique(self.checked_reasons, effect.reason_codes)

        if effect.expose_conditions:
            for key, value in effect.constraints_used.items():
                self._merge_condition(key, value)

        source_key = (effect.layer, effect.record.rule_set.code)
        if not any(s.layer == source_key[0] and s.code == source_key[1] for s in self.sources):
            self.sources.append(SourceEntry(layer=source_key[0], code=source_key[1]))

        self.trace.append(
            TraceEntry(
                rule_id=effect.record.item_rule.id,
                layer=effect.layer,
                code=effect.record.rule_set.code,
                item_category=effect.record.item_rule.item_category,
                effect={
                    "carry_on": effect.carry_status,
                    "checked": effect.checked_status,
                },
                applied=True,
                reason_codes=sorted(effect.reason_codes),
                constraints_used=effect.constraints_used,
            )
        )

    def _merge_status(self, current: DecisionStatus, new: DecisionStatus) -> DecisionStatus:
        return new if STATUS_ORDER[new] >= STATUS_ORDER[current] else current

    def _extend_unique(self, target: list[str], items: Iterable[str]) -> None:
        for item in items:
            if item not in target:
                target.append(item)

    def _merge_condition(self, key: str, value: Any) -> None:
        if value is None:
            return
        if key in MIN_CONDITION_KEYS:
            current = self.conditions.get(key)
            if current is None or (isinstance(current, (int, float)) and value < current):
                self.conditions[key] = value
        elif key in BOOL_CONDITION_KEYS:
            if value:
                self.conditions[key] = True
            else:
                self.conditions.setdefault(key, False)
        else:
            self.conditions[key] = value

    def build_response(self) -> RuleEngineResponse:
        return RuleEngineResponse(
            req_id=self.req_id,
            canonical=self.canonical,
            decision=DecisionPayload(
                carry_on=DecisionSlot(
                    status=self.carry_status,
                    badges=sorted(self.carry_badges),
                    reason_codes=self.carry_reasons,
                ),
                checked=DecisionSlot(
                    status=self.checked_status,
                    badges=sorted(self.checked_badges),
                    reason_codes=self.checked_reasons,
                ),
            ),
            conditions=self.conditions,
            sources=self.sources,
            trace=self.trace,
        )


class RuleEngine:
    """Main orchestration entrypoint."""

    def __init__(self, db: Session):
        self.db = db

    def evaluate(self, payload: RuleEngineRequest) -> RuleEngineResponse:
        req_id = payload.req_id or uuid.uuid4().hex
        accumulator = DecisionAccumulator(req_id=req_id, canonical=payload.canonical)
        ctx = ItineraryContext(payload)
        selectors = list(get_selectors(payload.canonical))
        selectors.extend(build_airline_selectors(ctx.airlines))
        if not selectors:
            return accumulator.build_response()

        records = self._collect_records(selectors, ctx)
        for record in records:
            effect = self._evaluate_record(record, ctx)
            if effect:
                accumulator.apply(effect)

        return accumulator.build_response()

    def _collect_records(self, selectors: Sequence[RuleSelector], ctx: ItineraryContext) -> list[RuleRecord]:
        records: list[RuleRecord] = []
        for selector in selectors:
            if not self._selector_applicable(selector, ctx):
                continue
            stmt = (
                select(RuleSet, ItemRule, Applicability, ConstraintsQuant)
                .join(ItemRule, ItemRule.rule_set_id == RuleSet.id)
                .join(Applicability, Applicability.item_rule_id == ItemRule.id)
                .join(ConstraintsQuant, ConstraintsQuant.applicability_id == Applicability.id)
                .where(RuleSet.scope == selector.scope, RuleSet.code == selector.code)
            )
            if selector.item_category:
                stmt = stmt.where(ItemRule.item_category == selector.item_category)
            results = self.db.execute(stmt).all()
            matched: list[RuleRecord] = []
            for rule_set, item_rule, applicability, constraint in results:
                if selector.item_name_contains:
                    name = item_rule.item_name or ""
                    lowered = name.lower()
                    if not all(fragment.lower() in lowered for fragment in selector.item_name_contains):
                        continue
                if not context_matches(applicability, ctx):
                    continue
                if not selector.matches_ext(constraint.ext):
                    continue
                matched.append(
                    RuleRecord(
                        selector=selector,
                        rule_set=rule_set,
                        item_rule=item_rule,
                        applicability=applicability,
                        constraint=constraint,
                    )
                )
                if selector.max_rules and len(matched) >= selector.max_rules:
                    break
            records.extend(matched)
        return records

    def _selector_applicable(self, selector: RuleSelector, ctx: ItineraryContext) -> bool:
        if selector.requires_rescreening and not ctx.rescreening:
            return False
        if selector.requires_security_country:
            if not any(ctx.has_security_country(code) for code in selector.requires_security_country):
                return False
        return True

    def _evaluate_record(self, record: RuleRecord, ctx: ItineraryContext) -> RuleEffect | None:
        constraint = record.constraint
        reason = set(record.selector.reason_codes)

        carry_status = compute_status(constraint.carry_on_allowed, record.item_rule.severity, constraint)
        checked_status = compute_status(constraint.checked_allowed, record.item_rule.severity, constraint)

        if record.selector.layer_kind == "airline":
            if record.item_rule.item_category == "carry_on":
                carry_status = "limit"
                checked_status = None
            elif record.item_rule.item_category == "checked":
                carry_status = None
                checked_status = "allow"

        if not record.selector.applies_to_carry_on:
            carry_status = None
        if not record.selector.applies_to_checked:
            checked_status = None

        carry_badges = set(record.selector.badges) if record.selector.applies_to_carry_on else set()
        checked_badges = set(record.selector.badges) if record.selector.applies_to_checked else set()
        conditions = extract_conditions(constraint, record.selector, ctx)
        expose_conditions = record.selector.layer_kind != "airline"

        return RuleEffect(
            selector=record.selector,
            record=record,
            carry_status=carry_status,
            checked_status=checked_status,
            carry_badges=carry_badges,
            checked_badges=checked_badges,
            reason_codes=reason,
            constraints_used=conditions,
            expose_conditions=expose_conditions,
        )


def context_matches(applicability: Applicability, ctx: ItineraryContext) -> bool:
    today = date.today()
    if applicability.effective_from and applicability.effective_from > today:
        return False
    if applicability.effective_until and applicability.effective_until < today:
        return False
    if not ctx.matches_route(applicability.route_type):
        return False
    if not ctx.matches_region(applicability.region):
        return False
    if not ctx.matches_cabin(applicability.cabin_class):
        return False
    return True


def compute_status(flag: int | None, severity: str, constraint: ConstraintsQuant) -> DecisionStatus | None:
    if flag is None:
        return None
    allowed = bool(flag)
    if not allowed or severity == "block":
        return "deny"
    has_conditions = any(
        getattr(constraint, attr) is not None
        for attr in (
            "max_container_ml",
            "max_total_bag_l",
            "lithium_ion_max_wh",
            "lithium_metal_g",
            "max_weight_kg",
            "max_pieces",
        )
    )
    if has_conditions or constraint.operator_approval_required:
        return "limit"
    return "allow"


def extract_conditions(constraint: ConstraintsQuant, selector: RuleSelector, ctx: ItineraryContext) -> dict[str, Any]:
    conditions: dict[str, Any] = {}
    security_layer = selector.layer_kind == "security"
    enforce_steb = ctx.should_enforce_steb(selector.layer_kind)

    def set_condition(key: str, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, float):
            value = round(value, 3)
        conditions[key] = value

    if constraint.max_container_ml is not None:
        set_condition("max_container_ml", int(constraint.max_container_ml))
    if constraint.max_total_bag_l is not None:
        total = float(constraint.max_total_bag_l)
        set_condition("max_total_bag_l", total)
        if security_layer and total <= 1.0:
            conditions["zip_bag_1l"] = True
    if constraint.lithium_ion_max_wh is not None:
        set_condition("max_wh", int(constraint.lithium_ion_max_wh))
    if constraint.max_pieces is not None:
        set_condition("max_count", int(constraint.max_pieces))
    if constraint.max_weight_kg is not None:
        set_condition("max_weight_kg", float(constraint.max_weight_kg))
    if constraint.operator_approval_required:
        conditions["airline_approval"] = True

    ext = constraint.ext or {}
    bag_type = ext.get("bag_type")
    if security_layer and isinstance(bag_type, str) and "zip" in bag_type.lower():
        conditions["zip_bag_1l"] = True

    intl_exc = ext.get("international_connection_exception")
    if enforce_steb and isinstance(intl_exc, dict) and intl_exc.get("steb_required"):
        conditions["steb_required"] = True
    elif enforce_steb and ext.get("steb_required"):
        conditions["steb_required"] = True

    if "max_spare_batteries" in ext and ext["max_spare_batteries"] is not None:
        set_condition("max_count", int(ext["max_spare_batteries"]))

    if selector.layer_kind == "security" and "steb_required" not in conditions:
        conditions["steb_required"] = False

    return conditions


__all__ = ["RuleEngine"]

