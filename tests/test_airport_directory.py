from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.reference import list_airports, list_countries
from app.db.base import Base
from app.db.models.airport import Airport
from app.db.models.country import Country
from app.db.models.user import User
from app.schemas.trip import TripCreate, TripSegmentInput
from app.services.airport_directory import (
    AirportDirectoryService,
    AirportDirectorySynchronizer,
    CountryDirectoryService,
)
from app.services.airport_lookup import (
    reset_airport_directory_session_factory,
    set_airport_directory_session_factory,
)
from app.services.trip_service import TripService


class _FakeMolitClient:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def iter_rows(self, per_page: int = 1000):
        yield from self._rows


@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, future=True)


@pytest.fixture()
def db_session(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def override_airport_lookup_session(session_factory):
    set_airport_directory_session_factory(session_factory)
    try:
        yield
    finally:
        reset_airport_directory_session_factory()


def _seed_directory(session: Session) -> None:
    session.add_all(
        [
            Country(code="KR", name_en="Korea", name_ko="대한민국", region_group="아시아"),
            Country(code="US", name_en="United States", name_ko="미국", region_group="북미"),
        ]
    )
    session.flush()
    session.add_all(
        [
            Airport(
                iata_code="ICN",
                icao_code="RKSI",
                name_en="Incheon International Airport",
                name_ko="인천국제공항",
                city_en="Seoul",
                country_code="KR",
                region_group="아시아",
            ),
            Airport(
                iata_code="JFK",
                icao_code="KJFK",
                name_en="John F. Kennedy International Airport",
                name_ko="존 에프 케네디 국제공항",
                city_en="New York",
                country_code="US",
                region_group="북미",
            ),
        ]
    )
    session.commit()


def test_synchronizer_loads_directory(db_session: Session):
    fake_rows = [
        {
            "공항코드1(IATA)": "ICN",
            "공항코드2(ICAO)": "RKSI",
            "영문공항명": "Incheon International Airport",
            "영문국가명": "Korea",
            "영문도시명": "Seoul",
            "지역": "아시아",
            "한글공항": "인천국제공항",
            "한글국가명": "대한민국",
        },
        {
            "공항코드1(IATA)": "JFK",
            "공항코드2(ICAO)": "KJFK",
            "영문공항명": "John F. Kennedy International Airport",
            "영문국가명": "United States",
            "영문도시명": "New York",
            "지역": "북미",
            "한글공항": "존 에프 케네디 국제공항",
            "한글국가명": "미국",
        },
    ]

    sync = AirportDirectorySynchronizer(db_session, client=_FakeMolitClient(fake_rows))
    result = sync.run()

    assert result.country_count == 2
    assert result.airport_count == 2
    assert result.skipped_airports == 0

    countries = db_session.scalars(select(Country)).all()
    assert {c.code for c in countries} == {"KR", "US"}

    country_service = CountryDirectoryService(db_session)
    assert country_service.search(q="대한")[0]["code"] == "KR"

    airport_service = AirportDirectoryService(db_session)
    airports = airport_service.search(q="kennedy", limit=5)
    assert airports[0]["iata_code"] == "JFK"


def test_reference_handlers_filter_results(session_factory):
    with session_factory() as session:
        _seed_directory(session)
        countries = list_countries(q="kor", region=None, db=session, auth=None)
        assert countries.items[0].code == "KR"

        airports = list_airports(
            q=None,
            country_code="US",
            limit=5,
            db=session,
            auth=None,
        )
        assert [item.iata_code for item in airports.items] == ["JFK"]


def test_trip_service_assigns_countries(db_session: Session):
    _seed_directory(db_session)

    user = User(user_id=1, device_uuid="test-device")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    class _Auth:
        def __init__(self, user_obj):
            self.user = user_obj
            self.token = {}

    service = TripService(db_session, auth=_Auth(user))
    payload = TripCreate(
        title="서울-뉴욕",
        from_airport="ICN",
        to_airport="JFK",
        segments=[TripSegmentInput(leg="ICN-JFK")],
    )

    trip = service.create_trip(payload)

    assert trip.itinerary.from_airport == "ICN"
    assert trip.itinerary.to_airport == "JFK"
    assert trip.itinerary.route_type == "international"


def test_trip_service_rejects_unknown_airport(db_session: Session):
    _seed_directory(db_session)

    user = User(user_id=1, device_uuid="test-device")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    class _Auth:
        def __init__(self, user_obj):
            self.user = user_obj
            self.token = {}

    service = TripService(db_session, auth=_Auth(user))
    payload = TripCreate(
        title="Invalid Trip",
        from_airport="ZZZ",
        to_airport="ICN",
        segments=[TripSegmentInput(leg="ICN-JFK")],
    )

    with pytest.raises(HTTPException) as exc:
        service.create_trip(payload)
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "airport_not_found"


