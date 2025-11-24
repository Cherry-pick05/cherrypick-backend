from __future__ import annotations

from datetime import date
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import DeviceAuthContext
from app.api.items import SaveItemRequest, save_item
from app.db.base import Base
from app.db.models import Bag, BagItem, RegulationMatch, User
from app.schemas.checklist import BagItemUpdate
from app.schemas.preview import PreviewResponse, ResolvedInfo
from app.schemas.trip import TripCreate, TripSegmentInput
from app.services.bag_service import BagService
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


def _get_bag(session: Session, trip_id: int, bag_type: str) -> Bag:
    bag = session.scalar(select(Bag).where(Bag.trip_id == trip_id, Bag.bag_type == bag_type))
    assert bag is not None, f"{bag_type} bag missing"
    return bag


def _save_preview_item(
    session: Session,
    auth: DeviceAuthContext,
    bag: Bag,
    trip_id: int,
    label: str,
) -> BagItem:
    preview = PreviewResponse(
        resolved=ResolvedInfo(label=label, canonical=label),
        engine=None,
        narration=None,
        ai_tips=[],
        flags={},
    )
    request = SaveItemRequest(
        req_id=f"req-{label}-{uuid.uuid4().hex[:6]}",
        preview=preview,
        bag_id=bag.bag_id,
        trip_id=trip_id,
    )
    result = save_item(req=request, db=session, auth=auth)
    item = session.get(BagItem, result["bag_item_id"])
    assert item is not None
    return item


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


def test_trip_access_guard_blocks_other_users(db_session: Session) -> None:
    user_owner = _create_user(db_session)
    auth_owner = _make_auth(user_owner)
    _, trip_id = _create_trip(db_session, auth_owner)

    other_user = User(device_uuid="other-device")
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)

    other_auth = _make_auth(other_user)
    service_other = TripService(db_session, other_auth)

    with pytest.raises(HTTPException) as excinfo:
        service_other.get_trip_detail(trip_id)
    assert excinfo.value.status_code == 403


def test_bag_items_pagination_and_updates(db_session: Session) -> None:
    user = _create_user(db_session)
    auth = _make_auth(user)
    _, trip_id = _create_trip(db_session, auth)

    carry_on = _get_bag(db_session, trip_id, "carry_on")
    checked = _get_bag(db_session, trip_id, "checked")

    items = [_save_preview_item(db_session, auth, carry_on, trip_id, f"item-{idx}") for idx in range(3)]

    bag_service = BagService(db_session, auth)
    page1 = bag_service.list_items(carry_on.bag_id, limit=2, offset=0)
    assert len(page1.items) == 2
    assert page1.has_more is True
    assert page1.next_offset == 2

    page2 = bag_service.list_items(carry_on.bag_id, limit=2, offset=2)
    assert len(page2.items) == 1
    assert page2.has_more is False
    assert page2.next_offset is None

    target_item_id = page1.items[0].item_id
    updated = bag_service.update_item(
        target_item_id,
        BagItemUpdate(bag_id=checked.bag_id, status="packed"),
    )
    assert updated.status == "packed"
    assert updated.bag_id == checked.bag_id

    db_item = db_session.get(BagItem, target_item_id)
    assert db_item is not None
    assert db_item.status == "packed"
    assert db_item.bag_id == checked.bag_id


def test_trip_delete_cascades_bags_and_items(db_session: Session) -> None:
    user = _create_user(db_session)
    auth = _make_auth(user)
    service, trip_id = _create_trip(db_session, auth)
    carry_on = _get_bag(db_session, trip_id, "carry_on")
    _save_preview_item(db_session, auth, carry_on, trip_id, "camera")

    service.delete_trip(trip_id, purge=True)

    assert (
        db_session.scalar(select(func.count()).select_from(Bag).where(Bag.trip_id == trip_id)) == 0
    )
    assert (
        db_session.scalar(select(func.count()).select_from(BagItem).where(BagItem.trip_id == trip_id)) == 0
    )


def test_delete_bag_item_removes_record(db_session: Session) -> None:
    user = _create_user(db_session)
    auth = _make_auth(user)
    _, trip_id = _create_trip(db_session, auth)

    carry_on = _get_bag(db_session, trip_id, "carry_on")
    item = _save_preview_item(db_session, auth, carry_on, trip_id, "umbrella")
    assert db_session.get(BagItem, item.item_id) is not None

    service = BagService(db_session, auth)
    service.delete_item(item.item_id)

    assert db_session.get(BagItem, item.item_id) is None

