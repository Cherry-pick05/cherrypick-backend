from __future__ import annotations

from typing import Any

from app.core.config import settings


def build_bootstrap_config() -> dict[str, Any]:
    return {
        "safe_mode": settings.safe_mode_default,
        "supported_locales": settings.supported_locales,
        "units": settings.units_defaults,
        "ui_flags": settings.ui_flags_defaults,
        "rule_manifest_version": settings.rules_manifest_version,
        "taxonomy_manifest_version": settings.taxonomy_manifest_version,
    }

