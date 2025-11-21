from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import DeviceAuthContext, maybe_device_auth
from app.db.session import get_db
from app.schemas.reference import AirportListResponse, CountryListResponse
from app.services.airport_directory import AirportDirectoryService, CountryDirectoryService


router = APIRouter(tags=["Reference"])


@router.get("/countries", response_model=CountryListResponse)
def list_countries(
    q: str | None = Query(None, description="국가명/코드 검색어"),
    region: str | None = Query(None, description="지역 필터 (데이터 원문 기준)"),
    db: Session = Depends(get_db),
    auth: DeviceAuthContext | None = Depends(maybe_device_auth),
) -> CountryListResponse:
    service = CountryDirectoryService(db)
    items = service.search(q=q, region=region)
    return CountryListResponse(items=items)


@router.get("/airports", response_model=AirportListResponse)
def list_airports(
    q: str | None = Query(None, description="공항명/코드/도시 검색어"),
    country_code: str | None = Query(None, description="ISO 3166-1 alpha-2 국가 코드"),
    limit: int = Query(20, ge=1, le=200, description="최대 반환 개수"),
    db: Session = Depends(get_db),
    auth: DeviceAuthContext | None = Depends(maybe_device_auth),
) -> AirportListResponse:
    service = AirportDirectoryService(db)
    items = service.search(q=q, country_code=country_code, limit=limit)
    return AirportListResponse(items=items)


