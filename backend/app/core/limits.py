from __future__ import annotations

import json
import math
from typing import Annotated, Any, TypeAlias, TypeVar

from pydantic import AfterValidator, Field, ValidationInfo

MAX_CONTENT_CHARS = 500_000
MAX_DESCRIPTION_CHARS = 50_000
MAX_PROMPT_CHARS = 100_000
MAX_NOTE_CHARS = 20_000
MAX_REGEX_CHARS = 2_000
MAX_SEARCH_CHARS = 500
MAX_CURSOR_CHARS = 4_096
MAX_LEGACY_OFFSET = 1_000_000
MAX_BULK_ITEMS = 500
MAX_COLLECTION_ITEMS = 500
MAX_DB_INTEGER = 2_147_483_647
MAX_JSON_BYTES = 524_288
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 20_000
MAX_JSON_KEYS = 10_000
MAX_JSON_KEY_CHARS = 1_000
MAX_JSON_ARRAY_ITEMS = 5_000
ValueT = TypeVar("ValueT")

BOUNDED_JSON_SCHEMA: dict[str, int] = {
    "x-max-json-bytes": MAX_JSON_BYTES,
    "x-max-json-depth": MAX_JSON_DEPTH,
    "x-max-json-nodes": MAX_JSON_NODES,
    "x-max-json-keys": MAX_JSON_KEYS,
    "x-max-json-key-chars": MAX_JSON_KEY_CHARS,
    "x-max-json-array-items": MAX_JSON_ARRAY_ITEMS,
}


def _is_json_scalar(value: Any, *, field_name: str) -> bool:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{field_name} contains a non-finite number")
    return value is None or isinstance(value, str | int | float | bool)


def _json_container_children(
    value: dict[Any, Any] | list[Any] | tuple[Any, ...],
    *,
    field_name: str,
) -> tuple[tuple[Any, ...], int]:
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise ValueError(f"{field_name} contains a non-string JSON key")
            if len(key) > MAX_JSON_KEY_CHARS:
                raise ValueError(
                    f"{field_name} contains a JSON key longer than "
                    f"{MAX_JSON_KEY_CHARS} characters"
                )
        return tuple(reversed(tuple(value.values()))), len(value)

    if len(value) > MAX_JSON_ARRAY_ITEMS:
        raise ValueError(
            f"{field_name} contains an array with more than "
            f"{MAX_JSON_ARRAY_ITEMS} items"
        )
    return tuple(reversed(value)), 0


def _validate_json_tree(value: Any, *, field_name: str) -> None:
    """Validate JSON shape without recursion or accepting non-finite numbers."""
    node_count = 0
    key_count = 0
    active_containers: set[int] = set()
    stack: list[tuple[bool, Any, int]] = [(True, value, 1)]

    while stack:
        entering, current, depth = stack.pop()
        if not entering:
            active_containers.remove(id(current))
            continue

        node_count += 1
        if node_count > MAX_JSON_NODES:
            raise ValueError(f"{field_name} exceeds {MAX_JSON_NODES} JSON nodes")

        if _is_json_scalar(current, field_name=field_name):
            continue

        if not isinstance(current, dict | list | tuple):
            raise ValueError(f"{field_name} contains a non-JSON value")
        if depth > MAX_JSON_DEPTH:
            raise ValueError(
                f"{field_name} exceeds JSON nesting depth {MAX_JSON_DEPTH}"
            )

        identity = id(current)
        if identity in active_containers:
            raise ValueError(f"{field_name} contains a cyclic JSON structure")
        active_containers.add(identity)
        stack.append((False, current, depth))

        children, new_keys = _json_container_children(
            current,
            field_name=field_name,
        )
        key_count += new_keys
        if key_count > MAX_JSON_KEYS:
            raise ValueError(f"{field_name} exceeds {MAX_JSON_KEYS} JSON keys")
        for item in children:
            stack.append((True, item, depth + 1))


def validate_json_size(value: ValueT, *, field_name: str) -> ValueT:
    """Validate a bounded, finite, acyclic JSON-compatible value."""
    _validate_json_tree(value, field_name=field_name)
    try:
        size = len(
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
        )
    except (OverflowError, RecursionError, TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} is not a valid bounded JSON structure") from exc
    if size > MAX_JSON_BYTES:
        raise ValueError(f"{field_name} exceeds {MAX_JSON_BYTES} encoded bytes")
    return value


def _bounded_json_after(value: Any, info: ValidationInfo) -> Any:
    return validate_json_size(
        value,
        field_name=info.field_name or "JSON value",
    )


BoundedJsonValue: TypeAlias = Annotated[
    Any,
    Field(json_schema_extra=BOUNDED_JSON_SCHEMA),
    AfterValidator(_bounded_json_after),
]
BoundedJsonObject: TypeAlias = Annotated[
    dict[str, Any],
    Field(json_schema_extra=BOUNDED_JSON_SCHEMA),
    AfterValidator(_bounded_json_after),
]
BoundedJsonArray: TypeAlias = Annotated[
    list[Any],
    Field(json_schema_extra=BOUNDED_JSON_SCHEMA),
    AfterValidator(_bounded_json_after),
]
