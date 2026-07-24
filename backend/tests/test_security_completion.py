from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import LocalHMACAuthenticationAdapter


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql+asyncpg://app:test@db/app",
        "auth_secret": "a" * 48,
        "auth_key_id": "current",
        "auth_issuer": "test-issuer",
        "auth_audience": "test-audience",
        "auth_clock_skew_seconds": 5,
    }
    values.update(overrides)
    return Settings(**values)


def _encode(value: dict[str, Any]) -> str:
    serialized = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(serialized).rstrip(b"=").decode()


def _decode(value: str) -> dict[str, Any]:
    padded = value + "=" * (-len(value) % 4)
    decoded = json.loads(base64.urlsafe_b64decode(padded))
    assert isinstance(decoded, dict)
    return decoded


def _signed(
    header: dict[str, Any],
    payload: dict[str, Any],
    secret: str,
) -> str:
    signing_input = f"{_encode(header)}.{_encode(payload)}"
    signature = hmac.new(
        secret.encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    return f"{signing_input}.{encoded_signature}"


def _legacy_token(config: Settings) -> str:
    now = int(time.time())
    encoded = _encode(
        {
            "sub": "legacy-user",
            "roles": ["read_only"],
            "type": "user",
            "iat": now,
            "exp": now + 60,
        }
    )
    signature = hmac.new(
        config.auth_secret.encode(), encoded.encode(), hashlib.sha256
    ).digest()
    return f"{encoded}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def _assert_unauthorized(adapter: LocalHMACAuthenticationAdapter, token: str) -> None:
    with pytest.raises(HTTPException) as captured:
        adapter.authenticate(token)
    assert captured.value.status_code == 401
    assert captured.value.detail["code"] == "AUTHENTICATION_REQUIRED"


def test_current_token_has_fixed_header_and_validated_claims() -> None:
    adapter = LocalHMACAuthenticationAdapter(_settings())
    token = adapter.issue_token(
        "operator",
        ("read_only",),
        token_id="known-jti",
    )
    header, payload, _ = token.split(".")
    assert _decode(header) == {
        "alg": "HS256",
        "kid": "current",
        "typ": "JWT",
    }
    claims = _decode(payload)
    assert claims["iss"] == "test-issuer"
    assert claims["aud"] == "test-audience"
    assert claims["ver"] == 1
    assert claims["jti"] == "known-jti"
    principal = adapter.authenticate(token)
    assert principal.subject == "operator"
    assert principal.roles == ("read_only",)
    assert principal.token_id == "known-jti"
    assert principal.token_version == 1
    assert principal.key_id == "current"


def test_tamper_and_role_escalation_are_rejected() -> None:
    config = _settings()
    adapter = LocalHMACAuthenticationAdapter(config)
    token = adapter.issue_token("reader", ("read_only",))
    header_segment, payload_segment, signature = token.split(".")
    payload = _decode(payload_segment)
    payload["roles"] = ["system_admin"]
    tampered = f"{header_segment}.{_encode(payload)}.{signature}"
    _assert_unauthorized(adapter, tampered)

    payload["roles"] = ["not-a-real-role"]
    signed_unknown_role = _signed(
        _decode(header_segment),
        payload,
        config.auth_secret,
    )
    _assert_unauthorized(adapter, signed_unknown_role)


def test_noncanonical_equivalent_signature_is_rejected() -> None:
    adapter = LocalHMACAuthenticationAdapter(_settings())
    token = adapter.issue_token("reader", ("read_only",))
    header, payload, signature = token.split(".")
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    final_index = alphabet.index(signature[-1])
    assert final_index % 4 == 0
    equivalent_signature = f"{signature[:-1]}{alphabet[final_index + 1]}"
    assert base64.urlsafe_b64decode(
        f"{signature}=",
    ) == base64.urlsafe_b64decode(f"{equivalent_signature}=")
    _assert_unauthorized(
        adapter,
        f"{header}.{payload}.{equivalent_signature}",
    )


@pytest.mark.parametrize(
    "token",
    [
        "",
        "one",
        "one.two.three.four",
        "..",
        "not-base64.not-base64.not-base64",
        "x" * 16_385,
    ],
)
def test_malformed_tokens_are_rejected(token: str) -> None:
    _assert_unauthorized(LocalHMACAuthenticationAdapter(_settings()), token)


def test_algorithm_and_unknown_key_id_are_rejected_even_when_signed() -> None:
    config = _settings()
    adapter = LocalHMACAuthenticationAdapter(config)
    token = adapter.issue_token("reader", ("read_only",))
    header_segment, payload_segment, _ = token.split(".")
    payload = _decode(payload_segment)
    header = _decode(header_segment)

    header["alg"] = "none"
    _assert_unauthorized(
        adapter,
        _signed(header, payload, config.auth_secret),
    )
    header["alg"] = "HS256"
    header["kid"] = "attacker-controlled"
    _assert_unauthorized(
        adapter,
        _signed(header, payload, config.auth_secret),
    )


def test_issuer_audience_and_version_are_bound_to_verifier() -> None:
    source = LocalHMACAuthenticationAdapter(_settings())
    token = source.issue_token("reader", ("read_only",))
    _assert_unauthorized(
        LocalHMACAuthenticationAdapter(_settings(auth_issuer="other")),
        token,
    )
    _assert_unauthorized(
        LocalHMACAuthenticationAdapter(_settings(auth_audience="other")),
        token,
    )
    _assert_unauthorized(
        LocalHMACAuthenticationAdapter(_settings(auth_token_version=2)),
        token,
    )


def test_active_and_previous_key_rotation() -> None:
    old_config = _settings(auth_secret="o" * 48, auth_key_id="old")
    old_token = LocalHMACAuthenticationAdapter(old_config).issue_token(
        "reader", ("read_only",)
    )
    rotated_config = _settings(
        auth_secret="n" * 48,
        auth_key_id="new",
        auth_previous_keys={"old": "o" * 48},
    )
    rotated = LocalHMACAuthenticationAdapter(rotated_config)
    assert rotated.authenticate(old_token).key_id == "old"
    new_token = rotated.issue_token("reader", ("read_only",))
    assert _decode(new_token.split(".")[0])["kid"] == "new"
    _assert_unauthorized(
        LocalHMACAuthenticationAdapter(
            _settings(auth_secret="n" * 48, auth_key_id="new")
        ),
        old_token,
    )


def test_active_key_id_cannot_be_shadowed_by_previous_key() -> None:
    with pytest.raises(ValidationError):
        _settings(
            auth_key_id="duplicate",
            auth_previous_keys={"duplicate": "p" * 48},
        )


def test_expiry_not_before_and_clock_skew(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    issued_at = 2_000_000_000
    monkeypatch.setattr("app.core.security.time.time", lambda: issued_at)
    adapter = LocalHMACAuthenticationAdapter(_settings(auth_clock_skew_seconds=5))
    token = adapter.issue_token(
        "reader",
        ("read_only",),
        expires_in=10,
        not_before_in=4,
    )
    assert adapter.authenticate(token).subject == "reader"

    future = adapter.issue_token(
        "reader",
        ("read_only",),
        expires_in=10,
        not_before_in=6,
    )
    _assert_unauthorized(adapter, future)

    monkeypatch.setattr("app.core.security.time.time", lambda: issued_at + 12)
    assert adapter.authenticate(token).subject == "reader"
    monkeypatch.setattr("app.core.security.time.time", lambda: issued_at + 15)
    _assert_unauthorized(adapter, token)


def test_legacy_two_part_token_compatibility_is_explicit() -> None:
    enabled_config = _settings(auth_allow_legacy_tokens=True)
    token = _legacy_token(enabled_config)
    principal = LocalHMACAuthenticationAdapter(enabled_config).authenticate(token)
    assert principal.subject == "legacy-user"
    assert principal.token_version == 0

    disabled = LocalHMACAuthenticationAdapter(_settings(auth_allow_legacy_tokens=False))
    _assert_unauthorized(disabled, token)
