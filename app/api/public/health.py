from fastapi import APIRouter


router = APIRouter(prefix="/healthz", tags=["health"])


@router.get("")
def healthz():
    return {"status": "ok"}