from datetime import datetime

from sqlalchemy import TIMESTAMP, String, BigInteger, Text, Enum, JSON, Index, func, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RegulationRule(Base):
    __tablename__ = "regulation_rules"

    rule_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scope: Mapped[str | None] = mapped_column(Enum("country", "airline", name="rule_scope"))
    code: Mapped[str | None] = mapped_column(String(20))
    item_category: Mapped[str | None] = mapped_column(String(50))
    constraints: Mapped[dict | None] = mapped_column(JSON)
    severity: Mapped[str | None] = mapped_column(Enum("info", "warn", "block", name="rule_severity"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("uq_rules_scope_code_cat", "scope", "code", "item_category", unique=True),
        Index("ix_rules_scope_code", "scope", "code"),
    )


class RegulationMatch(Base):
    __tablename__ = "regulation_matches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    status: Mapped[str | None] = mapped_column(Enum("allow", "ban", "limited", name="match_status"))
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    trip_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("trips.trip_id"))
    image_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("item_images.image_id"))
    rule_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("regulation_rules.rule_id"))
    details: Mapped[dict | None] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    source: Mapped[str | None] = mapped_column(Enum("detect", "ocr", "manual", name="match_source"))
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    matched_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index("ix_matches_user_trip_time", "user_id", "trip_id", "matched_at"),
    )

