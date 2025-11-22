from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import DeviceAuthContext
from app.api.items import SaveItemRequest, save_item
from app.db.base import Base
from app.db.models import Bag, BagItem, RegulationMatch, User
from app.schemas.preview import PreviewResponse, ResolvedInfo
from app.schemas.trip import TripCreate, TripSegmentInput
from app.services.trip_service import TripService


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def _make_auth(user: User) -> DeviceAuthContext:
    return DeviceAuthContext(user=user, token={"uid": user.user_id, "du": user.device_uuid})


def _create_user(session: Session) -> User:
    user = User(device_uuid="test-device")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _create_trip(session: Session, auth: DeviceAuthContext) -> tuple[TripService, int]:
    service = TripService(session, auth)
    payload = TripCreate(
        title="테스트 여행",
        from_airport="ICN",
        to_airport="JFK",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 10),
        segments=[TripSegmentInput(leg="ICN-JFK", operating="KE", cabin_class="YL")],
    )
    detail = service.create_trip(payload)
    return service, detail.trip_id


def test_trip_creation_creates_default_bags(db_session: Session) -> None:
    user = _create_user(db_session)
    auth = _make_auth(user)

    _, trip_id = _create_trip(db_session, auth)

    bags = db_session.scalars(select(Bag).where(Bag.trip_id == trip_id)).all()
    assert len(bags) == 2
    assert {bag.bag_type for bag in bags} == {"carry_on", "checked"}
    assert all(bag.is_default for bag in bags)


def test_save_item_creates_bag_item_and_match(db_session: Session) -> None:
    user = _create_user(db_session)
    auth = _make_auth(user)
    _, trip_id = _create_trip(db_session, auth)

    bag = db_session.scalar(
        select(Bag).where(Bag.trip_id == trip_id, Bag.bag_type == "carry_on")
    )
    assert bag is not None

    preview = PreviewResponse(
        resolved=ResolvedInfo(label="Laptop", canonical="electronics"),
        engine=None,
        narration=None,
        ai_tips=[],
        flags={},
    )

    request = SaveItemRequest(
        req_id="req-123",
        preview=preview,
        bag_id=bag.bag_id,
        trip_id=trip_id,
    )

    result = save_item(req=request, db=db_session, auth=auth)
    assert result["saved"] is True
    assert "bag_item_id" in result

    bag_item = db_session.get(BagItem, result["bag_item_id"])
    assert bag_item is not None
    assert bag_item.trip_id == trip_id
    assert bag_item.bag_id == bag.bag_id
    assert bag_item.preview_snapshot["preview_response"]["resolved"]["label"] == "Laptop"

    reg_match = db_session.get(RegulationMatch, result["match_id"])
    assert reg_match is not None
    assert reg_match.trip_id == trip_id

