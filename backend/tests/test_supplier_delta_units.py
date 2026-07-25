from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from app.modules.suppliers.delta_anomalies import anomaly_signals
from app.modules.suppliers.delta_comparison import (
    MISSING, compare_values, decimal_value, identity_index, preview, value_hash,
)


@dataclass
class Item:
    source_key: str | None
    source_identifier: str | None


def test_identity_priority_order_independence_and_duplicates() -> None:
    first = Item("SKU-1", "ALT")
    second = Item(None, "SKU-2")
    assert list(identity_index([second, first])) == [
        ("SOURCE_IDENTIFIER", "SKU-2"),
        ("SOURCE_KEY", "SKU-1"),
    ]
    with pytest.raises(ValueError, match="DELTA_DUPLICATE_IDENTITY"):
        identity_index([first, Item("SKU-1", None)])


def test_canonical_field_comparison_contract() -> None:
    assert compare_values({"b": 2, "a": 1}, {"a": 1, "b": 2}) == []
    changes = compare_values(
        {"null": None, "array": [1, 2], "price": "50.00", "html": "<b>Ž</b>\n"},
        {"array": [2, 1], "price": "55.00", "html": "<b>Ž</b>\nnovo", "added": 1},
    )
    assert {change.change_type for change in changes} == {
        "VALUE_REMOVED", "ARRAY_CHANGED", "VALUE_CHANGED", "VALUE_ADDED",
    }
    assert compare_values(None, MISSING)[0].change_type == "VALUE_REMOVED"
    assert decimal_value("55.00") == Decimal("55.00")
    assert decimal_value(True) is None


def test_large_text_uses_hash_and_bounded_preview() -> None:
    previous = ("Dugačak Unicode <p>opis</p>\n" * 2000) + "A"
    current = previous[:-1] + "B"
    assert value_hash(previous) != value_hash(current)
    assert len(preview(previous) or "") <= 240
    assert previous not in (preview(previous) or "")


def test_anomaly_signals_are_deterministic_facts() -> None:
    signals = anomaly_signals(
        previous_total=100, current_total=100, added=60, removed=60,
        modified=90, schema_changed=True, mapping_changed=True,
    )
    assert [signal["code"] for signal in signals] == [
        "SCHEMA_VERSION_CHANGED", "MAPPING_VERSION_CHANGED",
        "HIGH_REMOVAL_RATIO", "HIGH_ADDITION_RATIO",
        "UNUSUAL_FIELD_CHANGE_VOLUME",
    ]
