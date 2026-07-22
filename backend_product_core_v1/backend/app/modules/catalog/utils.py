from __future__ import annotations

import re
import unicodedata


_TRANSLITERATION = str.maketrans(
    {
        "đ": "dj",
        "Đ": "dj",
        "ć": "c",
        "Ć": "c",
        "č": "c",
        "Č": "c",
        "š": "s",
        "Š": "s",
        "ž": "z",
        "Ž": "z",
    }
)


def stable_code(value: str) -> str:
    """Create a stable ASCII identifier while preserving the original display name."""
    transliterated = value.translate(_TRANSLITERATION)
    normalized = unicodedata.normalize("NFKD", transliterated)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    code = re.sub(r"[^a-z0-9]+", "_", ascii_value).strip("_")
    if not code:
        raise ValueError("Nije moguće napraviti interni kod iz zadatog naziva")
    return code
