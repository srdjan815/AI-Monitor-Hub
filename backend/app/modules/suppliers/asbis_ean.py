from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.modules.suppliers.gtin_normalization import (
    GtinNormalizationStatus,
    normalize_to_ean13,
)


class AsbisEanStatus(StrEnum):
    MATCH = "MATCH"
    PRIMARY_ONLY = "PRIMARY_ONLY"
    SECONDARY_ONLY = "SECONDARY_ONLY"
    PRIMARY_VALID_SECONDARY_INVALID = "PRIMARY_VALID_SECONDARY_INVALID"
    SECONDARY_VALID_PRIMARY_INVALID = "SECONDARY_VALID_PRIMARY_INVALID"
    CONFLICT = "CONFLICT"
    MISSING = "MISSING"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class AsbisEanResolution:
    value: str
    status: AsbisEanStatus
    message: str


def is_valid_ean13(value: object) -> bool:
    """Compatibility helper backed by the shared GTIN policy."""
    result = normalize_to_ean13(value)
    return result.status == GtinNormalizationStatus.EAN13_VALID


def resolve_asbis_ean(primary: object, secondary: object) -> AsbisEanResolution:
    """Resolve ASBIS price-feed EAN against the catalog ATTR_EAN Code."""
    first_source = str(primary or "").strip()
    second_source = str(secondary or "").strip()
    first_result = normalize_to_ean13(first_source)
    second_result = normalize_to_ean13(second_source)
    first = first_result.value
    second = second_result.value
    first_valid = bool(first)
    second_valid = bool(second)

    if first_valid and second_valid:
        if first == second:
            return AsbisEanResolution(
                first,
                AsbisEanStatus.MATCH,
                "EAN i ATTR_EAN Code sadrže isti validan EAN-13.",
            )
        return AsbisEanResolution(
            "",
            AsbisEanStatus.CONFLICT,
            "EAN i ATTR_EAN Code sadrže različite validne EAN-13 vrednosti.",
        )
    if first_valid:
        status = (
            AsbisEanStatus.PRIMARY_VALID_SECONDARY_INVALID
            if second_source
            else AsbisEanStatus.PRIMARY_ONLY
        )
        message = (
            "Korišćen je validan EAN; ATTR_EAN Code nije validan EAN-13."
            if second_source
            else "Korišćen je validan EAN; ATTR_EAN Code je prazan."
        )
        return AsbisEanResolution(first, status, message)
    if second_valid:
        status = (
            AsbisEanStatus.SECONDARY_VALID_PRIMARY_INVALID
            if first_source
            else AsbisEanStatus.SECONDARY_ONLY
        )
        message = (
            "Korišćen je validan ATTR_EAN Code; EAN nije validan EAN-13."
            if first_source
            else "Korišćen je validan ATTR_EAN Code; EAN je prazan."
        )
        return AsbisEanResolution(second, status, message)
    if not first_source and not second_source:
        return AsbisEanResolution(
            "",
            AsbisEanStatus.MISSING,
            "EAN i ATTR_EAN Code su prazni.",
        )
    return AsbisEanResolution(
        "",
        AsbisEanStatus.INVALID,
        "Ni EAN ni ATTR_EAN Code ne sadrže validan EAN-13.",
    )


__all__ = [
    "AsbisEanResolution",
    "AsbisEanStatus",
    "is_valid_ean13",
    "resolve_asbis_ean",
]
