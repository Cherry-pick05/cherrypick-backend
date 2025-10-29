from fastapi import APIRouter

from app.api.items import router as items_router
from app.api.media import router as media_router
from app.api.public.health import router as health_router
from app.api.trips import router as trips_router
from app.api.ws import router as ws_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(media_router)
api_router.include_router(ws_router)
api_router.include_router(items_router)
api_router.include_router(trips_router)


