from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import DeviceAuthContext, require_device_auth
from app.db.models.trip import Trip
from app.db.session import get_db
from app.schemas.flight import FlightLookupRequest, FlightLookupResponse
from app.schemas.recommendation import (
    OutfitRecommendationRequest,
    OutfitRecommendationResponse,
    TripRecommendationResponse,
)
from app.schemas.trip import (
    TripCreate,
    TripDetail,
    TripDurationStatus,
    TripDurationUpdate,
    TripItemsListResponse,
    TripListResponse,
)
from app.services.recommendation import RecommendationService
from app.services.flight_lookup import FlightLookupError, FlightLookupService
from app.services.trip_service import TripService, TripStatusFilter
from app.services.outfit_recommendation import OutfitRecommendationService

router = APIRouter(prefix="/trips", tags=["trips"])


def get_trip_service(
    auth: DeviceAuthContext = Depends(require_device_auth),
    db: Session = Depends(get_db),
) -> TripService:
    return TripService(db, auth)


@router.post("/lookup-flight", response_model=FlightLookupResponse, status_code=200)
def lookup_flight(
    payload: FlightLookupRequest,
    auth: DeviceAuthContext = Depends(require_device_auth),
) -> FlightLookupResponse:
    service = FlightLookupService()
    try:
        return service.lookup(payload.flight_code, payload.code_type)
    except FlightLookupError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc


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


@router.patch("/{trip_id}/duration", response_model=TripDurationStatus)
def update_trip_duration(
    trip_id: int,
    payload: TripDurationUpdate,
    service: TripService = Depends(get_trip_service),
) -> TripDurationStatus:
    trip = service.update_duration(trip_id, payload)
    return TripDurationStatus(
        trip_id=trip.trip_id,
        start_date=trip.start_date,
        end_date=trip.end_date,
        needs_duration=bool(trip.needs_duration),
    )


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


@router.post(
    "/{trip_id}/recommendations/outfit",
    response_model=OutfitRecommendationResponse,
    status_code=status.HTTP_200_OK,
)
def generate_outfit_recommendation(
    trip_id: int,
    payload: OutfitRecommendationRequest = Body(default_factory=OutfitRecommendationRequest),
    auth: DeviceAuthContext = Depends(require_device_auth),
    db: Session = Depends(get_db),
) -> OutfitRecommendationResponse:
    service = OutfitRecommendationService(db, auth)
    return service.recommend(trip_id, payload)

