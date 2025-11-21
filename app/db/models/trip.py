from datetime import datetime, date

from sqlalchemy import TIMESTAMP, String, BigInteger, ForeignKey, Date, Index, func, SmallInteger, Boolean
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Trip(Base):
    __tablename__ = "trips"

    trip_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    city: Mapped[str | None] = mapped_column(String(80))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    country_code2: Mapped[str] = mapped_column(String(2))
    airline_code: Mapped[str | None] = mapped_column(String(8))
    has_rescreening: Mapped[bool | None] = mapped_column(Boolean, server_default=sa.false())
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_trips_user_id", "user_id"),
        Index("ix_trips_country_airline", "country_code2", "airline_code"),
    )

    segments: Mapped[list["TripSegment"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan", order_by="TripSegment.segment_order"
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

