from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models.trip import Trip
from app.db.session import get_db
from app.schemas.recommendation import TripRecommendationResponse
from app.services.recommendation import RecommendationService

router = APIRouter(prefix="/trips", tags=["trips"])


@router.get("/{trip_id}/regulations")
async def get_trip_regulations(trip_id: int, db=Depends(get_db)):
    # TODO: SELECT country_code2, airline_code FROM trips WHERE trip_id = ?
    # Load rules via cache for (country_code2, airline_code)
    return {"trip_id": trip_id, "regulations": []}


@router.get("/{trip_id}")
async def get_trip(trip_id: int, db=Depends(get_db)):
    # TODO: SELECT FROM trips WHERE trip_id = ?
    return {"trip_id": trip_id}


@router.get(
    "/{trip_id}/recommendation",
    response_model=TripRecommendationResponse,
    status_code=status.HTTP_200_OK,
)
async def get_trip_recommendation(trip_id: int, db: Session = Depends(get_db)) -> TripRecommendationResponse:
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="trip_not_found")

    service = RecommendationService()
    return service.build(trip)

