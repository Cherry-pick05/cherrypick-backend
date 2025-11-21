from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Airport(Base):
    __tablename__ = "airports"

    airport_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    iata_code: Mapped[str] = mapped_column(String(3), nullable=False, unique=True)
    icao_code: Mapped[str | None] = mapped_column(String(4))
    name_en: Mapped[str] = mapped_column(String(150))
    name_ko: Mapped[str | None] = mapped_column(String(150))
    city_en: Mapped[str | None] = mapped_column(String(120))
    city_ko: Mapped[str | None] = mapped_column(String(120))
    country_code: Mapped[str] = mapped_column(
        String(2), ForeignKey("countries.code", ondelete="CASCADE"), nullable=False
    )
    region_group: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=False), server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=False), server_default=sa.func.now(), onupdate=sa.func.now()
    )

    country: Mapped["Country"] = relationship("Country", back_populates="airports")

    __table_args__ = (
        sa.Index("ix_airports_country_code", "country_code"),
        sa.Index("ix_airports_name_en", "name_en"),
        sa.Index("ix_airports_name_ko", "name_ko"),
    )


