from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, constr, model_validator
from sqlalchemy.orm import Session

from app.api.deps import DeviceAuthContext, maybe_device_auth, require_device_auth
from app.db.session import get_db
from app.services.device_registry import DeviceRegistry, DeviceRegistryError
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


class DeviceLinkRequest(BaseModel):
    action: Literal["generate", "redeem"]
    recovery_code: constr(strip_whitespace=True, min_length=6, max_length=12) | None = None  # type: ignore[valid-type]
    device_uuid: constr(strip_whitespace=True, min_length=4, max_length=64) | None = None  # type: ignore[valid-type]
    profile: DeviceProfilePayload | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> "DeviceLinkRequest":
        if self.action == "generate":
            if self.recovery_code or self.device_uuid or self.profile:
                raise ValueError("generate does not accept recovery_code or profile")
        else:
            if not (self.recovery_code and self.device_uuid and self.profile):
                raise ValueError("redeem requires recovery_code, device_uuid, and profile")
        return self


class DeviceLinkGenerateResponse(BaseModel):
    recovery_code: str
    expires_at: datetime


DeviceLinkResponse = DeviceLinkGenerateResponse | DeviceAuthResponse


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


@router.post("/link", response_model=DeviceLinkResponse, status_code=status.HTTP_200_OK)
def link_device(
    payload: DeviceLinkRequest,
    auth: DeviceAuthContext | None = Depends(maybe_device_auth),
    accept_language: str | None = Header(default=None, alias="Accept-Language"),
    db: Session = Depends(get_db),
) -> DeviceLinkResponse:
    registry = DeviceRegistry(db)
    if payload.action == "generate":
        if not auth:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="device_auth_required")
        result = registry.generate_recovery_code(auth.user)
        return DeviceLinkGenerateResponse(recovery_code=result.code, expires_at=result.expires_at)

    assert payload.recovery_code and payload.device_uuid and payload.profile  # guarded by validator
    redeem_payload = payload.profile.model_dump()
    redeem_payload["device_uuid"] = payload.device_uuid

    try:
        result = registry.redeem_recovery_code(
            code=payload.recovery_code,
            new_device_payload=redeem_payload,
            accept_language=accept_language,
        )
    except DeviceRegistryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc

    issued = issue_device_token(result.user.user_id, result.user.device_uuid or payload.device_uuid)
    return _issue_response(issued, result.feature_flags, result.ab_test_bucket)

