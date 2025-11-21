from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import DeviceAuthContext, require_device_auth
from app.db.models.trip import Trip
from app.db.session import get_db
from app.schemas.recommendation import TripRecommendationResponse
from app.schemas.trip import TripCreate, TripDetail, TripItemsListResponse, TripListResponse
from app.services.recommendation import RecommendationService
from app.services.trip_service import TripService, TripStatusFilter

router = APIRouter(prefix="/v1/trips", tags=["trips"])


def get_trip_service(
    auth: DeviceAuthContext = Depends(require_device_auth),
    db: Session = Depends(get_db),
) -> TripService:
    return TripService(db, auth)


@router.post("", response_model=TripDetail, status_code=201)
def create_trip(payload: TripCreate, service: TripService = Depends(get_trip_service)) -> TripDetail:
    return service.create_trip(payload)


@router.get("", response_model=TripListResponse)
def list_trips(
    status: TripStatusFilter = Query("active", description="active | archived | all"),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    service: TripService = Depends(get_trip_service),
) -> TripListResponse:
    return service.list_trips(status, limit, offset)


@router.get("/{trip_id}", response_model=TripDetail)
def get_trip_detail(trip_id: int, service: TripService = Depends(get_trip_service)) -> TripDetail:
    return service.get_trip_detail(trip_id)


@router.get("/{trip_id}/items", response_model=TripItemsListResponse)
def list_trip_items(
    trip_id: int,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    service: TripService = Depends(get_trip_service),
) -> TripItemsListResponse:
    return service.list_trip_items(trip_id, limit, offset)


@router.post("/{trip_id}/archive")
def archive_trip(trip_id: int, service: TripService = Depends(get_trip_service)) -> dict:
    trip = service.archive_trip(trip_id)
    return {"trip_id": trip.trip_id, "archived": True}


@router.delete("/{trip_id}")
def delete_trip(
    trip_id: int,
    purge: bool = Query(False, description="Hard delete requires purge=true"),
    service: TripService = Depends(get_trip_service),
) -> dict:
    service.delete_trip(trip_id, purge=purge)
    return {"trip_id": trip_id, "deleted": True}


@router.post("/{trip_id}/set_active")
def set_active(trip_id: int, service: TripService = Depends(get_trip_service)) -> dict:
    trip = service.set_active_trip(trip_id)
    return {"trip_id": trip.trip_id, "active": True}


@router.post("/{trip_id}/duplicate")
def duplicate_trip(trip_id: int, service: TripService = Depends(get_trip_service)) -> dict:
    copy = service.duplicate_trip(trip_id)
    return {"trip_id_new": copy.trip_id}


@router.get(
    "/{trip_id}/recommendation",
    response_model=TripRecommendationResponse,
    status_code=status.HTTP_200_OK,
)
def get_trip_recommendation(
    trip_id: int,
    auth: DeviceAuthContext = Depends(require_device_auth),
    db: Session = Depends(get_db),
) -> TripRecommendationResponse:
    trip = db.get(Trip, trip_id)
    if not trip or trip.user_id != auth.user.user_id:
        raise HTTPException(status_code=404, detail="trip_not_found")

    service = RecommendationService()
    return service.build(trip)

