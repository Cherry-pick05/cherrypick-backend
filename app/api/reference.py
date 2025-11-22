from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import DeviceAuthContext, maybe_device_auth
from app.db.session import get_db
from app.schemas.reference import (
    AirlineListResponse,
    AirportListResponse,
    CabinClassListResponse,
    CountryListResponse,
)
from app.services.airport_directory import AirportDirectoryService, CountryDirectoryService
from app.services.regulation_sources import REGULATION_SOURCES
from app.services.reference_data import AIRLINE_CABIN_CLASSES, CABIN_CLASSES_DEFAULT


router = APIRouter(prefix="/reference", tags=["reference"])


@router.get("/countries", response_model=CountryListResponse)
def list_countries(
    q: str | None = Query(None, description="국가명/코드 검색어"),
    region: str | None = Query(None, description="지역 필터 (데이터 원문 기준)"),
    active_only: bool = Query(True, description="서비스 중인 국가만 반환 (DB에 규정이 있는 국가)"),
    db: Session = Depends(get_db),
    auth: DeviceAuthContext | None = Depends(maybe_device_auth),
) -> CountryListResponse:
    service = CountryDirectoryService(db)
    items = service.search(q=q, region=region, active_only=active_only)
    return CountryListResponse(items=items)


@router.get("/airports", response_model=AirportListResponse)
def list_airports(
    q: str | None = Query(None, description="공항명/코드/도시 검색어"),
    country_code: str | None = Query(None, description="ISO 3166-1 alpha-2 국가 코드"),
    limit: int = Query(20, ge=1, le=200, description="최대 반환 개수"),
    active_only: bool = Query(True, description="서비스 중인 국가의 공항만 반환 (DB에 규정이 있는 국가)"),
    db: Session = Depends(get_db),
    auth: DeviceAuthContext | None = Depends(maybe_device_auth),
) -> AirportListResponse:
    service = AirportDirectoryService(db)
    items = service.search(q=q, country_code=country_code, limit=limit, active_only=active_only)
    return AirportListResponse(items=items)


@router.get("/airlines", response_model=AirlineListResponse)
def list_airlines(
    q: str | None = Query(None, description="항공사명/코드 검색어"),
    active_only: bool = Query(True, description="서비스 중인 항공사만 반환 (DB에 규정이 있는 항공사)"),
    db: Session = Depends(get_db),
    auth: DeviceAuthContext | None = Depends(maybe_device_auth),
) -> AirlineListResponse:
    from app.db.models.regulation import RuleSet
    from sqlalchemy import select

    # 서비스 중인 항공사 코드 목록 (DB에 규정이 있는 항공사)
    active_codes = set()
    if active_only:
        rows = db.scalars(select(RuleSet.code).where(RuleSet.scope == "airline")).all()
        active_codes = {code.upper() for code in rows}

    # 규정 소스에서 항공사 정보 가져오기
    airlines = REGULATION_SOURCES.get("airline", {})
    items = []
    for code, config in airlines.items():
        if active_only and code.upper() not in active_codes:
            continue
        if q:
            q_lower = q.lower().strip()
            if q_lower not in code.lower() and q_lower not in (config.get("name") or "").lower():
                continue
        items.append({"code": code, "name": config.get("name", code)})

    return AirlineListResponse(items=sorted(items, key=lambda x: x["code"]))


@router.get("/cabin_classes", response_model=CabinClassListResponse)
def list_cabin_classes(
    airline_code: str | None = Query(
        None, description="항공사 코드(예: KE, TW). 없으면 기본 좌석 등급 반환"
    )
) -> CabinClassListResponse:
    if airline_code:
        matched = AIRLINE_CABIN_CLASSES.get(airline_code.upper())
        if matched:
            return CabinClassListResponse(items=matched)
    return CabinClassListResponse(items=CABIN_CLASSES_DEFAULT)


