from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

_PK_COUNTER = 1


def _next_id() -> int:
    global _PK_COUNTER
    value = _PK_COUNTER
    _PK_COUNTER += 1
    return value

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    Applicability,
    Base,
    ConstraintsQuant,
    ItemRule,
    RuleSet,
)
from app.schemas.decision import RuleEngineRequest
from app.services.rule_engine import RuleEngine


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_cosmetics_liquid_merges_security_and_airline(db_session: Session) -> None:
    _seed_security_rule(db_session, code="KR")
    _seed_security_rule(db_session, code="CN")
    _seed_airline_rule(db_session, code="KE")

    engine = RuleEngine(db_session)
    payload = RuleEngineRequest(
        canonical="cosmetics_liquid",
        req_id="test-cosmetics",
        itinerary={"from": "ICN", "to": "LAX", "via": ["PVG"], "rescreening": True},
        segments=[{"leg": "ICN-PVG", "operating": "KE", "cabin_class": "economy"}],
        item_params={"volume_ml": 150},
    )

    result = engine.evaluate(payload)

    assert result.conditions == {
        "max_container_ml": 100,
        "max_total_bag_l": 1.0,
        "zip_bag_1l": True,
        "steb_required": False,
    }
    assert [(source.layer, source.code) for source in result.sources] == [
        ("country_security", "KR"),
        ("country_security", "CN"),
        ("airline", "KE"),
    ]
    assert result.decision.carry_on.badges == sorted(
        ["100ml", "1L zip bag", "1pc", "10kg", "115cm"]
    )
    assert result.decision.carry_on.reason_codes == sorted(
        ["AIR_KE_CARRYON_LIMIT", "SEC_CN_LAGS", "SEC_KR_LAGS"]
    )
    assert result.decision.checked.badges == sorted(["2pc", "23kg"])
    assert result.decision.checked.reason_codes == ["AIR_KE_CHECKED_ALLOW"]
    assert len(result.trace) == 4


def test_cosmetics_liquid_without_rescreening_excludes_countries(db_session: Session) -> None:
    _seed_security_rule(db_session, code="KR")
    _seed_security_rule(db_session, code="CN")
    _seed_airline_rule(db_session, code="KE")

    engine = RuleEngine(db_session)
    payload = RuleEngineRequest(
        canonical="cosmetics_liquid",
        req_id="test-no-rescreen",
        itinerary={"from": "ICN", "to": "LAX", "via": ["PVG"], "rescreening": False},
        segments=[{"leg": "ICN-PVG", "operating": "KE", "cabin_class": "economy"}],
    )

    result = engine.evaluate(payload)

    assert [(source.layer, source.code) for source in result.sources] == [
        ("country_security", "KR"),
        ("airline", "KE"),
    ]


def test_cosmetics_liquid_via_japan_orders_security(db_session: Session) -> None:
    _seed_security_rule(db_session, code="KR")
    _seed_security_rule(db_session, code="JP")
    _seed_airline_rule(db_session, code="KE")

    engine = RuleEngine(db_session)
    payload = RuleEngineRequest(
        canonical="cosmetics_liquid",
        req_id="test-japan",
        itinerary={"from": "ICN", "to": "LAX", "via": ["NRT"], "rescreening": True},
        segments=[{"leg": "ICN-NRT", "operating": "KE", "cabin_class": "economy"}],
    )

    result = engine.evaluate(payload)

    assert [(source.layer, source.code) for source in result.sources] == [
        ("country_security", "KR"),
        ("country_security", "JP"),
        ("airline", "KE"),
    ]


def test_aerosol_uses_dg_limits_when_no_security(db_session: Session) -> None:
    _seed_pack_safe_aerosol_rule(db_session)

    engine = RuleEngine(db_session)
    payload = RuleEngineRequest(
        canonical="aerosol",
        req_id="test-aerosol",
        itinerary={"from": "SYD", "to": "LAX", "via": [], "rescreening": False},
        segments=[],
    )

    result = engine.evaluate(payload)

    assert result.conditions["max_container_ml"] == 500
    assert result.conditions["max_total_bag_l"] == 2.0
    assert "DG_US_AEROSOL_FLAMMABLE" in result.decision.carry_on.reason_codes
    assert [(source.layer, source.code) for source in result.sources] == [
        ("dangerous_goods", "US_PACKSAFE_MD")
    ]


def test_lithium_spare_denies_checked_baggage(db_session: Session) -> None:
    _seed_lithium_rules(db_session)

    engine = RuleEngine(db_session)
    payload = RuleEngineRequest(
        canonical="lithium_ion_battery_spare",
        req_id="test-lithium",
        itinerary={"from": "SYD", "to": "LAX", "via": [], "rescreening": False},
        segments=[],
    )

    result = engine.evaluate(payload)

    assert result.decision.carry_on.status == "limit"
    assert result.decision.checked.status == "deny"
    assert "DG_IATA_SPARE_LIION" in result.decision.carry_on.reason_codes


def _seed_security_rule(session: Session, code: str) -> None:
    rule_set = _create_rule_set(session, scope="country", code=code)
    item_rule = ItemRule(
        id=_next_id(),
        rule_set_id=rule_set.id,
        item_category="restricted_liquids",
        severity="warn",
        item_name=f"{code} LAGs",
    )
    session.add(item_rule)
    session.flush()
    applicability = Applicability(id=_next_id(), item_rule_id=item_rule.id)
    session.add(applicability)
    session.flush()
    constraint = ConstraintsQuant(
        id=_next_id(),
        applicability_id=applicability.id,
        max_container_ml=100,
        max_total_bag_l=1.0,
        carry_on_allowed=1,
        checked_allowed=1,
        ext={"bag_type": "transparent_ziplock"},
    )
    session.add(constraint)
    session.commit()


def _seed_airline_rule(session: Session, code: str) -> None:
    rule_set = _create_rule_set(session, scope="airline", code=code)

    carry_rule = ItemRule(
        id=_next_id(),
        rule_set_id=rule_set.id,
        item_category="carry_on",
        severity="warn",
        item_name=f"{code} carry-on",
    )
    session.add(carry_rule)
    session.flush()
    carry_app = Applicability(
        id=_next_id(), item_rule_id=carry_rule.id, cabin_class="economy"
    )
    session.add(carry_app)
    session.flush()
    carry_constraint = ConstraintsQuant(
        id=_next_id(),
        applicability_id=carry_app.id,
        max_pieces=1,
        max_weight_kg=10,
        max_total_cm=115,
        carry_on_allowed=1,
        checked_allowed=1,
        ext={},
    )
    session.add(carry_constraint)

    checked_rule = ItemRule(
        id=_next_id(),
        rule_set_id=rule_set.id,
        item_category="checked",
        severity="warn",
        item_name=f"{code} checked",
    )
    session.add(checked_rule)
    session.flush()
    checked_app = Applicability(
        id=_next_id(), item_rule_id=checked_rule.id, cabin_class="economy"
    )
    session.add(checked_app)
    session.flush()
    checked_constraint = ConstraintsQuant(
        id=_next_id(),
        applicability_id=checked_app.id,
        max_pieces=2,
        max_weight_kg=23,
        carry_on_allowed=1,
        checked_allowed=1,
        ext={},
    )
    session.add(checked_constraint)
    session.commit()


def _seed_pack_safe_aerosol_rule(session: Session) -> None:
    rule_set = _create_rule_set(session, scope="country", code="US_PACKSAFE_MD")
    item_rule = ItemRule(
        id=_next_id(),
        rule_set_id=rule_set.id,
        item_category="tsa_restriction",
        severity="warn",
        item_name="Aerosols, Flammable",
    )
    session.add(item_rule)
    session.flush()
    app = Applicability(id=_next_id(), item_rule_id=item_rule.id)
    session.add(app)
    session.flush()
    constraint = ConstraintsQuant(
        id=_next_id(),
        applicability_id=app.id,
        max_container_ml=500,
        max_total_bag_l=2.0,
        carry_on_allowed=1,
        checked_allowed=1,
        ext={},
    )
    session.add(constraint)
    session.commit()


def _seed_lithium_rules(session: Session) -> None:
    iata = _create_rule_set(session, scope="international", code="IATA")
    iata_rule = ItemRule(
        id=_next_id(),
        rule_set_id=iata.id,
        item_category="hazardous_materials",
        severity="warn",
        item_name="Spare/loose batteries",
    )
    session.add(iata_rule)
    session.flush()
    iata_app = Applicability(id=_next_id(), item_rule_id=iata_rule.id)
    session.add(iata_app)
    session.flush()
    iata_constraint = ConstraintsQuant(
        id=_next_id(),
        applicability_id=iata_app.id,
        max_pieces=20,
        lithium_ion_max_wh=100,
        carry_on_allowed=1,
        checked_allowed=0,
        ext={},
    )
    session.add(iata_constraint)

    pack_safe = _create_rule_set(session, scope="country", code="US_PACKSAFE_MD")
    pack_rule = ItemRule(
        id=_next_id(),
        rule_set_id=pack_safe.id,
        item_category="tsa_restriction",
        severity="warn",
        item_name="Batteries, Lithium",
    )
    session.add(pack_rule)
    session.flush()
    pack_app = Applicability(id=_next_id(), item_rule_id=pack_rule.id)
    session.add(pack_app)
    session.flush()
    pack_constraint = ConstraintsQuant(
        id=_next_id(),
        applicability_id=pack_app.id,
        carry_on_allowed=1,
        checked_allowed=0,
        max_pieces=2,
        ext={},
    )
    session.add(pack_constraint)
    session.commit()


def _create_rule_set(session: Session, scope: str, code: str) -> RuleSet:
    rule_set = RuleSet(
        id=_next_id(),
        scope=scope,
        code=code,
        name=f"{scope}-{code}",
        imported_at=datetime.utcnow(),
    )
    session.add(rule_set)
    session.flush()
    return rule_set

