"""Lightweight helpers for looking up airports and deriving country/region info."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, Optional

from airportsdata import load

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


@lru_cache(maxsize=1)
def _airport_index() -> Dict[str, Dict[str, Any]]:
    """Load the IATA airport dataset once per process."""

    return load("IATA")


def get_airport_info(iata_code: str) -> Optional[Dict[str, Any]]:
    """Return the dataset entry for a given IATA airport code."""

    if not iata_code:
        return None
    return _airport_index().get(iata_code.upper())


def get_country_code(iata_code: str) -> Optional[str]:
    """Return the ISO country code (alpha-2) for an airport."""

    info = get_airport_info(iata_code)
    if not info:
        return None
    return info.get("iso_country") or info.get("country")


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


__all__ = [
    "get_airport_info",
    "get_country_code",
    "get_region_bucket",
]

