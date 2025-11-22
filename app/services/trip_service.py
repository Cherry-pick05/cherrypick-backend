from __future__ import annotations

from datetime import datetime
from typing import Iterable, Literal

from fastapi import HTTPException
from sqlalchemy import desc, func, select, text
from sqlalchemy.orm import Session

from app.api.deps import DeviceAuthContext
from app.db.models import Bag, BagItem, ItemImage, RegulationMatch
from app.db.models.trip import Trip, TripSegment, TripViaAirport
from app.schemas.trip import (
    ItinerarySnapshot,
    TripCreate,
    TripDetail,
    TripItemListItem,
    TripItemsListResponse,
    TripListItem,
    TripListResponse,
    TripSegmentInput,
    TripSegmentOutput,
    TripStats,
    TripUpdate,
)
from app.services.airport_lookup import get_country_code
from app.services.bag_service import apply_default_bags

TripStatusFilter = Literal["active", "archived", "all"]


class TripService:
    def __init__(self, db: Session, auth: DeviceAuthContext):
        self.db = db
        self.auth = auth

    # ------------------------------------------------------------------ #
    # CRUD operations
    # ------------------------------------------------------------------ #
    def create_trip(self, payload: TripCreate) -> TripDetail:
        trip = Trip(user_id=self.auth.user.user_id)
        self._assign_basic_fields(trip, payload)

        self._replace_via_airports(trip, payload.via_airports)
        self._replace_segments(trip, payload.segments)

        self._validate_date_range(trip)
        self._infer_countries_and_route(trip)
        apply_default_bags(self.db, self.auth, trip)

        self.db.add(trip)
        self.db.commit()
        self.db.refresh(trip)
        return self._build_trip_detail(trip)

    def update_trip(self, trip_id: int, payload: TripUpdate) -> TripDetail:
        trip = self._get_trip_for_user(trip_id)
        self._assign_basic_fields(trip, payload, partial=True)

        if payload.via_airports is not None:
            self._replace_via_airports(trip, payload.via_airports)
        if payload.segments is not None:
            self._replace_segments(trip, payload.segments)

        self._validate_date_range(trip)
        self._infer_countries_and_route(trip)
        apply_default_bags(self.db, self.auth, trip)

        self.db.commit()
        self.db.refresh(trip)
        return self._build_trip_detail(trip)

    def list_trips(self, status_filter: TripStatusFilter, limit: int, offset: int) -> TripListResponse:
        query = select(Trip).where(Trip.user_id == self.auth.user.user_id)
        if status_filter == "active":
            query = query.where(Trip.archived_at.is_(None), Trip.active.is_(True))
        elif status_filter == "archived":
            query = query.where(Trip.archived_at.is_not(None))
        else:
            query = query.where(Trip.archived_at.is_(None))

        query = query.order_by(desc(Trip.created_at)).offset(offset).limit(limit + 1)
        rows = self.db.scalars(query).all()

        has_more = len(rows) > limit
        items = rows[:limit]

        return TripListResponse(
            items=[
                TripListItem(
                    trip_id=trip.trip_id,
                    title=trip.title,
                    start_date=trip.start_date,
                    end_date=trip.end_date,
                    from_airport=trip.from_airport,
                    to_airport=trip.to_airport,
                    active=bool(trip.active),
                    archived_at=trip.archived_at,
                )
                for trip in items
            ],
            next_offset=(offset + len(items)) if has_more else None,
            has_more=has_more,
        )

    def get_trip_detail(self, trip_id: int) -> TripDetail:
        trip = self._get_trip_for_user(trip_id)
        return self._build_trip_detail(trip)

    def list_trip_items(self, trip_id: int, limit: int, offset: int) -> TripItemsListResponse:
        # Trip 소유권 확인
        trip = self._get_trip_for_user(trip_id)

        query = (
            select(BagItem, Bag, RegulationMatch)
            .join(Bag, BagItem.bag_id == Bag.bag_id)
            .outerjoin(RegulationMatch, BagItem.regulation_match_id == RegulationMatch.id)
            .where(
                BagItem.trip_id == trip.trip_id,
                BagItem.user_id == self.auth.user.user_id,
            )
            .order_by(desc(BagItem.updated_at))
            .offset(offset)
            .limit(limit + 1)
        )
        rows = self.db.execute(query).all()

        has_more = len(rows) > limit
        items = rows[:limit]

        return TripItemsListResponse(
            items=[
                TripItemListItem(
                    item_id=item.item_id,
                    bag_id=item.bag_id,
                    bag_name=bag.name,
                    status=item.status,  # type: ignore[arg-type]
                    quantity=item.quantity,
                    title=item.title,
                    note=item.note,
                    regulation_match_id=item.regulation_match_id,
                    canonical_key=match.canonical_key if match else None,
                    raw_label=match.raw_label if match else None,
                    norm_label=match.norm_label if match else None,
                    preview_snapshot=item.preview_snapshot,
                    updated_at=item.updated_at,
                )
                for item, bag, match in items
            ],
            next_offset=(offset + len(items)) if has_more else None,
            has_more=has_more,
        )

    def archive_trip(self, trip_id: int) -> TripDetail:
        trip = self._get_trip_for_user(trip_id)
        trip.archived_at = datetime.utcnow()
        trip.active = False
        self.db.commit()
        self.db.refresh(trip)
        return self._build_trip_detail(trip)

    def delete_trip(self, trip_id: int, *, purge: bool) -> None:
        if not purge:
            raise HTTPException(status_code=400, detail="purge_required")

        trip = self._get_trip_for_user(trip_id)

        # Detach related records
        self.db.execute(
            text("UPDATE regulation_matches SET trip_id = NULL WHERE trip_id = :trip_id"),
            {"trip_id": trip.trip_id},
        )
        self.db.execute(
            text("UPDATE item_images SET trip_id = NULL WHERE trip_id = :trip_id"),
            {"trip_id": trip.trip_id},
        )

        self.db.delete(trip)
        self.db.commit()

    def set_active_trip(self, trip_id: int) -> TripDetail:
        trip = self._get_trip_for_user(trip_id)
        if trip.archived_at is not None:
            raise HTTPException(status_code=400, detail="cannot_activate_archived_trip")

        # Deactivate existing active trip
        self.db.execute(
            text(
                "UPDATE trips SET active = FALSE WHERE user_id = :user_id AND active = TRUE AND trip_id != :trip_id"
            ),
            {"user_id": self.auth.user.user_id, "trip_id": trip.trip_id},
        )
        trip.active = True
        self.db.commit()
        self.db.refresh(trip)
        return self._build_trip_detail(trip)

    def duplicate_trip(self, trip_id: int) -> TripDetail:
        original = self._get_trip_for_user(trip_id)
        copy = Trip(
            user_id=self.auth.user.user_id,
            title=(original.title or "") + " (복제)",
            note=original.note,
            from_airport=original.from_airport,
            to_airport=original.to_airport,
            country_from=original.country_from,
            country_to=original.country_to,
            route_type=original.route_type,
            start_date=original.start_date,
            end_date=original.end_date,
            tags_json=list(original.tags_json or []),
            active=False,
        )

        for via in original.via_airports:
            copy.via_airports.append(
                TripViaAirport(airport_code=via.airport_code, via_order=via.via_order),
            )
        for seg in original.segments:
            copy.segments.append(
                TripSegment(
                    segment_order=seg.segment_order,
                    direction=seg.direction,
                    departure_airport=seg.departure_airport,
                    arrival_airport=seg.arrival_airport,
                    departure_country=seg.departure_country,
                    arrival_country=seg.arrival_country,
                    operating_airline=seg.operating_airline,
                    cabin_class=seg.cabin_class,
                    departure_date=seg.departure_date,
                )
            )

        self.db.add(copy)
        self.db.commit()
        self.db.refresh(copy)
        return self._build_trip_detail(copy)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_trip_for_user(self, trip_id: int) -> Trip:
        trip = self.db.get(Trip, trip_id)
        if not trip:
            raise HTTPException(status_code=404, detail="trip_not_found")
        if trip.user_id != self.auth.user.user_id:
            raise HTTPException(status_code=403, detail="trip_forbidden")
        return trip

    def _assign_basic_fields(self, trip: Trip, payload: TripCreate | TripUpdate, *, partial: bool = False) -> None:
        fields_set = getattr(payload, "model_fields_set", set())

        def should_assign(field_name: str) -> bool:
            return not partial or field_name in fields_set

        if should_assign("title"):
            trip.title = payload.title
        if should_assign("note"):
            trip.note = payload.note
        if should_assign("start_date"):
            trip.start_date = payload.start_date
        if should_assign("end_date"):
            trip.end_date = payload.end_date
        if should_assign("from_airport"):
            trip.from_airport = self._normalize_airport(payload.from_airport)
        if should_assign("to_airport"):
            trip.to_airport = self._normalize_airport(payload.to_airport)

        if isinstance(payload, TripUpdate):
            if should_assign("tags"):
                trip.tags_json = list(payload.tags or [])
            if should_assign("active") and payload.active is not None:
                trip.active = payload.active
            if "archived_at" in fields_set:
                trip.archived_at = payload.archived_at
        else:
            trip.tags_json = list(payload.tags)

    def _normalize_airport(self, code: str | None) -> str | None:
        if not code:
            return None
        code = code.strip().upper()
        if len(code) != 3:
            raise HTTPException(status_code=400, detail="invalid_airport_code")
        return code

    def _replace_via_airports(self, trip: Trip, airports: Iterable[str]) -> None:
        trip.via_airports.clear()
        for idx, code in enumerate(airports):
            normalized = self._normalize_airport(code)
            if not normalized:
                continue
            trip.via_airports.append(
                TripViaAirport(
                    airport_code=normalized,
                    via_order=idx,
                )
            )

    def _replace_segments(self, trip: Trip, segments: Iterable[TripSegmentInput]) -> None:
        trip.segments.clear()
        for idx, seg in enumerate(segments):
            dep, arr = self._parse_leg(seg.leg)
            trip.segments.append(
                TripSegment(
                    segment_order=idx,
                    direction="outbound",
                    departure_airport=dep,
                    arrival_airport=arr,
                    departure_country=self._country_for_airport(dep),
                    arrival_country=self._country_for_airport(arr),
                    operating_airline=seg.operating.upper() if seg.operating else None,
                    cabin_class=seg.cabin_class,
                )
            )

    def _parse_leg(self, leg: str) -> tuple[str, str]:
        parts = leg.strip().upper().split("-")
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail="invalid_segment_leg")
        dep, arr = parts
        if len(dep) != 3 or len(arr) != 3:
            raise HTTPException(status_code=400, detail="invalid_segment_leg")
        return dep, arr

    def _country_for_airport(self, airport_code: str | None) -> str | None:
        if not airport_code:
            return None
        country = get_country_code(airport_code)
        if not country:
            raise HTTPException(
                status_code=400,
                detail={"code": "airport_not_found", "airport": airport_code},
            )
        return country.upper()

    def _validate_date_range(self, trip: Trip) -> None:
        if trip.start_date and trip.end_date and trip.start_date > trip.end_date:
            raise HTTPException(status_code=400, detail="invalid_date_range")

    def _infer_countries_and_route(self, trip: Trip) -> None:
        trip.country_from = self._country_for_airport(trip.from_airport)
        trip.country_to = self._country_for_airport(trip.to_airport)
        via_countries = {self._country_for_airport(v.airport_code) for v in trip.via_airports if v.airport_code}
        via_countries.discard(None)

        if trip.country_from and trip.country_to:
            if trip.country_from == trip.country_to and not via_countries:
                trip.route_type = "domestic"
            else:
                trip.route_type = "international"
        else:
            trip.route_type = None

    def _build_trip_detail(self, trip: Trip) -> TripDetail:
        itinerary = ItinerarySnapshot(
            from_airport=trip.from_airport,
            via_airports=[via.airport_code for via in sorted(trip.via_airports, key=lambda v: v.via_order)],
            to_airport=trip.to_airport,
            route_type=trip.route_type,
            segments=[
                TripSegmentOutput(
                    segment_id=seg.segment_id,
                    segment_order=seg.segment_order,
                    leg=f"{seg.departure_airport}-{seg.arrival_airport}",
                    operating=seg.operating_airline,
                    cabin_class=seg.cabin_class,
                    direction=seg.direction,  # type: ignore[arg-type]
                    departure_airport=seg.departure_airport,
                    arrival_airport=seg.arrival_airport,
                    departure_country=seg.departure_country,
                    arrival_country=seg.arrival_country,
                    departure_date=seg.departure_date,
                )
                for seg in sorted(trip.segments, key=lambda s: s.segment_order)
            ],
        )

        stats = self._fetch_trip_stats(trip.trip_id)

        return TripDetail(
            trip_id=trip.trip_id,
            title=trip.title,
            note=trip.note,
            start_date=trip.start_date,
            end_date=trip.end_date,
            active=bool(trip.active),
            tags=list(trip.tags_json or []),
            itinerary=itinerary,
            stats=stats,
            created_at=trip.created_at,
            updated_at=trip.updated_at,
            archived_at=trip.archived_at,
        )

    def _fetch_trip_stats(self, trip_id: int) -> TripStats:
        items_scanned = self.db.scalar(select(func.count()).select_from(BagItem).where(BagItem.trip_id == trip_id))
        last_match = self.db.scalar(select(func.max(BagItem.updated_at)).where(BagItem.trip_id == trip_id))
        last_image = self.db.scalar(
            select(func.max(ItemImage.created_at)).where(ItemImage.trip_id == trip_id)
        )
        last_activity = max(filter(None, [last_match, last_image]), default=None)
        return TripStats(items_scanned=items_scanned or 0, last_activity_at=last_activity)

