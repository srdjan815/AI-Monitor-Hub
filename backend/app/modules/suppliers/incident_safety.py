from __future__ import annotations

import hashlib
import html
import json

SENSITIVE = (
    "secret",
    "token",
    "password",
    "authorization",
    "credential",
    "cookie",
    "api_key",
)


def incident_fingerprint(parts: dict[str, object]) -> str:
    encoded = json.dumps(
        parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def sanitize_text(value: str, limit: int) -> str:
    return html.escape(" ".join(value.replace("\x00", "").split()), quote=False)[:limit]


def sanitize_context(value: object, *, depth: int = 0) -> object:
    if depth > 4:
        return "[bounded]"
    if isinstance(value, dict):
        result: dict[str, object] = {}
        for raw_key, raw_value in list(value.items())[:50]:
            key = str(raw_key)[:100]
            if any(word in key.lower() for word in SENSITIVE):
                result[key] = "[redacted]"
            else:
                result[key] = sanitize_context(raw_value, depth=depth + 1)
        return result
    if isinstance(value, list):
        return [sanitize_context(item, depth=depth + 1) for item in value[:50]]
    if isinstance(value, str):
        lowered = value.lower()
        if "bearer " in lowered or "token=" in lowered or "password=" in lowered:
            return "[redacted]"
        if len(value) > 500:
            return {
                "hash": hashlib.sha256(value.encode()).hexdigest(),
                "length": len(value),
                "preview": sanitize_text(value, 240),
            }
        return sanitize_text(value, 500)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return sanitize_text(str(value), 500)


__all__ = ["incident_fingerprint", "sanitize_context", "sanitize_text"]
