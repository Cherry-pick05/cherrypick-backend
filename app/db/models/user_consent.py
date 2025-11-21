from datetime import datetime

from sqlalchemy import TIMESTAMP, Boolean, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import BIGINT


class UserConsent(Base):
    __tablename__ = "user_consents"

    consent_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("users.user_id", ondelete="CASCADE"), unique=True, nullable=False
    )
    terms_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    privacy_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    marketing_opt_in: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    crash_opt_in: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    consent_version: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

