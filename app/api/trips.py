from fastapi import APIRouter, Depends

from app.db.session import get_db

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

