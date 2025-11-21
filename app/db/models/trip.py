from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Index,
    JSON,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Trip(Base):
    __tablename__ = "trips"

    trip_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str | None] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(Text)
    from_airport: Mapped[str | None] = mapped_column(String(3))
    to_airport: Mapped[str | None] = mapped_column(String(3))
    country_from: Mapped[str | None] = mapped_column(String(2))
    country_to: Mapped[str | None] = mapped_column(String(2))
    route_type: Mapped[str | None] = mapped_column(Enum("domestic", "international", name="trip_route_type"))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, server_default=sa.false())
    tags_json: Mapped[dict | list | None] = mapped_column(JSON)
    archived_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_trips_user_id", "user_id"),
        Index("ix_trips_active", "user_id", "active"),
        Index("ix_trips_archived_at", "user_id", "archived_at"),
    )

    segments: Mapped[list["TripSegment"]] = relationship(
        back_populates="trip",
        cascade="all, delete-orphan",
        order_by="TripSegment.segment_order",
    )
    via_airports: Mapped[list["TripViaAirport"]] = relationship(
        back_populates="trip",
        cascade="all, delete-orphan",
        order_by="TripViaAirport.via_order",
    )


class TripSegment(Base):
    __tablename__ = "trip_segments"

    segment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("trips.trip_id", ondelete="CASCADE"))
    segment_order: Mapped[int] = mapped_column(SmallInteger)
    direction: Mapped[str] = mapped_column(String(16))  # 'outbound' or 'return'
    departure_airport: Mapped[str] = mapped_column(String(3))
    arrival_airport: Mapped[str] = mapped_column(String(3))
    departure_country: Mapped[str] = mapped_column(String(2))
    arrival_country: Mapped[str] = mapped_column(String(2))
    operating_airline: Mapped[str | None] = mapped_column(String(8))
    cabin_class: Mapped[str | None] = mapped_column(String(32))
    departure_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    trip: Mapped["Trip"] = relationship(back_populates="segments")

    __table_args__ = (
        Index("ix_trip_segments_trip_order", "trip_id", "segment_order"),
        Index("ix_trip_segments_direction", "trip_id", "direction"),
    )


class TripViaAirport(Base):
    __tablename__ = "trip_via_airports"

    via_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("trips.trip_id", ondelete="CASCADE"))
    airport_code: Mapped[str] = mapped_column(String(3))
    via_order: Mapped[int] = mapped_column(SmallInteger)
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now())

    trip: Mapped["Trip"] = relationship(back_populates="via_airports")

    __table_args__ = (
        Index("ix_trip_via_airports_trip_order", "trip_id", "via_order"),
    )

