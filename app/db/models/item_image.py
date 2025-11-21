from datetime import datetime

from sqlalchemy import TIMESTAMP, String, Integer, ForeignKey, Enum, JSON, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import BIGINT


class ItemImage(Base):
    __tablename__ = "item_images"

    image_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    s3_key: Mapped[str] = mapped_column(String(512), unique=True)
    status: Mapped[str | None] = mapped_column(Enum("uploaded", "queued", "processed", "failed", name="image_status"))
    mime_type: Mapped[str | None] = mapped_column(String(64))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    rekognition_labels: Mapped[dict | None] = mapped_column(JSON)
    user_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.user_id"))
    trip_id: Mapped[int | None] = mapped_column(BIGINT, ForeignKey("trips.trip_id"))
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index("ix_item_images_user_created", "user_id", "created_at"),
    )

