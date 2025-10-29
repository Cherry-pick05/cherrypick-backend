from datetime import datetime, date

from sqlalchemy import TIMESTAMP, String, BigInteger, ForeignKey, Date, Index, func
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
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_trips_user_id", "user_id"),
        Index("ix_trips_country_airline", "country_code2", "airline_code"),
    )

