from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, Field, constr
from sqlalchemy.orm import Session

from app.api.deps import DeviceAuthContext, require_device_auth
from app.db.session import get_db
from app.services.device_registry import DeviceRegistry
from app.services.device_tokens import IssuedToken, issue_device_token, token_expires_in

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceProfilePayload(BaseModel):
    app_version: constr(strip_whitespace=True, min_length=1, max_length=32)  # type: ignore[valid-type]
    os: constr(strip_whitespace=True, min_length=2, max_length=32)  # type: ignore[valid-type]
    model: constr(strip_whitespace=True, min_length=2, max_length=64)  # type: ignore[valid-type]
    locale: constr(strip_whitespace=True, min_length=2, max_length=16) | None = None  # type: ignore[valid-type]
    timezone: constr(strip_whitespace=True, min_length=2, max_length=64) | None = None  # type: ignore[valid-type]


class DeviceRegisterRequest(DeviceProfilePayload):
    device_uuid: constr(strip_whitespace=True, min_length=4, max_length=64)  # type: ignore[valid-type]


class DeviceRefreshRequest(BaseModel):
    app_version: constr(strip_whitespace=True, min_length=1, max_length=32) | None = None  # type: ignore[valid-type]
    os: constr(strip_whitespace=True, min_length=2, max_length=32) | None = None  # type: ignore[valid-type]
    model: constr(strip_whitespace=True, min_length=2, max_length=64) | None = None  # type: ignore[valid-type]
    locale: constr(strip_whitespace=True, min_length=2, max_length=16) | None = None  # type: ignore[valid-type]
    timezone: constr(strip_whitespace=True, min_length=2, max_length=64) | None = None  # type: ignore[valid-type]


class DeviceAuthResponse(BaseModel):
    device_token: str
    feature_flags: dict[str, Any]
    ab_test_bucket: str
    expires_in: int = Field(..., description="Seconds until the token expires")


def _issue_response(token: IssuedToken, feature_flags: dict[str, Any], bucket: str) -> DeviceAuthResponse:
    return DeviceAuthResponse(
        device_token=token.token,
        feature_flags=feature_flags,
        ab_test_bucket=bucket,
        expires_in=token_expires_in(token.payload),
    )


@router.post("/register", response_model=DeviceAuthResponse, status_code=status.HTTP_200_OK)
def register_device(
    payload: DeviceRegisterRequest,
    accept_language: str | None = Header(default=None, alias="Accept-Language"),
    db: Session = Depends(get_db),
) -> DeviceAuthResponse:
    registry = DeviceRegistry(db)
    result = registry.register_device(payload.model_dump(), accept_language)
    issued = issue_device_token(result.user.user_id, result.user.device_uuid or payload.device_uuid)
    return _issue_response(issued, result.feature_flags, result.ab_test_bucket)


@router.post("/refresh", response_model=DeviceAuthResponse, status_code=status.HTTP_200_OK)
def refresh_device(
    payload: DeviceRefreshRequest,
    auth: DeviceAuthContext = Depends(require_device_auth),
    accept_language: str | None = Header(default=None, alias="Accept-Language"),
    db: Session = Depends(get_db),
) -> DeviceAuthResponse:
    registry = DeviceRegistry(db)
    update_payload = payload.model_dump(exclude_none=True)
    update_payload["device_uuid"] = auth.user.device_uuid
    result = registry.update_user(auth.user, update_payload, accept_language)
    issued = issue_device_token(result.user.user_id, result.user.device_uuid or auth.user.device_uuid)
    return _issue_response(issued, result.feature_flags, result.ab_test_bucket)

