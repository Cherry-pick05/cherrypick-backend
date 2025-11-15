"""Dictionary-based fallback classifier for item labels."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from functools import cached_property
from typing import DefaultDict, Dict, List

from app.services.classifier_data import get_allowed_keys, get_synonym_map


SPACE_RE = re.compile(r"\s+")


def normalize_label(label: str) -> str:
    if not label:
        return ""
    text = unicodedata.normalize("NFKC", label)
    text = SPACE_RE.sub(" ", text.strip().lower())
    text = text.replace("e-cig", "ecig").replace("보조 배터리", "보조배터리")
    return text


RULES: tuple[tuple[re.Pattern[str], str, float], ...] = (
    (re.compile(r"(spray|스프레이|aerosol|분사|propellant|butane)"), "aerosol", 0.6),
    (re.compile(r"(vape|ecig|전자담배)"), "e_cigarette_device", 0.6),
    (re.compile(r"(zippo|torch|토치|버너)"), "lighter", 0.4),
    (re.compile(r"(knife|칼|가위|scissor)"), "knife", 0.6),
    (re.compile(r"(toner|로션|세럼|essence|에센스|emulsion)"), "cosmetics_liquid", 0.4),
    (re.compile(r"(dry ice|드라이아이스)"), "dry_ice", 0.8),
)


@dataclass(slots=True)
class DictionaryClassification:
    canonical: str
    confidence: float
    categories: list[dict]
    candidates: list[str]
    abstain: bool
    norm_label: str
    signals: dict


class DictionaryClassifier:
    def __init__(self) -> None:
        self.allowed_keys = get_allowed_keys()
        self.synonym_map = get_synonym_map()

    @cached_property
    def _exact_map(self) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for canonical in self.allowed_keys:
            mapping[normalize_label(canonical)] = canonical
            for entry in self.synonym_map.get(canonical, []):
                if entry.get("match_type", "substring") == "exact":
                    mapping[normalize_label(entry["value"])] = canonical
        return mapping

    @cached_property
    def _partial_entries(self) -> list[dict]:
        entries: list[dict] = []
        for canonical in self.allowed_keys:
            for entry in self.synonym_map.get(canonical, []):
                if entry.get("match_type", "substring") != "exact":
                    token = normalize_label(entry["value"])
                    data = {
                        "canonical": canonical,
                        "token": token,
                        "priority": int(entry.get("priority", 0)),
                        "match_type": entry.get("match_type", "substring"),
                    }
                    if data["match_type"] == "regex":
                        data["pattern"] = re.compile(entry["value"])
                    entries.append(data)
        return entries

    def classify(self, raw_label: str) -> DictionaryClassification:
        norm = normalize_label(raw_label)
        if not norm:
            return self._empty(norm)

        exact_hit = self._exact_map.get(norm)
        if exact_hit:
            payload = {
                "canonical": exact_hit,
                "confidence": 0.95,
                "categories": [{"key": exact_hit, "score": 1.0}],
                "candidates": [exact_hit],
                "abstain": False,
                "norm_label": norm,
                "signals": {"mode": "exact", "hits": {exact_hit: [norm]}, "rules": []},
            }
            return DictionaryClassification(**payload)

        scores: DefaultDict[str, float] = DefaultDict(float)
        hits: DefaultDict[str, List[str]] = DefaultDict(list)

        for entry in self._partial_entries:
            canonical = entry["canonical"]
            match_type = entry["match_type"]
            token = entry["token"]
            matched = False
            if match_type == "substring":
                matched = token in norm
            elif match_type == "regex":
                pattern: re.Pattern[str] = entry["pattern"]
                matched = bool(pattern.search(norm))

            if matched:
                weight = 1.0 + 0.2 * entry["priority"] + min(0.3, len(token) / 20.0)
                scores[canonical] += weight
                hits[canonical].append(token)

        rule_hits: list[dict] = []
        for pattern, canonical, weight in RULES:
            if pattern.search(norm):
                scores[canonical] += weight
                rule_hits.append({"rule": pattern.pattern, "canonical": canonical, "weight": weight})

        if not scores:
            return self._empty(norm, mode="none", rule_hits=rule_hits)

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        categories = [{"key": key, "score": round(score, 3)} for key, score in ranked[:5]]
        top_key, top_score = ranked[0]
        confidence = self._score_to_conf(top_score)
        candidates = [item["key"] for item in categories[:3]]
        abstain = confidence < 0.5
        signals = {"mode": "partial", "hits": dict(hits), "rules": rule_hits}

        return DictionaryClassification(
            canonical=top_key,
            confidence=confidence,
            categories=categories,
            candidates=candidates,
            abstain=abstain,
            norm_label=norm,
            signals=signals,
        )

    def _empty(self, norm_label: str, mode: str = "empty", rule_hits: list[dict] | None = None) -> DictionaryClassification:
        canonical = "other" if "other" in self.allowed_keys else self.allowed_keys[-1]
        signals = {"mode": mode, "hits": {}, "rules": rule_hits or []}
        return DictionaryClassification(
            canonical=canonical,
            confidence=0.3,
            categories=[{"key": canonical, "score": 0.3}],
            candidates=[canonical],
            abstain=True,
            norm_label=norm_label,
            signals=signals,
        )

    @staticmethod
    def _score_to_conf(score: float) -> float:
        value = 1 / (1 + math.exp(-(0.8 * score - 0.5)))
        return round(value, 4)


_DICT_CLASSIFIER: DictionaryClassifier | None = None


def get_dictionary_classifier() -> DictionaryClassifier:
    global _DICT_CLASSIFIER
    if _DICT_CLASSIFIER is None:
        _DICT_CLASSIFIER = DictionaryClassifier()
    return _DICT_CLASSIFIER

