from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import DeviceAuthContext, require_device_auth
from app.db.session import get_db
from app.schemas.climate import ClimateRecentResponse
from app.services.climate_service import TripClimateService

router = APIRouter(prefix="/climate", tags=["climate"])


def get_trip_climate_service(
    auth: DeviceAuthContext = Depends(require_device_auth),
    db: Session = Depends(get_db),
) -> TripClimateService:
    return TripClimateService(db, auth)


@router.get("/trips/{trip_id}/recent", response_model=ClimateRecentResponse)
def get_recent_trip_climate(
    trip_id: int,
    years: int = Query(3, ge=1, le=5),
    aggregation: str = Query("weighted"),
    service: TripClimateService = Depends(get_trip_climate_service),
) -> ClimateRecentResponse:
    return service.get_trip_climate(trip_id, years=years, agg=aggregation)


