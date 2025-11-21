from datetime import datetime

from sqlalchemy import TIMESTAMP, BigInteger, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DeviceRecoveryCode(Base):
    __tablename__ = "device_recovery_codes"
    __table_args__ = (Index("ix_device_recovery_user", "user_id"),)

    code_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    code_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    previous_device_uuid: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=False)
    redeemed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)

