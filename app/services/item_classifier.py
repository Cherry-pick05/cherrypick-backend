"""High-level orchestrator that combines LLM and dictionary classifiers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.services.dict_classifier import DictionaryClassifier, DictionaryClassification, get_dictionary_classifier
from app.services.llm_classifier import LLMClassification, LLMClassificationError, classify_with_llm


@dataclass(slots=True)
class ClassificationResult:
    raw_label: str
    norm_label: str
    canonical: Optional[str]
    confidence: Optional[float]
    candidates: List[str]
    categories: List[dict]
    abstain: bool
    decided_by: str
    signals: dict
    model_info: dict | None


def classify_label(raw_label: str, locale: str | None = None) -> ClassificationResult:
    llm_result: LLMClassification | None = None
    llm_error: str | None = None

    try:
        llm_result = classify_with_llm(raw_label, locale=locale)
    except LLMClassificationError as exc:
        llm_error = str(exc)

    if llm_result and not llm_result.abstain and llm_result.top:
        canonical = llm_result.top.get("key")
        candidates = [item["key"] for item in llm_result.categories[:3]]
        signals = dict(llm_result.signals)
        if llm_error:
            signals["llm_error"] = llm_error
        return ClassificationResult(
            raw_label=raw_label,
            norm_label=llm_result.norm_label,
            canonical=canonical,
            confidence=llm_result.confidence,
            candidates=candidates,
            categories=llm_result.categories,
            abstain=False,
            decided_by="llm_classifier",
            signals=signals,
            model_info=llm_result.model_info or {"name": "gemini"},
        )

    dict_classifier: DictionaryClassifier = get_dictionary_classifier()
    dict_result: DictionaryClassification = dict_classifier.classify(raw_label)

    signals = dict(dict_result.signals)
    if llm_result:
        signals["llm_abstain"] = True
    if llm_error:
        signals["llm_error"] = llm_error

    return ClassificationResult(
        raw_label=raw_label,
        norm_label=dict_result.norm_label,
        canonical=dict_result.canonical,
        confidence=dict_result.confidence,
        candidates=dict_result.candidates,
        categories=dict_result.categories,
        abstain=dict_result.abstain,
        decided_by="dict_classifier",
        signals=signals,
        model_info={"name": "dictionary_classifier"},
    )

