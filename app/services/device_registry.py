from __future__ import annotations

import hashlib
import secrets
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    DeviceRecoveryCode,
    ItemImage,
    RegulationMatch,
    Trip,
    User,
    UserConsent,
)


@dataclass(slots=True)
class DeviceRegistrationResult:
    user: User
    feature_flags: dict[str, Any]
    ab_test_bucket: str


@dataclass(slots=True)
class RecoveryCodeResult:
    code: str
    expires_at: datetime


class DeviceRegistryError(Exception):
    def __init__(self, code: str, status_code: int = 400) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(code)


class DeviceRegistry:
    def __init__(self, db: Session) -> None:
        self.db = db

    def register_device(self, payload: dict[str, Any], accept_language: str | None) -> DeviceRegistrationResult:
        device_uuid = payload["device_uuid"].strip()
        user = self._get_or_create_user(device_uuid)
        feature_flags, ab_bucket = self._apply_profile(user, payload, accept_language)
        self.db.commit()
        self.db.refresh(user)
        return DeviceRegistrationResult(user=user, feature_flags=feature_flags, ab_test_bucket=ab_bucket)

    def update_user(self, user: User, payload: dict[str, Any], accept_language: str | None) -> DeviceRegistrationResult:
        feature_flags, ab_bucket = self._apply_profile(user, payload, accept_language)
        self.db.commit()
        self.db.refresh(user)
        return DeviceRegistrationResult(user=user, feature_flags=feature_flags, ab_test_bucket=ab_bucket)

    def record_consent(self, user: User, payload: dict[str, Any]) -> UserConsent:
        consent = self.db.scalar(select(UserConsent).where(UserConsent.user_id == user.user_id))
        if not consent:
            consent = UserConsent(user_id=user.user_id)
            self.db.add(consent)
        consent.terms_required = bool(payload["terms_required"])
        consent.privacy_required = bool(payload["privacy_required"])
        consent.marketing_opt_in = bool(payload.get("marketing_opt_in", False))
        consent.crash_opt_in = bool(payload.get("crash_opt_in", False))
        consent.consent_version = payload.get("version")
        self.db.commit()
        self.db.refresh(consent)
        return consent

    def generate_recovery_code(self, user: User) -> RecoveryCodeResult:
        now = self._now()
        active_codes = self.db.scalars(
            select(DeviceRecoveryCode).where(
                DeviceRecoveryCode.user_id == user.user_id,
                DeviceRecoveryCode.redeemed_at.is_(None),
                DeviceRecoveryCode.revoked_at.is_(None),
            )
        ).all()
        for record in active_codes:
            record.revoked_at = now

        code = self._generate_code()
        record = DeviceRecoveryCode(
            user_id=user.user_id,
            code_hash=self._hash_code(code),
            previous_device_uuid=user.device_uuid,
            expires_at=now + timedelta(hours=settings.device_recovery_code_ttl_hours),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return RecoveryCodeResult(code=code, expires_at=record.expires_at)

    def redeem_recovery_code(
        self,
        code: str,
        new_device_payload: dict[str, Any],
        accept_language: str | None,
    ) -> DeviceRegistrationResult:
        code_hash = self._hash_code(code)
        now = self._now()
        record = self.db.scalar(
            select(DeviceRecoveryCode)
            .where(
                DeviceRecoveryCode.code_hash == code_hash,
                DeviceRecoveryCode.revoked_at.is_(None),
                DeviceRecoveryCode.redeemed_at.is_(None),
                DeviceRecoveryCode.expires_at > now,
            )
            .order_by(DeviceRecoveryCode.created_at.desc())
        )
        if not record:
            raise DeviceRegistryError("recovery_code_invalid", status_code=404)

        user = self.db.get(User, record.user_id)
        if not user:
            raise DeviceRegistryError("user_not_found", status_code=404)

        target_uuid = new_device_payload["device_uuid"].strip()
        placeholder = self._get_user_by_uuid(target_uuid)
        if placeholder and placeholder.user_id != user.user_id:
            self._merge_users(primary=user, secondary=placeholder)

        user.device_uuid = target_uuid
        record.redeemed_at = now
        feature_flags, ab_bucket = self._apply_profile(user, new_device_payload, accept_language)
        self.db.commit()
        self.db.refresh(user)
        return DeviceRegistrationResult(user=user, feature_flags=feature_flags, ab_test_bucket=ab_bucket)

    def _get_or_create_user(self, device_uuid: str) -> User:
        user = self._get_user_by_uuid(device_uuid)
        if user:
            return user
        user = User(device_uuid=device_uuid)
        self.db.add(user)
        self.db.flush()
        return user

    def _get_user_by_uuid(self, device_uuid: str) -> User | None:
        if not device_uuid:
            return None
        stmt = select(User).where(User.device_uuid == device_uuid)
        return self.db.scalar(stmt)

    def _apply_profile(self, user: User, payload: dict[str, Any], accept_language: str | None) -> tuple[dict[str, Any], str]:
        locale = self._resolve_locale(payload.get("locale"), accept_language, user.locale)
        profile = self._build_profile(flags=user.flags, payload=payload, locale=locale)
        feature_flags = deepcopy(user.flags.get("feature_flags")) if user.flags else None
        if not feature_flags:
            feature_flags = deepcopy(settings.feature_flags_defaults)
        ab_bucket = (user.flags or {}).get("ab_test_bucket")
        if not ab_bucket:
            fallback_uuid = payload.get("device_uuid") or user.device_uuid or ""
            ab_bucket = self._assign_ab_bucket(fallback_uuid)

        next_flags = deepcopy(user.flags) if user.flags else {}
        next_flags["profile"] = profile
        next_flags["feature_flags"] = feature_flags
        next_flags["ab_test_bucket"] = ab_bucket

        user.flags = next_flags
        user.locale = locale
        user.last_seen_at = self._now()
        self.db.add(user)
        return feature_flags, ab_bucket

    def _build_profile(self, flags: dict[str, Any] | None, payload: dict[str, Any], locale: str) -> dict[str, Any]:
        profile = deepcopy((flags or {}).get("profile", {}))
        profile.setdefault("device_uuid", payload.get("device_uuid"))
        profile["locale"] = locale
        for key in ("app_version", "os", "model", "timezone"):
            value = payload.get(key)
            if value:
                profile[key] = value
        return profile

    def _resolve_locale(self, explicit: str | None, accept_language: str | None, fallback: str | None) -> str:
        candidates = settings.supported_locales
        if explicit and explicit in candidates:
            return explicit
        if accept_language:
            for token in accept_language.split(","):
                code = token.strip().split(";")[0]
                if not code:
                    continue
                if code in candidates:
                    return code
                prefix = code.split("-")[0]
                for cand in candidates:
                    if cand.startswith(prefix):
                        return cand
        if fallback:
            return fallback
        return candidates[0]

    def _assign_ab_bucket(self, device_uuid: str) -> str:
        buckets = settings.ab_test_buckets or ["control"]
        digest = hashlib.sha1(device_uuid.encode("utf-8")).hexdigest()
        index = int(digest[:8], 16) % len(buckets)
        return buckets[index]

    def _generate_code(self) -> str:
        alphabet = settings.device_recovery_code_charset or "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        length = max(6, min(settings.device_recovery_code_length, 12))
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def _hash_code(self, code: str) -> str:
        return hashlib.sha256(code.strip().upper().encode("utf-8")).hexdigest()

    def _merge_users(self, primary: User, secondary: User) -> None:
        if primary.user_id == secondary.user_id:
            return
        for model in (Trip, ItemImage, RegulationMatch):
            self.db.execute(
                update(model)
                .where(model.user_id == secondary.user_id)
                .values(user_id=primary.user_id)
            )
        self.db.flush()
        self.db.delete(secondary)

    @staticmethod
    def _now() -> datetime:
        return datetime.utcnow()

