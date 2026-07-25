from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Protocol, TypeVar, cast
from app.modules.suppliers.snapshot_fingerprints import canonical_json

MISSING = object()
PREVIEW_LIMIT = 240


class IdentityItem(Protocol):
    source_key: str | None
    source_identifier: str | None


TIdentity = TypeVar("TIdentity", bound=IdentityItem)


@dataclass(frozen=True, slots=True)
class ValueChange:
    path: str
    change_type: str
    previous: object
    current: object


def matching_identity(item: IdentityItem) -> tuple[str, str]:
    source_key = item.source_key
    if isinstance(source_key, str) and source_key:
        return "SOURCE_KEY", source_key
    source_identifier = item.source_identifier
    if isinstance(source_identifier, str) and source_identifier:
        return "SOURCE_IDENTIFIER", source_identifier
    raise ValueError("DELTA_IDENTITY_MISSING")


def identity_index(items: list[TIdentity]) -> dict[tuple[str, str], TIdentity]:
    result: dict[tuple[str, str], TIdentity] = {}
    for item in items:
        key = matching_identity(item)
        if key in result:
            raise ValueError(f"DELTA_DUPLICATE_IDENTITY:{key[0]}:{key[1]}")
        result[key] = item
    return result


def compare_values(previous: object, current: object, path: str = "") -> list[ValueChange]:
    if previous is MISSING or current is MISSING:
        return [ValueChange(path, "VALUE_ADDED" if previous is MISSING else "VALUE_REMOVED", previous, current)]
    if type(previous) is not type(current):
        return [ValueChange(path, "TYPE_CHANGED", previous, current)]
    if isinstance(previous, dict):
        current_dict = cast(dict[object, object], current)
        changes: list[ValueChange] = []
        for key in sorted(set(previous) | set(current_dict), key=str):
            child = f"{path}.{key}" if path else str(key)
            changes.extend(compare_values(previous.get(key, MISSING), current_dict.get(key, MISSING), child))
        return changes
    if isinstance(previous, list):
        return [] if previous == current else [ValueChange(path, "ARRAY_CHANGED", previous, current)]
    return [] if previous == current else [ValueChange(path, "VALUE_CHANGED", previous, current)]


def value_hash(value: object) -> str | None:
    if value is MISSING:
        return None
    return hashlib.sha256(canonical_json(value)).hexdigest()


def value_type(value: object) -> str | None:
    if value is MISSING:
        return None
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float, Decimal)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def preview(value: object) -> str | None:
    if value is MISSING:
        return None
    rendered = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return rendered[:PREVIEW_LIMIT]


def decimal_value(value: object) -> Decimal | None:
    if isinstance(value, bool) or value is MISSING or value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def field_role(path: str) -> str | None:
    leaf = path.rsplit(".", 1)[-1].lower()
    if leaf in {"price", "purchase_price", "supplier_price"}:
        return "PRICE"
    if leaf in {"stock", "quantity", "quantity_on_hand", "availability"}:
        return "STOCK"
    if leaf in {"sku", "ean", "manufacturer_code", "source_identifier"}:
        return "IDENTIFIER"
    return None


__all__ = [
    "MISSING", "ValueChange", "compare_values", "decimal_value", "field_role",
    "identity_index", "matching_identity", "preview", "value_hash", "value_type",
]
