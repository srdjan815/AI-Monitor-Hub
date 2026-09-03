from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class GtinNormalizationStatus(StrEnum):
    EAN13_VALID = "EAN13_VALID"
    UPC_A_CONVERTED_TO_EAN13 = "UPC_A_CONVERTED_TO_EAN13"
    MISSING = "MISSING"
    NON_NUMERIC = "NON_NUMERIC"
    UNSUPPORTED_LENGTH = "UNSUPPORTED_LENGTH"
    INVALID_CHECKSUM = "INVALID_CHECKSUM"
    PLACEHOLDER = "PLACEHOLDER"


@dataclass(frozen=True, slots=True)
class GtinNormalizationResult:
    value: str
    status: GtinNormalizationStatus
    message: str


def _has_valid_mod10_check_digit(value: str) -> bool:
    body = value[:-1]
    weighted_sum = sum(
        int(character) * (3 if (len(body) - index) % 2 else 1)
        for index, character in enumerate(body)
    )
    return (10 - weighted_sum % 10) % 10 == int(value[-1])


def normalize_to_ean13(value: object) -> GtinNormalizationResult:
    """Return a verified EAN-13 from an EAN-13 or its UPC-A representation."""
    original = str(value or "").strip()
    if not original:
        return GtinNormalizationResult(
            "", GtinNormalizationStatus.MISSING, "Barkod nije dostavljen."
        )
    if not original.isascii() or not original.isdigit():
        return GtinNormalizationResult(
            "",
            GtinNormalizationStatus.NON_NUMERIC,
            "Barkod mora sadržati samo ASCII cifre.",
        )
    if len(set(original)) == 1:
        return GtinNormalizationResult(
            "",
            GtinNormalizationStatus.PLACEHOLDER,
            "Barkod je očigledna zamenska vrednost sa ponovljenom cifrom.",
        )
    if len(original) not in {12, 13}:
        return GtinNormalizationResult(
            "",
            GtinNormalizationStatus.UNSUPPORTED_LENGTH,
            "Barkod mora imati 12 cifara (UPC-A) ili 13 cifara (EAN-13).",
        )
    if not _has_valid_mod10_check_digit(original):
        return GtinNormalizationResult(
            "",
            GtinNormalizationStatus.INVALID_CHECKSUM,
            "Kontrolna cifra barkoda nije ispravna.",
        )
    if len(original) == 12:
        converted = f"0{original}"
        if not _has_valid_mod10_check_digit(converted):
            return GtinNormalizationResult(
                "",
                GtinNormalizationStatus.INVALID_CHECKSUM,
                "UPC-A nije moguće bezbedno predstaviti kao EAN-13.",
            )
        return GtinNormalizationResult(
            converted,
            GtinNormalizationStatus.UPC_A_CONVERTED_TO_EAN13,
            "Validan UPC-A je predstavljen kao EAN-13 dodavanjem vodeće nule.",
        )
    return GtinNormalizationResult(
        original,
        GtinNormalizationStatus.EAN13_VALID,
        "Dobavljač je dostavio validan EAN-13.",
    )


__all__ = [
    "GtinNormalizationResult",
    "GtinNormalizationStatus",
    "normalize_to_ean13",
]
