from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, constr
from sqlalchemy.orm import Session

from app.api.deps import DeviceAuthContext, require_device_auth
from app.db.session import get_db
from app.services.app_config import build_bootstrap_config
from app.services.device_registry import DeviceRegistry

router = APIRouter(prefix="/bootstrap", tags=["bootstrap"])


class ConsentRequest(BaseModel):
    terms_required: bool = Field(..., description="필수 이용약관 동의 여부")
    privacy_required: bool = Field(..., description="필수 개인정보 동의 여부")
    marketing_opt_in: bool = Field(False, description="선택 마케팅 수신 동의 여부")
    crash_opt_in: bool = Field(False, description="선택 크래시 수집 동의 여부")
    version: constr(strip_whitespace=True, min_length=1, max_length=16) | None = None  # type: ignore[valid-type]


class ConsentResponse(BaseModel):
    status: str = "ok"


class ConfigResponse(BaseModel):
    safe_mode: bool
    supported_locales: list[str]
    units: dict[str, str]
    ui_flags: dict[str, Any]
    rule_manifest_version: str
    taxonomy_manifest_version: str


@router.post("/consent", response_model=ConsentResponse, status_code=status.HTTP_200_OK)
def submit_consent(
    payload: ConsentRequest,
    auth: DeviceAuthContext = Depends(require_device_auth),
    db: Session = Depends(get_db),
) -> ConsentResponse:
    registry = DeviceRegistry(db)
    registry.record_consent(auth.user, payload.model_dump())
    return ConsentResponse()


@router.get("/config", response_model=ConfigResponse, status_code=status.HTTP_200_OK)
def get_bootstrap_config(
    auth: DeviceAuthContext = Depends(require_device_auth),
) -> ConfigResponse:
    del auth  # context only ensures device auth
    return ConfigResponse(**build_bootstrap_config())

