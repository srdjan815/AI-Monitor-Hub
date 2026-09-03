from __future__ import annotations

import base64
import binascii


def encode_base64url(value: bytes) -> str:
    """Return canonical unpadded Base64URL."""
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def decode_base64url(value: str) -> bytes:
    """Decode only canonical unpadded Base64URL.

    Python's permissive decoder accepts alternate trailing characters whose
    unused padding bits decode to the same bytes. Rejecting those aliases keeps
    signed cursors and tokens byte-representation bound.
    """
    if not value or "=" in value:
        raise binascii.Error("Base64URL must be non-empty and unpadded")
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise binascii.Error("Base64URL must contain ASCII characters") from exc
    decoded = base64.b64decode(
        encoded + b"=" * (-len(encoded) % 4),
        altchars=b"-_",
        validate=True,
    )
    if encode_base64url(decoded) != value:
        raise binascii.Error("Base64URL is not canonical")
    return decoded


__all__ = ["decode_base64url", "encode_base64url"]
