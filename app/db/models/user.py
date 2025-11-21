from datetime import datetime
from typing import Any

from sqlalchemy import TIMESTAMP, String, BigInteger, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_uuid: Mapped[str | None] = mapped_column(String(36), unique=True)
    name: Mapped[str | None] = mapped_column(String(100))
    locale: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    flags: Mapped[dict[str, Any] | None] = mapped_column(JSON)

