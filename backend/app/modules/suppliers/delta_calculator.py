from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal

from app.core.config import settings
from app.modules.suppliers.delta_change_policy import (
    classify_critical_price_change,
    classify_ean_change,
    classify_name_change,
    ensure_currency_unchanged,
)
from app.modules.suppliers.delta_comparison import (
    ValueChange,
    compare_values,
    decimal_value,
    field_role,
    identity_index,
    preview,
    value_hash,
    value_type,
)
from app.modules.suppliers.delta_identifier_policy import shared_ean_findings
from app.modules.suppliers.delta_models import (
    SupplierDeltaFieldChange,
    SupplierDeltaItem,
)
from app.modules.suppliers.snapshot_models import SupplierSnapshotItem


def product_codes(records: Sequence[object]) -> set[str]:
    return {
        code.casefold()
        for record in records
        if (
            code := str(
                getattr(record, "mapped_data", {}).get("product_code") or ""
            ).strip()
        )
    }


def calculate_delta(
    run_id: uuid.UUID,
    previous: list[SupplierSnapshotItem],
    current: list[SupplierSnapshotItem],
    *,
    previous_rejected_codes: set[str] | None = None,
    current_rejected_codes: set[str] | None = None,
) -> tuple[list[SupplierDeltaItem], list[SupplierDeltaFieldChange], dict[str, int]]:
    old = identity_index(list(previous))
    new = identity_index(list(current))
    ensure_currency_unchanged(old, new)
    previous_rejected_codes = previous_rejected_codes or set()
    current_rejected_codes = current_rejected_codes or set()
    delta_items: list[SupplierDeltaItem] = []
    fields: list[SupplierDeltaFieldChange] = []
    stats = {
        name: 0
        for name in (
            "added_items",
            "removed_items",
            "modified_items",
            "unchanged_items",
            "price_increased_items",
            "price_decreased_items",
            "price_unchanged_items",
            "stock_increased_items",
            "stock_decreased_items",
            "became_available_items",
            "became_unavailable_items",
            "image_changed_items",
            "identifier_changed_items",
        )
    }
    for key in sorted(new.keys() - old.keys()):
        current_item = new[key]
        classification = "RECOVERED" if key[1] in previous_rejected_codes else "ADDED"
        delta_items.append(delta_item(run_id, classification, key, None, current_item))
        stats["added_items"] += 1
    for key in sorted(old.keys() - new.keys()):
        previous_item = old[key]
        if key[1] in current_rejected_codes:
            delta_items.append(
                delta_item(
                    run_id,
                    "BLOCKED",
                    key,
                    previous_item,
                    None,
                    classification="PRESENT_BUT_REJECTED",
                    anomaly_flags=["CURRENT_RECORD_INVALID"],
                )
            )
        else:
            delta_items.append(
                delta_item(
                    run_id,
                    "REMOVED",
                    key,
                    previous_item,
                    None,
                    classification="REMOVED_BLOCKED",
                    anomaly_flags=["REMOVAL_REQUIRES_REVIEW"],
                )
            )
        stats["removed_items"] += 1
    for key in sorted(old.keys() & new.keys()):
        prior, latest = old[key], new[key]
        if prior.item_fingerprint == latest.item_fingerprint:
            stats["unchanged_items"] += 1
            continue
        changes = compare_values(prior.mapped_data, latest.mapped_data)
        images_changed = prior.source_image_links != latest.source_image_links
        if images_changed:
            changes.append(
                ValueChange(
                    "source_image_links",
                    "ARRAY_CHANGED",
                    prior.source_image_links,
                    latest.source_image_links,
                )
            )
        if len(changes) > settings.delta_max_changed_fields_per_item:
            raise ValueError("DELTA_FIELD_LIMIT_EXCEEDED")
        delta = delta_item(run_id, "MODIFIED", key, prior, latest)
        price_direction = stock_direction = 0
        for change in changes:
            role = field_role(change.path)
            field = delta_field(delta.id, change, role)
            fields.append(field)
            if (
                role == "PRICE"
                and field.previous_numeric_value is not None
                and field.current_numeric_value is not None
            ):
                price_direction = (
                    field.current_numeric_value > field.previous_numeric_value
                ) - (field.current_numeric_value < field.previous_numeric_value)
            if (
                role == "STOCK"
                and field.previous_numeric_value is not None
                and field.current_numeric_value is not None
            ):
                stock_direction = (
                    field.current_numeric_value > field.previous_numeric_value
                ) - (field.current_numeric_value < field.previous_numeric_value)
                stats["became_available_items"] += (
                    field.previous_numeric_value <= 0 < field.current_numeric_value
                )
                stats["became_unavailable_items"] += (
                    field.previous_numeric_value > 0 >= field.current_numeric_value
                )
        delta.changed_field_count = len(changes)
        delta.has_price_change = price_direction != 0
        delta.has_stock_change = stock_direction != 0
        delta.has_image_change = images_changed
        delta.has_identifier_change = any(
            field_role(change.path) == "IDENTIFIER" for change in changes
        )
        classify_ean_change(delta, prior, latest)
        classify_name_change(delta, prior, latest)
        classify_critical_price_change(delta, prior, latest)
        stats["price_increased_items"] += price_direction > 0
        stats["price_decreased_items"] += price_direction < 0
        stats["stock_increased_items"] += stock_direction > 0
        stats["stock_decreased_items"] += stock_direction < 0
        stats["image_changed_items"] += images_changed
        stats["identifier_changed_items"] += delta.has_identifier_change
        stats["modified_items"] += 1
        delta_items.append(delta)
    add_shared_ean_reviews(run_id, current, delta_items)
    reconcile(len(previous), len(current), stats)
    return delta_items, fields, stats


def add_shared_ean_reviews(
    run_id: uuid.UUID,
    current: list[SupplierSnapshotItem],
    items: list[SupplierDeltaItem],
) -> None:
    for finding in shared_ean_findings(list(current)):
        key = (
            "SHARED_EAN",
            f"{finding.ean}:{finding.first_code.casefold()}:{finding.second_code.casefold()}",
        )
        items.append(
            delta_item(
                run_id,
                "REVIEW",
                key,
                None,
                None,
                classification="SHARED_EAN_NAME_REVIEW",
                anomaly_flags=[
                    "SHARED_EAN_LOW_NAME_SIMILARITY"
                    if finding.review_level == "MANUAL_REVIEW"
                    else "SHARED_EAN_INFORMATIONAL"
                ],
                summary={
                    "ean": finding.ean,
                    "first_product_code": finding.first_code,
                    "second_product_code": finding.second_code,
                    "name_similarity": finding.name_similarity,
                    "review_level": finding.review_level,
                    "downstream_blocked": False,
                },
            )
        )


def delta_item(
    run_id: uuid.UUID,
    change_type: str,
    key: tuple[str, str],
    previous: SupplierSnapshotItem | None,
    current: SupplierSnapshotItem | None,
    *,
    classification: str | None = None,
    anomaly_flags: list[str] | None = None,
    summary: dict[str, object] | None = None,
) -> SupplierDeltaItem:
    flags = set(anomaly_flags or [])
    provided_summary = summary or {}
    automatically_blocked = bool(
        flags
        & {
            "CURRENT_RECORD_INVALID",
            "REMOVAL_REQUIRES_REVIEW",
            "DOWNSTREAM_ITEM_BLOCKED",
        }
    )
    if automatically_blocked:
        flags.add("DOWNSTREAM_ITEM_BLOCKED")
    return SupplierDeltaItem(
        id=uuid.uuid4(),
        delta_run_id=run_id,
        change_type=change_type,
        matching_key_type=key[0],
        matching_key_value=key[1],
        previous_snapshot_item_id=previous.id if previous else None,
        current_snapshot_item_id=current.id if current else None,
        previous_item_fingerprint=previous.item_fingerprint if previous else None,
        current_item_fingerprint=current.item_fingerprint if current else None,
        change_summary={
            "classification": classification or change_type,
            "downstream_blocked": automatically_blocked,
            "requires_manual_approval": automatically_blocked,
            **provided_summary,
        },
        anomaly_flags=sorted(flags),
    )


def delta_field(
    item_id: uuid.UUID, change: object, role: str | None
) -> SupplierDeltaFieldChange:
    previous, current = getattr(change, "previous"), getattr(change, "current")
    old_num, new_num = decimal_value(previous), decimal_value(current)
    absolute = (
        new_num - old_num if old_num is not None and new_num is not None else None
    )
    percentage = (
        absolute / old_num * Decimal(100) if absolute is not None and old_num else None
    )
    return SupplierDeltaFieldChange(
        delta_item_id=item_id,
        field_path=getattr(change, "path") or "$",
        field_role=role,
        change_type=getattr(change, "change_type"),
        previous_value_type=value_type(previous),
        current_value_type=value_type(current),
        previous_value_hash=value_hash(previous),
        current_value_hash=value_hash(current),
        previous_value_preview=preview(previous),
        current_value_preview=preview(current),
        previous_numeric_value=old_num,
        current_numeric_value=new_num,
        absolute_numeric_change=absolute,
        percentage_numeric_change=percentage,
    )


def reconcile(previous: int, current: int, stats: dict[str, int]) -> None:
    matched = stats["modified_items"] + stats["unchanged_items"]
    if (
        previous != stats["removed_items"] + matched
        or current != stats["added_items"] + matched
    ):
        raise ValueError("DELTA_COUNT_INVARIANT")


__all__ = [
    "calculate_delta",
    "classify_critical_price_change",
    "classify_ean_change",
    "classify_name_change",
    "delta_field",
    "delta_item",
    "ensure_currency_unchanged",
    "product_codes",
    "reconcile",
]
