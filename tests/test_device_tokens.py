from __future__ import annotations

import pytest

from app.services import device_tokens
from app.services.device_tokens import DeviceTokenError, issue_device_token, verify_device_token


def test_issue_and_verify_device_token(monkeypatch):
    monkeypatch.setattr(device_tokens.time, "time", lambda: 1_000)
    issued = issue_device_token(user_id=10, device_uuid="device-abc", ttl_seconds=60)
    payload = verify_device_token(issued.token)

    assert payload["uid"] == 10
    assert payload["du"] == "device-abc"
    assert payload["iat"] == 1_000
    assert payload["exp"] == 1_060


def test_expired_token_raises(monkeypatch):
    monkeypatch.setattr(device_tokens.time, "time", lambda: 1_000)
    issued = issue_device_token(user_id=10, device_uuid="device-abc", ttl_seconds=1)

    monkeypatch.setattr(device_tokens.time, "time", lambda: 2_000)
    with pytest.raises(DeviceTokenError) as exc:
        verify_device_token(issued.token)

    assert exc.value.code == "token_expired"


def test_tampered_token_fails(monkeypatch):
    monkeypatch.setattr(device_tokens.time, "time", lambda: 1_000)
    issued = issue_device_token(user_id=10, device_uuid="device-abc", ttl_seconds=60)

    parts = issued.token.split(".")
    assert len(parts) == 2
    tampered = f"{parts[0]}.AAAA"

    with pytest.raises(DeviceTokenError) as exc:
        verify_device_token(tampered)

    assert exc.value.code in {"token_malformed", "invalid_signature"}

