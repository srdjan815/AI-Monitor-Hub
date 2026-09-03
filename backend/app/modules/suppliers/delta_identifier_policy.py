from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import combinations
from typing import Protocol

from app.core.config import settings


class IdentifierItem(Protocol):
    mapped_data: dict[str, object]


@dataclass(frozen=True, slots=True)
class SharedEanFinding:
    ean: str
    first_code: str
    second_code: str
    name_similarity: float
    review_level: str


def normalized_name_similarity(first: object, second: object) -> float:
    left = _normalized_text(first)
    right = _normalized_text(second)
    if not left or not right:
        return 0.0
    return round(SequenceMatcher(None, left, right, autojunk=False).ratio(), 4)


def shared_ean_findings(
    items: list[IdentifierItem],
    *,
    auto_accept_similarity: float | None = None,
    manual_review_similarity: float | None = None,
) -> list[SharedEanFinding]:
    auto_accept = (
        settings.supplier_shared_ean_auto_accept_similarity
        if auto_accept_similarity is None
        else auto_accept_similarity
    )
    manual_review = (
        settings.supplier_shared_ean_manual_review_similarity
        if manual_review_similarity is None
        else manual_review_similarity
    )
    groups: dict[str, list[IdentifierItem]] = {}
    for item in items:
        ean = str(item.mapped_data.get("ean") or "").strip()
        code = str(item.mapped_data.get("product_code") or "").strip()
        if ean and code:
            groups.setdefault(ean, []).append(item)
    findings: list[SharedEanFinding] = []
    for ean, group in sorted(groups.items()):
        for first, second in combinations(group, 2):
            first_code = str(first.mapped_data.get("product_code") or "").strip()
            second_code = str(second.mapped_data.get("product_code") or "").strip()
            if first_code.casefold() == second_code.casefold():
                continue
            similarity = normalized_name_similarity(
                first.mapped_data.get("name"), second.mapped_data.get("name")
            )
            if similarity >= auto_accept:
                continue
            findings.append(
                SharedEanFinding(
                    ean=ean,
                    first_code=first_code,
                    second_code=second_code,
                    name_similarity=similarity,
                    review_level=(
                        "MANUAL_REVIEW"
                        if similarity < manual_review
                        else "INFORMATIONAL"
                    ),
                )
            )
    return findings


def _normalized_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = text.encode("ascii", "ignore").decode().casefold()
    return " ".join(re.findall(r"[a-z0-9]+", ascii_text))


__all__ = [
    "SharedEanFinding",
    "normalized_name_similarity",
    "shared_ean_findings",
]
