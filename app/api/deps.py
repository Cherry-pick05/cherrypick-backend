from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.user import User
from app.db.session import get_db
from app.services.device_tokens import DeviceTokenError, TokenPayload, verify_device_token

DEVICE_UUID_HEADER = settings.device_uuid_header
DEVICE_TOKEN_HEADER = settings.device_token_header


@dataclass(slots=True)
class DeviceAuthContext:
    user: User
    token: TokenPayload


def require_device_auth(
    device_uuid: str = Header(..., alias=DEVICE_UUID_HEADER),
    device_token: str = Header(..., alias=DEVICE_TOKEN_HEADER),
    db: Session = Depends(get_db),
) -> DeviceAuthContext:
    return _resolve_device_auth(device_uuid, device_token, db)


def maybe_device_auth(
    device_uuid: str | None = Header(default=None, alias=DEVICE_UUID_HEADER),
    device_token: str | None = Header(default=None, alias=DEVICE_TOKEN_HEADER),
    db: Session = Depends(get_db),
) -> DeviceAuthContext | None:
    if not device_uuid or not device_token:
        return None
    return _resolve_device_auth(device_uuid, device_token, db)


def _resolve_device_auth(device_uuid: str, device_token: str, db: Session) -> DeviceAuthContext:
    try:
        payload = verify_device_token(device_token)
    except DeviceTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.code,
        ) from exc

    if payload["du"] != device_uuid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="device_token_mismatch")

    user = db.scalar(select(User).where(User.user_id == payload["uid"]))
    if not user or user.device_uuid != device_uuid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="device_not_registered")

    return DeviceAuthContext(user=user, token=payload)

