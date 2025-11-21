from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Country(Base):
    __tablename__ = "countries"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    iso3_code: Mapped[str | None] = mapped_column(String(3))
    name_en: Mapped[str] = mapped_column(String(120))
    name_ko: Mapped[str] = mapped_column(String(120))
    region_group: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=False), server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=False), server_default=sa.func.now(), onupdate=sa.func.now()
    )

    airports: Mapped[list["Airport"]] = relationship(
        "Airport", back_populates="country", cascade="all, delete-orphan"
    )

    __table_args__ = (
        sa.Index("ix_countries_name_en", "name_en"),
        sa.Index("ix_countries_name_ko", "name_ko"),
    )


