from fastapi import FastAPI

from app.core.config import settings
from app.api.routes import api_router


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.include_router(api_router, prefix="/v1")
    return app


app = create_app()


