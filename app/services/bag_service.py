from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.deps import DeviceAuthContext
from app.db.models import Bag, BagItem, Trip
from app.schemas.checklist import (
    BagCreate,
    BagItemDetail,
    BagItemUpdate,
    BagListResponse,
    BagSummary,
    BagUpdate,
    BagItemsListResponse,
)


class BagService:
    def __init__(self, db: Session, auth: DeviceAuthContext):
        self.db = db
        self.auth = auth

    # ------------------------------------------------------------------ #
    # Bag helpers
    # ------------------------------------------------------------------ #
    def list_bags(self, trip_id: int) -> BagListResponse:
        trip = self._get_trip_for_user(trip_id)
        counts_subq = (
            select(
                BagItem.bag_id.label("bag_id"),
                func.count().label("total_items"),
                func.sum(case((BagItem.status == "packed", 1), else_=0)).label("packed_items"),
            )
            .where(
                BagItem.trip_id == trip.trip_id,
                BagItem.user_id == self.auth.user.user_id,
            )
            .group_by(BagItem.bag_id)
            .subquery()
        )

        rows = (
            select(Bag, counts_subq.c.total_items, counts_subq.c.packed_items)
            .where(
                Bag.trip_id == trip.trip_id,
                Bag.user_id == self.auth.user.user_id,
            )
            .outerjoin(counts_subq, counts_subq.c.bag_id == Bag.bag_id)
            .order_by(Bag.sort_order, Bag.bag_id)
        )

        items = [
            self._build_bag_summary(record, total or 0, packed or 0)
            for record, total, packed in self.db.execute(rows)
        ]
        return BagListResponse(items=items)

    def create_bag(self, trip_id: int, payload: BagCreate) -> BagSummary:
        if payload.is_default:
            raise HTTPException(status_code=400, detail="default_bag_creation_forbidden")

        trip = self._get_trip_for_user(trip_id)
        next_order = (
            self.db.scalar(
                select(func.max(Bag.sort_order)).where(
                    Bag.trip_id == trip.trip_id,
                    Bag.user_id == self.auth.user.user_id,
                )
            )
            or 0
        )
        bag = Bag(
            user_id=self.auth.user.user_id,
            trip_id=trip.trip_id,
            name=payload.name,
            bag_type=payload.bag_type,
            is_default=False,
            sort_order=payload.sort_order if payload.sort_order is not None else next_order + 1,
        )
        self.db.add(bag)
        self.db.commit()
        self.db.refresh(bag)
        return self._build_bag_summary(bag, 0, 0)

    def update_bag(self, bag_id: int, payload: BagUpdate) -> BagSummary:
        bag = self._get_bag_for_user(bag_id)
        if bag.is_default and payload.bag_type and payload.bag_type != bag.bag_type:
            raise HTTPException(status_code=400, detail="cannot_change_default_bag_type")

        if payload.name is not None:
            bag.name = payload.name
        if payload.bag_type is not None and not bag.is_default:
            bag.bag_type = payload.bag_type
        if payload.sort_order is not None:
            bag.sort_order = payload.sort_order

        self.db.commit()
        self.db.refresh(bag)
        return self._build_bag_summary(
            bag,
            self._count_items(bag.bag_id, status=None),
            self._count_items(bag.bag_id, status="packed"),
        )

    def delete_bag(self, bag_id: int) -> None:
        bag = self._get_bag_for_user(bag_id)
        if bag.is_default:
            raise HTTPException(status_code=400, detail="cannot_delete_default_bag")
        self.db.delete(bag)
        self.db.commit()

    # ------------------------------------------------------------------ #
    # Items
    # ------------------------------------------------------------------ #
    def list_items(self, bag_id: int, limit: int, offset: int) -> BagItemsListResponse:
        bag = self._get_bag_for_user(bag_id)
        query = (
            select(BagItem)
            .where(
                BagItem.bag_id == bag.bag_id,
                BagItem.user_id == self.auth.user.user_id,
            )
            .order_by(BagItem.updated_at.desc())
            .offset(offset)
            .limit(limit + 1)
        )
        rows = self.db.scalars(query).all()
        has_more = len(rows) > limit
        items = rows[:limit]
        return BagItemsListResponse(
            items=[self._build_item_detail(item) for item in items],
            next_offset=(offset + len(items)) if has_more else None,
            has_more=has_more,
        )

    def get_item(self, item_id: int) -> BagItemDetail:
        item = self._get_item_for_user(item_id)
        return self._build_item_detail(item)

    def update_item(self, item_id: int, payload: BagItemUpdate) -> BagItemDetail:
        item = self._get_item_for_user(item_id)

        if payload.bag_id is not None and payload.bag_id != item.bag_id:
            new_bag = self._get_bag_for_user(payload.bag_id)
            item.bag_id = new_bag.bag_id
            item.trip_id = new_bag.trip_id

        if payload.title is not None:
            item.title = payload.title
        if payload.quantity is not None:
            item.quantity = payload.quantity
        if payload.note is not None:
            item.note = payload.note
        if payload.status is not None:
            item.status = payload.status

        self.db.commit()
        self.db.refresh(item)
        return self._build_item_detail(item)

    def delete_item(self, item_id: int) -> None:
        item = self._get_item_for_user(item_id)
        self.db.delete(item)
        self.db.commit()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _get_trip_for_user(self, trip_id: int) -> Trip:
        trip = self.db.get(Trip, trip_id)
        if not trip or trip.user_id != self.auth.user.user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trip_not_found")
        return trip

    def _get_bag_for_user(self, bag_id: int) -> Bag:
        bag = self.db.get(Bag, bag_id)
        if not bag or bag.user_id != self.auth.user.user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="bag_not_found")
        return bag

    def _get_item_for_user(self, item_id: int) -> BagItem:
        item = self.db.get(BagItem, item_id)
        if not item or item.user_id != self.auth.user.user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="bag_item_not_found")
        return item

    def _build_bag_summary(self, bag: Bag, total_items: int, packed_items: int) -> BagSummary:
        return BagSummary(
            bag_id=bag.bag_id,
            trip_id=bag.trip_id,
            name=bag.name,
            bag_type=bag.bag_type,
            is_default=bag.is_default,
            sort_order=bag.sort_order,
            total_items=total_items,
            packed_items=packed_items,
            created_at=bag.created_at,
            updated_at=bag.updated_at,
        )

    def _build_item_detail(self, item: BagItem) -> BagItemDetail:
        return BagItemDetail(
            item_id=item.item_id,
            bag_id=item.bag_id,
            trip_id=item.trip_id,
            title=item.title,
            status=item.status,
            quantity=item.quantity,
            note=item.note,
            regulation_match_id=item.regulation_match_id,
            preview_snapshot=item.preview_snapshot,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    def _count_items(self, bag_id: int, status: str | None) -> int:
        query = (
            select(func.count())
            .select_from(BagItem)
            .where(
                BagItem.bag_id == bag_id,
                BagItem.user_id == self.auth.user.user_id,
            )
        )
        if status:
            query = query.where(BagItem.status == status)
        return self.db.scalar(query) or 0
