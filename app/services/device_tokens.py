from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any, TypedDict

from app.core.config import settings


class DeviceTokenError(Exception):
    """Raised when a device token cannot be issued or verified."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail or code
        super().__init__(self.detail)


class TokenPayload(TypedDict):
    v: int
    uid: int
    du: str
    iat: int
    exp: int


@dataclass(slots=True)
class IssuedToken:
    token: str
    payload: TokenPayload


def issue_device_token(user_id: int, device_uuid: str, ttl_seconds: int | None = None) -> IssuedToken:
    if not device_uuid:
        raise DeviceTokenError("missing_device_uuid")
    ttl = ttl_seconds or settings.device_token_ttl_seconds
    now = int(time.time())
    payload: TokenPayload = {
        "v": settings.device_token_version,
        "uid": int(user_id),
        "du": device_uuid,
        "iat": now,
        "exp": now + ttl,
    }
    encoded = _encode_payload(payload)
    signature = _sign(encoded)
    token = f"{encoded}.{signature}"
    return IssuedToken(token=token, payload=payload)


def verify_device_token(token: str) -> TokenPayload:
    if not token:
        raise DeviceTokenError("token_missing")
    parts = token.split(".")
    if len(parts) != 2:
        raise DeviceTokenError("token_malformed")
    payload_part, signature_part = parts
    expected_signature = _sign(payload_part)
    if not hmac.compare_digest(signature_part, expected_signature):
        raise DeviceTokenError("invalid_signature")

    try:
        payload_dict: dict[str, Any] = json.loads(_decode_payload(payload_part))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise DeviceTokenError("token_corrupted") from exc

    required_fields = {"v", "uid", "du", "iat", "exp"}
    if not required_fields.issubset(payload_dict):
        raise DeviceTokenError("token_fields_missing")

    payload: TokenPayload = {
        "v": int(payload_dict["v"]),
        "uid": int(payload_dict["uid"]),
        "du": str(payload_dict["du"]),
        "iat": int(payload_dict["iat"]),
        "exp": int(payload_dict["exp"]),
    }

    if payload["v"] != settings.device_token_version:
        raise DeviceTokenError("token_version_mismatch")

    now = int(time.time())
    if payload["exp"] < now:
        raise DeviceTokenError("token_expired")

    return payload


def token_expires_in(payload: TokenPayload) -> int:
    return max(payload["exp"] - int(time.time()), 0)


def _encode_payload(payload: TokenPayload) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _decode_payload(encoded: str) -> str:
    padding = "=" * (-len(encoded) % 4)
    raw = base64.urlsafe_b64decode(encoded + padding)
    return raw.decode("utf-8")


def _sign(message: str) -> str:
    secret = settings.guest_hmac_secret.encode("utf-8")
    digest = hmac.new(secret, msg=message.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

