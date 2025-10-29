from fastapi import APIRouter, Depends

from app.db.session import get_db

router = APIRouter(prefix="/items", tags=["items"])


# 규정 매칭 결과 조회
@router.get("/{item_id}/matches")
async def get_item_matches(item_id: int, db=Depends(get_db)):
    # TODO: SELECT FROM regulation_matches WHERE item_id = ? ORDER BY matched_at DESC
    return {"item_id": item_id, "matches": []}


# 아이템 정보 조회
@router.get("/{item_id}")
async def get_item(item_id: int, db=Depends(get_db)):
    # TODO: SELECT FROM packing_items WHERE item_id = ?
    return {"item_id": item_id}

