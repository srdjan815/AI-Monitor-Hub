from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from types import SimpleNamespace
import uuid

import pytest

from app.modules.suppliers.delta_anomalies import anomaly_signals
from app.modules.suppliers.delta_comparison import (
    MISSING,
    compare_values,
    decimal_value,
    identity_index,
    preview,
    value_hash,
)
from app.modules.suppliers.delta_service import SupplierDeltaService
from app.modules.suppliers.delta_identifier_policy import shared_ean_findings


@dataclass
class Item:
    source_key: str | None
    source_identifier: str | None
    mapped_data: dict[str, object] = field(default_factory=dict)


def test_identity_priority_order_independence_and_duplicates() -> None:
    first = Item("SKU-1", "ALT")
    second = Item(None, "SKU-2")
    assert list(identity_index([second, first])) == [
        ("SOURCE_IDENTIFIER", "SKU-2"),
        ("SOURCE_KEY", "SKU-1"),
    ]
    with pytest.raises(ValueError, match="DELTA_DUPLICATE_IDENTITY"):
        identity_index([first, Item("SKU-1", None)])


def test_product_code_is_primary_identity_and_duplicate_ean_is_allowed() -> None:
    first = Item(
        "same-ean", "same-ean", {"product_code": "ABC", "ean": "8606019540128"}
    )
    second = Item(
        "same-ean", "same-ean", {"product_code": "DEF", "ean": "8606019540128"}
    )
    assert list(identity_index([first, second])) == [
        ("PRODUCT_CODE", "abc"),
        ("PRODUCT_CODE", "def"),
    ]


def _snapshot_item(code: str, ean: str, fingerprint: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        source_key=ean,
        source_identifier=ean,
        mapped_data={"product_code": code, "ean": ean, "name": code},
        source_image_links=[],
        item_fingerprint=fingerprint,
    )


def test_removed_rejected_recovered_and_ean_change_are_safely_classified() -> None:
    service = SupplierDeltaService(None)  # type: ignore[arg-type]
    old_removed = _snapshot_item("REMOVED", "8606019540128", "old-removed")
    old_rejected = _snapshot_item("REJECTED", "4006381333931", "old-rejected")
    old_changed = _snapshot_item("CHANGED", "5901234123457", "old-changed")
    recovered = _snapshot_item("RECOVERED", "0198156628701", "recovered")
    changed = _snapshot_item("CHANGED", "9780201379624", "new-changed")

    items, _, stats = service._compare(
        uuid.uuid4(),
        [old_removed, old_rejected, old_changed],
        [recovered, changed],
        previous_rejected_codes={"recovered"},
        current_rejected_codes={"rejected"},
    )
    by_code = {item.matching_key_value: item for item in items}

    assert by_code["removed"].change_summary["classification"] == "REMOVED_BLOCKED"
    assert by_code["removed"].change_summary["downstream_blocked"] is True
    assert by_code["removed"].change_summary["requires_manual_approval"] is True
    assert by_code["removed"].anomaly_flags == [
        "DOWNSTREAM_ITEM_BLOCKED",
        "REMOVAL_REQUIRES_REVIEW",
    ]
    assert by_code["rejected"].change_type == "BLOCKED"
    assert (
        by_code["rejected"].change_summary["classification"] == "PRESENT_BUT_REJECTED"
    )
    assert by_code["recovered"].change_type == "RECOVERED"
    assert (
        by_code["changed"].change_summary["identifier_classification"]
        == "EAN_CHANGED_BLOCKED"
    )
    assert by_code["changed"].change_summary["downstream_blocked"] is True
    assert by_code["changed"].change_summary["requires_manual_approval"] is True
    assert "EAN_CHANGE_REQUIRES_REVIEW" in by_code["changed"].anomaly_flags
    assert "DOWNSTREAM_ITEM_BLOCKED" in by_code["changed"].anomaly_flags
    assert stats["added_items"] == 1
    assert stats["removed_items"] == 2


def test_shared_ean_is_allowed_but_unrelated_names_are_marked_for_review() -> None:
    similar = [
        _snapshot_item("KB-RS", "8606019540128", "a"),
        _snapshot_item("KB-US", "8606019540128", "b"),
    ]
    similar[0].mapped_data["name"] = "Logitech MX Keys tastatura RS crna"
    similar[1].mapped_data["name"] = "Logitech MX Keys tastatura US crna"
    unrelated = _snapshot_item("MONITOR", "8606019540128", "c")
    unrelated.mapped_data["name"] = "Samsung 55 inch televizor"

    findings = shared_ean_findings([*similar, unrelated])

    assert all(finding.first_code != finding.second_code for finding in findings)
    assert any(finding.review_level == "MANUAL_REVIEW" for finding in findings)
    assert not any(
        {finding.first_code, finding.second_code} == {"KB-RS", "KB-US"}
        for finding in findings
    )


@pytest.mark.parametrize(
    ("previous_price", "current_price", "classification", "critical_flag"),
    [
        ("100.00", "300.00", "PRICE_INCREASE_BLOCKED", "CRITICAL_PRICE_INCREASE"),
        ("100.00", "50.00", "PRICE_DECREASE_BLOCKED", "CRITICAL_PRICE_DECREASE"),
    ],
)
def test_critical_price_change_blocks_only_affected_supplier_item(
    previous_price: str,
    current_price: str,
    classification: str,
    critical_flag: str,
) -> None:
    service = SupplierDeltaService(None)  # type: ignore[arg-type]
    previous = _snapshot_item("PRICE-1", "8606019540128", "old")
    current = _snapshot_item("PRICE-1", "8606019540128", "new")
    previous.mapped_data["price"] = previous_price
    current.mapped_data["price"] = current_price

    items, _, stats = service._compare(uuid.uuid4(), [previous], [current])

    assert stats["modified_items"] == 1
    assert len(items) == 1
    change = items[0]
    assert change.change_summary["price_classification"] == classification
    assert change.change_summary["downstream_blocked"] is True
    assert change.change_summary["requires_manual_approval"] is True
    assert critical_flag in change.anomaly_flags
    assert "DOWNSTREAM_ITEM_BLOCKED" in change.anomaly_flags


@pytest.mark.parametrize(
    ("previous_price", "current_price"),
    [("100.00", "299.99"), ("100.00", "50.01"), ("100.00", "120.00")],
)
def test_noncritical_price_change_is_not_blocked(
    previous_price: str, current_price: str
) -> None:
    service = SupplierDeltaService(None)  # type: ignore[arg-type]
    previous = _snapshot_item("PRICE-1", "8606019540128", "old")
    current = _snapshot_item("PRICE-1", "8606019540128", "new")
    previous.mapped_data["price"] = previous_price
    current.mapped_data["price"] = current_price

    items, _, _ = service._compare(uuid.uuid4(), [previous], [current])

    assert items[0].change_summary.get("downstream_blocked") is not True
    assert "DOWNSTREAM_ITEM_BLOCKED" not in items[0].anomaly_flags


def test_critical_price_thresholds_are_runtime_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(
        settings, "supplier_critical_price_increase_ratio", Decimal("2")
    )
    monkeypatch.setattr(
        settings, "supplier_critical_price_decrease_ratio", Decimal("0.75")
    )
    service = SupplierDeltaService(None)  # type: ignore[arg-type]
    previous = _snapshot_item("PRICE-1", "8606019540128", "old")
    current = _snapshot_item("PRICE-1", "8606019540128", "new")
    previous.mapped_data["price"] = "100.00"
    current.mapped_data["price"] = "200.00"

    items, _, _ = service._compare(uuid.uuid4(), [previous], [current])

    assert items[0].change_summary["price_classification"] == "PRICE_INCREASE_BLOCKED"


def test_currency_change_blocks_complete_delta_calculation() -> None:
    service = SupplierDeltaService(None)  # type: ignore[arg-type]
    previous = _snapshot_item("PRICE-1", "8606019540128", "old")
    current = _snapshot_item("PRICE-1", "8606019540128", "new")
    previous.mapped_data.update({"price": "100.00", "currency": "RSD"})
    current.mapped_data.update({"price": "100.00", "currency": "EUR"})

    with pytest.raises(ValueError, match="DELTA_CURRENCY_CHANGED"):
        service._compare(uuid.uuid4(), [previous], [current])


def test_unrelated_name_change_for_same_product_code_is_blocked() -> None:
    service = SupplierDeltaService(None)  # type: ignore[arg-type]
    previous = _snapshot_item("SAME-CODE", "8606019540128", "old")
    current = _snapshot_item("SAME-CODE", "8606019540128", "new")
    previous.mapped_data["name"] = "Lenovo ThinkPad E16 laptop"
    current.mapped_data["name"] = "Samsung frižider sa zamrzivačem"

    items, _, _ = service._compare(uuid.uuid4(), [previous], [current])

    change = items[0]
    assert (
        change.change_summary["name_classification"] == "PRODUCT_NAME_CHANGED_BLOCKED"
    )
    assert change.change_summary["downstream_blocked"] is True
    assert "PRODUCT_NAME_CHANGE_REQUIRES_REVIEW" in change.anomaly_flags
    assert "DOWNSTREAM_ITEM_BLOCKED" in change.anomaly_flags


def test_currency_comparison_is_case_and_whitespace_insensitive() -> None:
    service = SupplierDeltaService(None)  # type: ignore[arg-type]
    previous = _snapshot_item("PRICE-1", "8606019540128", "old")
    current = _snapshot_item("PRICE-1", "8606019540128", "new")
    previous.mapped_data.update({"price": "100.00", "currency": " rsd "})
    current.mapped_data.update({"price": "101.00", "currency": "RSD"})

    items, _, _ = service._compare(uuid.uuid4(), [previous], [current])

    assert len(items) == 1


def test_canonical_field_comparison_contract() -> None:
    assert compare_values({"b": 2, "a": 1}, {"a": 1, "b": 2}) == []
    changes = compare_values(
        {"null": None, "array": [1, 2], "price": "50.00", "html": "<b>Ž</b>\n"},
        {"array": [2, 1], "price": "55.00", "html": "<b>Ž</b>\nnovo", "added": 1},
    )
    assert {change.change_type for change in changes} == {
        "VALUE_REMOVED",
        "ARRAY_CHANGED",
        "VALUE_CHANGED",
        "VALUE_ADDED",
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
        previous_total=100,
        current_total=100,
        added=60,
        removed=60,
        modified=90,
        schema_changed=True,
        mapping_changed=True,
    )
    assert [signal["code"] for signal in signals] == [
        "SCHEMA_VERSION_CHANGED",
        "MAPPING_VERSION_CHANGED",
        "HIGH_REMOVAL_RATIO",
        "HIGH_ADDITION_RATIO",
        "UNUSUAL_FIELD_CHANGE_VOLUME",
    ]
