from __future__ import annotations

import binascii
import hashlib
import hmac
import json
import time
from typing import Any, Final, NoReturn, Protocol

from fastapi import HTTPException, status

from app.core.base64url import decode_base64url, encode_base64url
from app.core.config import Settings
from app.core.security_context import Principal
from app.core.security_permissions import ROLE_PERMISSIONS


def _b64encode(value: bytes) -> str:
    return encode_base64url(value)


def _b64decode(value: str) -> bytes:
    return decode_base64url(value)


class AuthenticationAdapter(Protocol):
    """Replaceable token boundary for a future OIDC-backed implementation."""

    def issue_token(
        self,
        subject: str,
        roles: tuple[str, ...] = ("system_admin",),
        *,
        expires_in: int | None = None,
        actor_type: str = "user",
        not_before_in: int | None = None,
        token_id: str | None = None,
        include_token_id: bool = True,
    ) -> str: ...

    def authenticate(self, token: str) -> Principal: ...


class LocalHMACAuthenticationAdapter:
    """Strict local token adapter with additive legacy-token verification."""

    algorithm: Final[str] = "HS256"
    token_type: Final[str] = "JWT"
    maximum_token_length: Final[int] = 16_384

    def __init__(self, config: Settings) -> None:
        self.config = config

    @property
    def verification_keys(self) -> dict[str, str]:
        return {
            **self.config.auth_previous_keys,
            self.config.auth_key_id: self.config.auth_secret,
        }

    @staticmethod
    def _json_segment(value: str) -> dict[str, Any]:
        decoded = json.loads(_b64decode(value))
        if not isinstance(decoded, dict):
            raise ValueError("token segment is not an object")
        return decoded

    @staticmethod
    def _invalid() -> NoReturn:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTHENTICATION_REQUIRED",
                "message": "Invalid or expired bearer token",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    def issue_token(
        self,
        subject: str,
        roles: tuple[str, ...] = ("system_admin",),
        *,
        expires_in: int | None = None,
        actor_type: str = "user",
        not_before_in: int | None = None,
        token_id: str | None = None,
        include_token_id: bool = True,
    ) -> str:
        now = int(time.time())
        lifetime = (
            self.config.auth_token_ttl_seconds if expires_in is None else expires_in
        )
        header = {
            "alg": self.algorithm,
            "kid": self.config.auth_key_id,
            "typ": self.token_type,
        }
        payload: dict[str, Any] = {
            "aud": self.config.auth_audience,
            "exp": now + lifetime,
            "iat": now,
            "iss": self.config.auth_issuer,
            "roles": list(roles),
            "sub": subject,
            "type": actor_type,
            "ver": self.config.auth_token_version,
        }
        if not_before_in is not None:
            payload["nbf"] = now + not_before_in
        if include_token_id:
            payload["jti"] = (
                token_id
                or hashlib.sha256(
                    f"{subject}:{now}:{time.time_ns()}".encode()
                ).hexdigest()[:32]
            )
        encoded_header = _b64encode(
            json.dumps(header, separators=(",", ":"), sort_keys=True).encode()
        )
        encoded_payload = _b64encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        )
        signing_input = f"{encoded_header}.{encoded_payload}"
        signature = hmac.new(
            self.config.auth_secret.encode(),
            signing_input.encode(),
            hashlib.sha256,
        ).digest()
        return f"{signing_input}.{_b64encode(signature)}"

    def _verify_current(self, parts: list[str]) -> tuple[dict[str, Any], str]:
        encoded_header, encoded_payload, supplied_signature = parts
        header = self._json_segment(encoded_header)
        if header.get("alg") != self.algorithm or header.get("typ") != self.token_type:
            raise ValueError("unsupported token header")
        key_id = header.get("kid")
        if not isinstance(key_id, str) or key_id not in self.verification_keys:
            raise ValueError("unknown signing key")
        signing_input = f"{encoded_header}.{encoded_payload}"
        expected = hmac.new(
            self.verification_keys[key_id].encode(),
            signing_input.encode(),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected, _b64decode(supplied_signature)):
            raise ValueError("invalid signature")
        return self._json_segment(encoded_payload), key_id

    def _verify_legacy(self, parts: list[str]) -> tuple[dict[str, Any], str]:
        if not self.config.auth_allow_legacy_tokens:
            raise ValueError("legacy tokens are disabled")
        encoded_payload, supplied_signature = parts
        decoded_signature = _b64decode(supplied_signature)
        verified_key_id: str | None = None
        for key_id, secret in self.verification_keys.items():
            expected = hmac.new(
                secret.encode(), encoded_payload.encode(), hashlib.sha256
            ).digest()
            if hmac.compare_digest(expected, decoded_signature):
                verified_key_id = key_id
        if verified_key_id is None:
            raise ValueError("invalid signature")
        return self._json_segment(encoded_payload), verified_key_id

    @staticmethod
    def _integer_claim(payload: dict[str, Any], name: str) -> int:
        value = payload.get(name)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"invalid {name}")
        return value

    def _validate_time_and_protocol(
        self,
        payload: dict[str, Any],
        *,
        legacy: bool,
    ) -> int:
        now = int(time.time())
        skew = self.config.auth_clock_skew_seconds
        issued_at = self._integer_claim(payload, "iat")
        expires_at = self._integer_claim(payload, "exp")
        not_before = payload.get("nbf", issued_at)
        if isinstance(not_before, bool) or not isinstance(not_before, int):
            raise ValueError("invalid nbf")
        if issued_at > now + skew or not_before > now + skew:
            raise ValueError("token is not active")
        if now >= expires_at + skew or expires_at <= issued_at:
            raise ValueError("expired")
        if not legacy:
            if payload.get("iss") != self.config.auth_issuer:
                raise ValueError("invalid issuer")
            if payload.get("aud") != self.config.auth_audience:
                raise ValueError("invalid audience")
            version = self._integer_claim(payload, "ver")
            if version != self.config.auth_token_version:
                raise ValueError("unsupported token version")
        else:
            version = 0
        return version

    @staticmethod
    def _identity_claims(
        payload: dict[str, Any],
    ) -> tuple[str, tuple[str, ...], str, str | None]:
        subject_value = payload.get("sub")
        roles_value = payload.get("roles")
        actor_type_value = payload.get("type", "user")
        if (
            not isinstance(subject_value, str)
            or not subject_value.strip()
            or len(subject_value) > 255
            or not isinstance(roles_value, list)
            or not roles_value
            or len(roles_value) > 32
            or not all(isinstance(role, str) for role in roles_value)
            or len(set(roles_value)) != len(roles_value)
            or any(role not in ROLE_PERMISSIONS for role in roles_value)
            or not isinstance(actor_type_value, str)
            or not actor_type_value
            or len(actor_type_value) > 64
        ):
            raise ValueError("invalid principal")
        token_id_value = payload.get("jti")
        if token_id_value is not None and (
            not isinstance(token_id_value, str)
            or not token_id_value
            or len(token_id_value) > 128
        ):
            raise ValueError("invalid token identifier")
        return (
            subject_value.strip(),
            tuple(str(role) for role in roles_value),
            actor_type_value,
            token_id_value,
        )

    def _principal(
        self,
        payload: dict[str, Any],
        key_id: str,
        *,
        legacy: bool,
    ) -> Principal:
        version = self._validate_time_and_protocol(payload, legacy=legacy)
        subject, roles, actor_type, token_id = self._identity_claims(payload)
        permissions: set[str] = set()
        for role in roles:
            permissions.update(ROLE_PERMISSIONS[role])
        return Principal(
            subject=subject,
            roles=roles,
            permissions=frozenset(permissions),
            actor_type=actor_type,
            token_id=token_id,
            token_version=version,
            key_id=key_id,
        )

    def authenticate(self, token: str) -> Principal:
        try:
            if not token or len(token) > self.maximum_token_length:
                raise ValueError("invalid token length")
            parts = token.split(".")
            if len(parts) == 3 and all(parts):
                payload, key_id = self._verify_current(parts)
                return self._principal(payload, key_id, legacy=False)
            if len(parts) == 2 and all(parts):
                payload, key_id = self._verify_legacy(parts)
                return self._principal(payload, key_id, legacy=True)
            raise ValueError("invalid token shape")
        except (
            binascii.Error,
            KeyError,
            TypeError,
            UnicodeDecodeError,
            ValueError,
            json.JSONDecodeError,
        ):
            self._invalid()


__all__ = ["AuthenticationAdapter", "LocalHMACAuthenticationAdapter"]
