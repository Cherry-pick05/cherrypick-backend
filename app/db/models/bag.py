from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import TIMESTAMP, Boolean, Enum, ForeignKey, JSON, SmallInteger, String, Text, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import BIGINT


BagTypeEnum = Enum("carry_on", "checked", "custom", name="bag_type")
BagItemStatusEnum = Enum("todo", "packed", name="bag_item_status")


class BagItem(Base):
    __tablename__ = "bag_items"

    item_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    trip_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False)
    bag_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("bags.bag_id", ondelete="CASCADE"), nullable=False)
    regulation_match_id: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("regulation_matches.id", ondelete="SET NULL"),
    )
    title: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(BagItemStatusEnum, nullable=False, server_default="todo")
    quantity: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")
    note: Mapped[str | None] = mapped_column(Text)
    preview_snapshot: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now(),
    )

    bag: Mapped["Bag"] = relationship(
        "Bag",
        back_populates="items",
        foreign_keys=[bag_id],
    )
    regulation_match: Mapped["RegulationMatch"] = relationship(back_populates="bag_items")

    __table_args__ = (
        sa.ForeignKeyConstraint(
            ("bag_id", "trip_id"),
            ("bags.bag_id", "bags.trip_id"),
            name="fk_bag_items_bag_trip",
            ondelete="CASCADE",
        ),
        Index("ix_bag_items_bag_status", "bag_id", "status", "updated_at"),
        Index("ix_bag_items_user_updated", "user_id", "updated_at"),
    )


class Bag(Base):
    __tablename__ = "bags"

    bag_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    trip_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120))
    bag_type: Mapped[str] = mapped_column(BagTypeEnum, server_default="custom")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.false())
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now(),
    )

    trip: Mapped["Trip"] = relationship(back_populates="bags")
    items: Mapped[list[BagItem]] = relationship(
        "BagItem",
        back_populates="bag",
        cascade="all, delete-orphan",
        order_by="BagItem.updated_at.desc()",
        foreign_keys=[BagItem.bag_id],
    )

    __table_args__ = (
        sa.UniqueConstraint("bag_id", "trip_id", name="uq_bags_id_trip"),
        Index("ix_bags_trip_id", "trip_id"),
        Index("ix_bags_user_updated_at", "user_id", "updated_at"),
    )


__all__ = ["Bag", "BagItem"]


