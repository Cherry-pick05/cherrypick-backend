from fastapi import FastAPI, Request
from starlette.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import api_router

def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Simple client id injection
    @app.middleware("http")
    async def inject_client_id(request: Request, call_next):
        client_id = request.headers.get(settings.client_id_header)
        if client_id:
            request.state.client_id = client_id
        try:
            response = await call_next(request)
        except Exception as exc:
            return JSONResponse(status_code=500, content={"detail": "internal_error"})
        return response
    app.include_router(api_router, prefix="/v1")
    return app


app = create_app()


