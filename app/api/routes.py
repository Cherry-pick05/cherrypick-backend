from fastapi import APIRouter

from app.api.bags import router as bags_router
from app.api.bootstrap import router as bootstrap_router
from app.api.climate import router as climate_router
from app.api.devices import router as devices_router
from app.api.items import router as items_router
from app.api.media import router as media_router
from app.api.public.health import router as health_router
from app.api.reference import router as reference_router
from app.api.trips import router as trips_router
from app.api.ws import router as ws_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(ws_router)

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(bootstrap_router)
v1_router.include_router(devices_router)
v1_router.include_router(media_router)
v1_router.include_router(items_router)
v1_router.include_router(reference_router)
v1_router.include_router(climate_router)
v1_router.include_router(trips_router)
v1_router.include_router(bags_router)

api_router.include_router(v1_router)