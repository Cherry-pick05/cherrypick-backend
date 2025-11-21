from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, constr
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import RegulationMatch
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

