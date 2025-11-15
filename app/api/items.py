from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, constr
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import RegulationMatch
from app.db.session import get_db
from app.schemas.decision import RuleEngineRequest, RuleEngineResponse
from app.schemas.preview import (
    NarrationPayload,
    PreviewRequest,
    PreviewResponse,
    ResolvedInfo,
    make_rule_request,
)
from app.services.ai_tips import generate_ai_tips
from app.services.item_classifier import ClassificationResult, classify_label
from app.services.narration import build_narration
from app.services.rule_engine import RuleEngine

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
    _persist_match(db, req_id, result)

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

    classification = classify_label(label, locale=req.locale)
    resolved = ResolvedInfo(
        label=label,
        canonical=classification.canonical,
        locale=req.locale,
    )

    if classification.abstain or not classification.canonical:
        return PreviewResponse(state="needs_review", resolved=resolved)

    req_id = req.req_id or uuid.uuid4().hex
    engine_req = make_rule_request(classification.canonical, req_id, req)
    engine = RuleEngine(db)
    engine_response = engine.evaluate(engine_req)
    engine_response.ai_tips = generate_ai_tips(engine_req, engine_response)

    narration = build_narration(req, classification, engine_response)

    return PreviewResponse(
        state="complete",
        resolved=resolved,
        engine=engine_response,
        narration=narration,
        ai_tips=engine_response.ai_tips,
    )


def _persist_match(db: Session, req_id: str, result: ClassificationResult) -> None:
    record = RegulationMatch(
        req_id=req_id,
        raw_label=result.raw_label,
        norm_label=result.norm_label,
        canonical_key=result.canonical,
        candidates_json=result.categories,
        details=result.signals,
        confidence=result.confidence,
        decided_by=result.decided_by,
        model_info=result.model_info,
        source="manual",
    )
    try:
        db.add(record)
        db.commit()
    except SQLAlchemyError as exc:  # pragma: no cover - logging best-effort
        db.rollback()
        logger.warning("Failed to persist classification match (req_id=%s): %s", req_id, exc)


# 규정 매칭 결과 조회 (stub)
@router.get("/{item_id}/matches")
def get_item_matches(item_id: int, db: Session = Depends(get_db)) -> dict:
    return {"item_id": item_id, "matches": []}


# 아이템 정보 조회 (stub)
@router.get("/{item_id}")
def get_item(item_id: int, db: Session = Depends(get_db)) -> dict:
    return {"item_id": item_id}

