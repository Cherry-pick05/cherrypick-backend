import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.api.routes import api_router
from app.core.config import settings

def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    app = FastAPI(title=settings.app_name)
    # CORS
    # "*"일 때는 allow_credentials를 False로 설정 (FastAPI 제약)
    cors_origins = settings.cors_origins
    allow_creds = cors_origins != "*"
    if cors_origins == "*":
        cors_origins = ["*"]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_creds,
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
    app.include_router(api_router)
    return app


app = create_app()


