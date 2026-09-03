from __future__ import annotations

import binascii
import hashlib
import hmac
import json
from typing import Any

from app.core.base64url import decode_base64url, encode_base64url
from app.core.config import settings
from app.core.limits import MAX_CURSOR_CHARS


class InvalidCursorError(ValueError):
    pass


def _encode(value: bytes) -> str:
    return encode_base64url(value)


def _decode(value: str) -> bytes:
    return decode_base64url(value)


def _filter_digest(filters: dict[str, Any]) -> str:
    serialized = json.dumps(
        filters,
        default=str,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(serialized).hexdigest()


def encode_cursor(
    resource: str,
    filters: dict[str, Any],
    position: list[str | int],
) -> str:
    payload = {
        "v": 1,
        "resource": resource,
        "filters": _filter_digest(filters),
        "position": position,
    }
    encoded = _encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    )
    signature = hmac.new(
        settings.auth_secret.encode(),
        encoded.encode(),
        hashlib.sha256,
    ).digest()
    return f"{encoded}.{_encode(signature)}"


def decode_cursor(
    cursor: str,
    resource: str,
    filters: dict[str, Any],
) -> list[str | int]:
    try:
        if len(cursor) > MAX_CURSOR_CHARS:
            raise InvalidCursorError("Cursor exceeds the maximum encoded length")
        encoded, supplied_signature = cursor.split(".", 1)
        expected_signature = hmac.new(
            settings.auth_secret.encode(),
            encoded.encode(),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected_signature, _decode(supplied_signature)):
            raise InvalidCursorError("Cursor signature is invalid")
        payload = json.loads(_decode(encoded))
        if payload.get("v") != 1 or payload.get("resource") != resource:
            raise InvalidCursorError("Cursor resource or version is invalid")
        if payload.get("filters") != _filter_digest(filters):
            raise InvalidCursorError("Cursor does not match the active filters")
        position = payload.get("position")
        if not isinstance(position, list) or not position:
            raise InvalidCursorError("Cursor position is invalid")
        if not all(isinstance(value, (str, int)) for value in position):
            raise InvalidCursorError("Cursor position contains invalid values")
        return position
    except (
        binascii.Error,
        UnicodeDecodeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        if isinstance(exc, InvalidCursorError):
            raise
        raise InvalidCursorError("Cursor is malformed") from exc
