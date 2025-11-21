"""Lightweight helpers for looking up airports and deriving country/region info."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Callable, Dict, Optional

from airportsdata import load

from app.core.cache import get_redis
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.airport_directory import AirportDirectoryService, DIRECTORY_VERSION_KEY

# ISO 3166-1 alpha-2 codes considered part of the Americas region for baggage policy
# segmentation (North, Central, South America + Caribbean).
AMERICAS_ISO2 = {
    "AG",
    "AI",
    "AR",
    "AW",
    "BB",
    "BL",
    "BM",
    "BO",
    "BQ",
    "BR",
    "BS",
    "BZ",
    "CA",
    "CL",
    "CO",
    "CR",
    "CU",
    "CW",
    "DM",
    "DO",
    "EC",
    "FK",
    "GD",
    "GF",
    "GL",
    "GP",
    "GT",
    "GY",
    "HN",
    "HT",
    "JM",
    "KN",
    "KY",
    "LC",
    "MF",
    "MQ",
    "MS",
    "MX",
    "NI",
    "PA",
    "PE",
    "PM",
    "PR",
    "PY",
    "SR",
    "SV",
    "SX",
    "TC",
    "TT",
    "US",
    "UY",
    "VC",
    "VE",
    "VG",
    "VI",
}

logger = logging.getLogger(__name__)

_PROCESS_CACHE: Dict[str, Any] = {"version": None, "index": {}}
_SESSION_FACTORY: Callable[[], Session] = SessionLocal


def get_airport_info(iata_code: str) -> Optional[Dict[str, Any]]:
    """Return the directory entry (DB → Redis cache) for a given IATA airport code."""

    if not iata_code:
        return None
    code = iata_code.strip().upper()
    if len(code) != 3:
        return None

    index = _load_directory_index()
    record = index.get(code)
    if record:
        return record

    # Fallback to bundled airportsdata dataset
    return _airportsdata_index().get(code)


def get_country_code(iata_code: str) -> Optional[str]:
    """Return the ISO country code (alpha-2) for an airport."""

    info = get_airport_info(iata_code)
    if not info:
        return None
    country = info.get("country_code") or info.get("iso_country") or info.get("country")
    if not country:
        return None
    return str(country).upper()


def get_region_bucket(iata_code: str) -> Optional[str]:
    """Rudimentary mapping of airports to airline baggage regions."""

    iso = get_country_code(iata_code)
    if not iso:
        return None
    iso = iso.upper()
    if iso == "BR":
        return "brazil"
    if iso in AMERICAS_ISO2:
        return "americas"
    return "international_non_americas"


def _load_directory_index() -> Dict[str, Dict[str, Any]]:
    version = _directory_version()
    cached_version = _PROCESS_CACHE.get("version")
    if cached_version == version and _PROCESS_CACHE.get("index"):
        return _PROCESS_CACHE["index"]

    try:
        with _SESSION_FACTORY() as db:
            service = AirportDirectoryService(db)
            index = service.as_index()
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("공항 디렉터리 조회 실패, 내장 데이터셋으로 대체합니다: %s", exc)
        _PROCESS_CACHE["version"] = None
        _PROCESS_CACHE["index"] = {}
        return {}

    normalized = {code.upper(): data for code, data in index.items()}
    _PROCESS_CACHE["version"] = version
    _PROCESS_CACHE["index"] = normalized
    return normalized


def _directory_version() -> str:
    try:
        value = get_redis().get(DIRECTORY_VERSION_KEY)
        return value or "0"
    except Exception:  # pragma: no cover - Redis가 없을 때
        return "0"


@lru_cache(maxsize=1)
def _airportsdata_index() -> Dict[str, Dict[str, Any]]:
    """Load the bundled airportsdata dataset once per process."""

    return load("IATA")


def set_airport_directory_session_factory(factory: Callable[[], Session]) -> None:
    """테스트나 백그라운드 작업에서 별도의 세션 팩토리를 주입할 때 사용."""

    global _SESSION_FACTORY
    _SESSION_FACTORY = factory
    _PROCESS_CACHE["version"] = None
    _PROCESS_CACHE["index"] = {}


def reset_airport_directory_session_factory() -> None:
    set_airport_directory_session_factory(SessionLocal)


__all__ = [
    "get_airport_info",
    "get_country_code",
    "get_region_bucket",
    "set_airport_directory_session_factory",
    "reset_airport_directory_session_factory",
]

