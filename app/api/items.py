from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, constr
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import DeviceAuthContext, require_device_auth
from app.core.config import settings
from app.db.models import Bag, BagItem, RegulationMatch
from app.db.session import get_db
from app.schemas.decision import DecisionPayload, DecisionSlot, RuleEngineRequest, RuleEngineResponse
from app.schemas.preview import (
    NarrationPayload,
    PreviewRequest,
    PreviewResponse,
    ResolvedInfo,
    make_rule_request,
)
from app.services.ai_tips import generate_ai_tips
from app.services.classifier_data import get_benign_keys
from app.services.dict_classifier import normalize_label
from app.services.item_classifier import ClassificationResult, classify_label
from app.services.llm_decision import LLMDecisionError, fetch_llm_decision
from app.services.narration import build_narration
from app.services.risk_guard import LLMDecisionPayload, merge_layers
from app.services.rule_engine import RuleEngine
BENIGN_KEY = "benign_general"
BENIGN_CATEGORIES = set(get_benign_keys())


router = APIRouter(prefix="/items", tags=["items"])
logger = logging.getLogger(__name__)


class CategoryScore(BaseModel):
    key: str
    score: float


class ClassificationRequest(BaseModel):
    label: constr(strip_whitespace=True, min_length=1)  # type: ignore[valid-type]
    locale: constr(strip_whitespace=True, min_length=2) | None = None  # type: ignore[valid-type]
    req_id: constr(strip_whitespace=True, min_length=4) | None = None  # type: ignore[valid-type]


class ClassificationResponse(BaseModel):
    req_id: str
    canonical: str | None
    confidence: float | None
    candidates: list[str]
    categories: list[CategoryScore]
    abstain: bool
    decided_by: str
    norm_label: str
    signals: dict[str, Any]
    model_info: dict[str, Any] | None = None


@router.post("/classify", response_model=ClassificationResponse, status_code=status.HTTP_200_OK)
def classify_item(req: ClassificationRequest, db: Session = Depends(get_db)) -> ClassificationResponse:
    label = req.label.strip()
    if not label:
        raise HTTPException(status_code=400, detail="label must not be empty")

    result = classify_label(label, locale=req.locale)
    req_id = req.req_id or uuid.uuid4().hex
    # Note: 저장은 사용자가 명시적으로 /items/save를 호출할 때만 수행됩니다.

    return ClassificationResponse(
        req_id=req_id,
        canonical=result.canonical,
        confidence=result.confidence,
        candidates=result.candidates,
        categories=[CategoryScore(**entry) for entry in result.categories],
        abstain=result.abstain,
        decided_by=result.decided_by,
        norm_label=result.norm_label,
        signals=result.signals,
        model_info=result.model_info,
    )


@router.post("/decide", response_model=RuleEngineResponse, status_code=status.HTTP_200_OK)
def decide_item(req: RuleEngineRequest, db: Session = Depends(get_db)) -> RuleEngineResponse:
    engine = RuleEngine(db)
    result = engine.evaluate(req)
    result.ai_tips = generate_ai_tips(req, result)
    return result


@router.post("/preview", response_model=PreviewResponse, status_code=status.HTTP_200_OK)
def preview_item(req: PreviewRequest, db: Session = Depends(get_db)) -> PreviewResponse:
    label = req.label.strip()
    if not label:
        raise HTTPException(status_code=400, detail="label must not be empty")

    req_id = req.req_id or uuid.uuid4().hex
    resolved = ResolvedInfo(label=label, canonical=None, locale=req.locale)

    try:
        llm_payload = fetch_llm_decision(req)
    except LLMDecisionError as exc:
        logger.warning("LLM decision failed: %s", exc)
        return _fallback_preview(req, resolved, label, req_id, str(exc), db)

    resolved.canonical = llm_payload.canonical
    classification = _classification_from_decision(label, llm_payload)

    flags: dict[str, Any] = {}
    needs_review = bool(llm_payload.needs_review)
    confidence = llm_payload.signals.confidence
    if confidence < settings.llm_classifier_confidence_threshold:
        flags["low_confidence"] = confidence
        if llm_payload.canonical not in BENIGN_CATEGORIES:
            needs_review = True

    engine_req: RuleEngineRequest
    engine_response: RuleEngineResponse

    if llm_payload.canonical in BENIGN_CATEGORIES:
        engine_req = make_rule_request(llm_payload.canonical, req_id, req, item_params=llm_payload.params)
        engine_response = _allow_benign_response(req_id, llm_payload.canonical)
        needs_review = False
        flags["benign_category"] = llm_payload.canonical
    else:
        try:
            outcome = merge_layers(llm_payload, req, req_id=req_id, db=db)
        except SQLAlchemyError as exc:  # pragma: no cover - DB path
            logger.exception("Rule engine merge failed: %s", exc)
            return PreviewResponse(
                state="needs_review",
                resolved=resolved,
                flags={"engine_error": "rule_engine_unavailable"},
            )
        engine_response = outcome.engine
        engine_req = outcome.engine_request
        if outcome.conflict:
            flags["conflicts"] = outcome.conflict_slots
            needs_review = True
        if outcome.missing_params:
            flags["missing_params"] = list(outcome.missing_params)
            needs_review = True

    flags["llm_needs_review"] = llm_payload.needs_review
    if "missing_params" not in flags:
        flags["missing_params"] = []

    engine_response.ai_tips = generate_ai_tips(engine_req, engine_response)
    narration = build_narration(req, classification, engine_response)

    flags["needs_review"] = needs_review
    state = "needs_review" if needs_review else "complete"

    return PreviewResponse(
        state=state,
        resolved=resolved,
        engine=engine_response,
        narration=narration,
        ai_tips=engine_response.ai_tips,
        flags=flags,
    )


class SaveItemRequest(BaseModel):
    req_id: str
    preview: PreviewResponse
    bag_id: int
    image_id: int | None = None
    trip_id: int | None = None


@router.post("/save", status_code=status.HTTP_201_CREATED)
def save_item(
    req: SaveItemRequest,
    db: Session = Depends(get_db),
    auth: DeviceAuthContext = Depends(require_device_auth),
) -> dict:
    """사용자가 preview 결과를 저장합니다. user_id, trip_id, image_id와 연결됩니다."""
    preview = req.preview
    resolved = preview.resolved
    engine = preview.engine

    # status 결정: engine의 decision에서 추출
    status_value = None
    if engine and engine.decision:
        carry_on_status = engine.decision.carry_on.status
        checked_status = engine.decision.checked.status
        # 둘 다 deny면 ban, 하나라도 limit면 limited, 둘 다 allow면 allow
        if carry_on_status == "deny" or checked_status == "deny":
            status_value = "ban"
        elif carry_on_status == "limit" or checked_status == "limit":
            status_value = "limited"
        elif carry_on_status == "allow" and checked_status == "allow":
            status_value = "allow"

    bag = db.get(Bag, req.bag_id)
    if not bag or bag.user_id != auth.user.user_id:
        raise HTTPException(status_code=404, detail="bag_not_found")

    trip_id = req.trip_id or bag.trip_id
    if not trip_id:
        raise HTTPException(status_code=400, detail="trip_id_required")
    if bag.trip_id != trip_id:
        raise HTTPException(status_code=400, detail="bag_trip_mismatch")

    preview_data = {
        "preview_response": preview.model_dump(),
        "engine_response": engine.model_dump() if engine else None,
        "narration": preview.narration.model_dump() if preview.narration else None,
        "ai_tips": [tip.model_dump() for tip in preview.ai_tips],
        "flags": preview.flags,
    }

    record = RegulationMatch(
        req_id=req.req_id,
        user_id=auth.user.user_id,
        trip_id=trip_id,
        image_id=req.image_id,
        raw_label=resolved.label,
        norm_label=resolved.label,  # TODO: normalize 필요시 수정
        canonical_key=resolved.canonical,
        status=status_value,
        confidence=None,  # engine에서 추출 가능하지만 일단 None
        decided_by="user",
        source="manual",
        details=preview_data,
    )

    try:
        db.add(record)
        db.flush()

        bag_item = BagItem(
            user_id=auth.user.user_id,
            trip_id=trip_id,
            bag_id=bag.bag_id,
            regulation_match_id=record.id,
            title=resolved.canonical or resolved.label,
            status="todo",
            quantity=1,
            preview_snapshot=preview_data,
        )
        db.add(bag_item)
        db.commit()
        db.refresh(record)
        db.refresh(bag_item)
        return {
            "match_id": record.id,
            "bag_item_id": bag_item.item_id,
            "req_id": req.req_id,
            "saved": True,
        }
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Failed to save item preview (req_id=%s): %s", req.req_id, exc)
        raise HTTPException(status_code=500, detail="failed_to_save_item")


# 규정 매칭 결과 조회 (stub)
@router.get("/{item_id}/matches")
def get_item_matches(item_id: int, db: Session = Depends(get_db)) -> dict:
    return {"item_id": item_id, "matches": []}


# 아이템 정보 조회 (stub)
@router.get("/{item_id}")
def get_item(item_id: int, db: Session = Depends(get_db)) -> dict:
    return {"item_id": item_id}


def _classification_from_decision(label: str, payload: LLMDecisionPayload) -> ClassificationResult:
    return ClassificationResult(
        raw_label=label,
        norm_label=normalize_label(label),
        canonical=payload.canonical,
        confidence=payload.signals.confidence,
        candidates=[payload.canonical],
        categories=[{"key": payload.canonical, "score": 1.0}],
        abstain=False,
        decided_by="llm_decision",
        signals={"matched_terms": payload.signals.matched_terms},
        model_info=payload.model_info,
    )


def _allow_benign_response(req_id: str, canonical: str) -> RuleEngineResponse:
    decision = DecisionPayload(
        carry_on=DecisionSlot(status="allow", badges=[], reason_codes=[]),
        checked=DecisionSlot(status="allow", badges=[], reason_codes=[]),
    )
    return RuleEngineResponse(
        req_id=req_id,
        canonical=canonical,
        decision=decision,
        conditions={"carry_on": {}, "checked": {}, "common": {}},
        sources=[],
        trace=[],
    )


def _fallback_preview(
    req: PreviewRequest,
    resolved: ResolvedInfo,
    label: str,
    req_id: str,
    error_message: str,
    db: Session,
) -> PreviewResponse:
    classification = classify_label(label, locale=req.locale)
    resolved.canonical = classification.canonical

    if classification.abstain or not classification.canonical:
        return PreviewResponse(
            state="needs_review",
            resolved=resolved,
            flags={"llm_error": error_message, "fallback": "dict_classifier_abstain"},
        )

    engine_req = make_rule_request(classification.canonical, req_id, req)
    engine = RuleEngine(db)
    try:
        engine_response = engine.evaluate(engine_req)
    except SQLAlchemyError as exc:  # pragma: no cover - DB path
        logger.exception("Fallback rule engine failed: %s", exc)
        return PreviewResponse(
            state="needs_review",
            resolved=resolved,
            flags={"llm_error": error_message, "engine_error": "rule_engine_unavailable"},
        )

    engine_response.ai_tips = generate_ai_tips(engine_req, engine_response)
    narration = build_narration(req, classification, engine_response)

    return PreviewResponse(
        state="complete",
        resolved=resolved,
        engine=engine_response,
        narration=narration,
        ai_tips=engine_response.ai_tips,
        flags={
            "fallback": "classic_pipeline",
            "llm_error": error_message,
            "needs_review": False,
        },
    )

