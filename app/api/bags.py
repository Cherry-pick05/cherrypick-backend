from fastapi import APIRouter, Depends, Query

from app.api.deps import DeviceAuthContext, require_device_auth
from app.db.session import get_db
from app.schemas.checklist import (
    BagCreate,
    BagItemDetail,
    BagItemUpdate,
    BagItemsListResponse,
    BagListResponse,
    BagSummary,
    BagUpdate,
)
from app.services.bag_service import BagService

router = APIRouter(tags=["bags"])


def get_bag_service(
    auth: DeviceAuthContext = Depends(require_device_auth),
    db=Depends(get_db),
) -> BagService:
    return BagService(db, auth)


@router.get("/trips/{trip_id}/bags", response_model=BagListResponse)
def list_bags(trip_id: int, service: BagService = Depends(get_bag_service)) -> BagListResponse:
    return service.list_bags(trip_id)


@router.post("/trips/{trip_id}/bags", response_model=BagSummary, status_code=201)
def create_bag(trip_id: int, payload: BagCreate, service: BagService = Depends(get_bag_service)) -> BagSummary:
    return service.create_bag(trip_id, payload)


@router.patch("/bags/{bag_id}", response_model=BagSummary)
def update_bag(bag_id: int, payload: BagUpdate, service: BagService = Depends(get_bag_service)) -> BagSummary:
    return service.update_bag(bag_id, payload)


@router.delete("/bags/{bag_id}", status_code=204)
def delete_bag(bag_id: int, service: BagService = Depends(get_bag_service)) -> None:
    service.delete_bag(bag_id)


@router.get("/bags/{bag_id}/items", response_model=BagItemsListResponse)
def list_bag_items(
    bag_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: BagService = Depends(get_bag_service),
) -> BagItemsListResponse:
    return service.list_items(bag_id, limit, offset)


@router.get("/bag-items/{item_id}", response_model=BagItemDetail)
def get_bag_item(item_id: int, service: BagService = Depends(get_bag_service)) -> BagItemDetail:
    return service.get_item(item_id)


@router.patch("/bag-items/{item_id}", response_model=BagItemDetail)
def update_bag_item(item_id: int, payload: BagItemUpdate, service: BagService = Depends(get_bag_service)) -> BagItemDetail:
    return service.update_item(item_id, payload)


