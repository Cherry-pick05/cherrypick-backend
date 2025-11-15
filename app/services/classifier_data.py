"""Utilities for loading classifier taxonomy assets from the data directory."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "taxonomy"


def _read_json(name: str) -> Any:
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Classifier asset not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def get_taxonomy_payload() -> Dict[str, Any]:
    return _read_json("taxonomy.json")


@lru_cache(maxsize=1)
def get_allowed_keys() -> tuple[str, ...]:
    payload = get_taxonomy_payload()
    keys = payload.get("allowed_keys", [])
    if not keys:
        raise ValueError("taxonomy.json must include at least one allowed key")
    return tuple(keys)


@lru_cache(maxsize=1)
def get_display_names() -> Dict[str, str]:
    payload = get_taxonomy_payload()
    return payload.get("display_names", {})


@lru_cache(maxsize=1)
def get_synonym_map() -> Dict[str, List[Dict[str, Any]]]:
    data = _read_json("synonyms.json")
    if not isinstance(data, dict):
        raise ValueError("synonyms.json must be an object mapping canonical key to entries")
    return data

