from __future__ import annotations

from decimal import Decimal

from app.core.config import settings
from app.modules.suppliers.delta_comparison import decimal_value
from app.modules.suppliers.delta_identifier_policy import normalized_name_similarity
from app.modules.suppliers.delta_models import SupplierDeltaItem
from app.modules.suppliers.gtin_normalization import normalize_to_ean13
from app.modules.suppliers.snapshot_models import SupplierSnapshotItem


def classify_ean_change(
    delta: SupplierDeltaItem,
    previous: SupplierSnapshotItem,
    current: SupplierSnapshotItem,
) -> None:
    old_source = previous.mapped_data.get("ean")
    new_source = current.mapped_data.get("ean")
    if str(old_source or "").strip() == str(new_source or "").strip():
        return
    old, new = normalize_to_ean13(old_source), normalize_to_ean13(new_source)
    if not old.value and new.value:
        classification, flags = "EAN_RECOVERED", ["EAN_RECOVERED"]
    elif old.value and new.value and old.value != new.value:
        classification, flags = "EAN_CHANGED_BLOCKED", ["EAN_CHANGE_REQUIRES_REVIEW"]
    elif old.value and not new.value:
        classification = "EAN_BECAME_INVALID"
        flags = ["EAN_CHANGE_REQUIRES_REVIEW", "CURRENT_EAN_INVALID"]
    else:
        return
    delta.change_summary = {
        **delta.change_summary,
        "identifier_classification": classification,
        "previous_ean": old.value or str(old_source or "").strip(),
        "current_ean": new.value or str(new_source or "").strip(),
        "downstream_blocked": "EAN_CHANGE_REQUIRES_REVIEW" in flags,
        "requires_manual_approval": "EAN_CHANGE_REQUIRES_REVIEW" in flags,
    }
    if "EAN_CHANGE_REQUIRES_REVIEW" in flags:
        flags.append("DOWNSTREAM_ITEM_BLOCKED")
    delta.anomaly_flags = sorted(set(delta.anomaly_flags) | set(flags))


def classify_critical_price_change(
    delta: SupplierDeltaItem,
    previous: SupplierSnapshotItem,
    current: SupplierSnapshotItem,
) -> None:
    old_price = decimal_value(previous.mapped_data.get("price"))
    new_price = decimal_value(current.mapped_data.get("price"))
    if old_price is None or new_price is None or old_price <= 0 or new_price <= 0:
        return
    ratio = new_price / old_price
    if ratio >= settings.supplier_critical_price_increase_ratio:
        classification, flag = "PRICE_INCREASE_BLOCKED", "CRITICAL_PRICE_INCREASE"
    elif ratio <= settings.supplier_critical_price_decrease_ratio:
        classification, flag = "PRICE_DECREASE_BLOCKED", "CRITICAL_PRICE_DECREASE"
    else:
        return
    delta.change_summary = {
        **delta.change_summary,
        "price_classification": classification,
        "previous_price": str(old_price),
        "current_price": str(new_price),
        "price_ratio": str(ratio),
        "price_change_percentage": str((ratio - Decimal("1")) * Decimal("100")),
        "downstream_blocked": True,
        "requires_manual_approval": True,
    }
    delta.anomaly_flags = sorted(
        set(delta.anomaly_flags) | {flag, "DOWNSTREAM_ITEM_BLOCKED"}
    )


def classify_name_change(
    delta: SupplierDeltaItem,
    previous: SupplierSnapshotItem,
    current: SupplierSnapshotItem,
) -> None:
    old_name = str(previous.mapped_data.get("name") or "").strip()
    new_name = str(current.mapped_data.get("name") or "").strip()
    if old_name == new_name:
        return
    similarity = normalized_name_similarity(old_name, new_name)
    if similarity >= settings.supplier_shared_ean_auto_accept_similarity:
        return
    requires_review = similarity < settings.supplier_shared_ean_manual_review_similarity
    flag = (
        "PRODUCT_NAME_CHANGE_REQUIRES_REVIEW"
        if requires_review
        else "PRODUCT_NAME_CHANGE_INFORMATIONAL"
    )
    delta.change_summary = {
        **delta.change_summary,
        "name_classification": (
            "PRODUCT_NAME_CHANGED_BLOCKED"
            if requires_review
            else "PRODUCT_NAME_CHANGED_INFORMATIONAL"
        ),
        "previous_name": old_name,
        "current_name": new_name,
        "name_similarity": similarity,
        "downstream_blocked": (
            requires_review or bool(delta.change_summary.get("downstream_blocked"))
        ),
        "requires_manual_approval": (
            requires_review
            or bool(delta.change_summary.get("requires_manual_approval"))
        ),
    }
    flags = {flag}
    if requires_review:
        flags.add("DOWNSTREAM_ITEM_BLOCKED")
    delta.anomaly_flags = sorted(set(delta.anomaly_flags) | flags)


def ensure_currency_unchanged(
    previous: dict[tuple[str, str], SupplierSnapshotItem],
    current: dict[tuple[str, str], SupplierSnapshotItem],
) -> None:
    for key in sorted(previous.keys() & current.keys()):
        old_currency = (
            str(previous[key].mapped_data.get("currency") or "").strip().upper()
        )
        new_currency = (
            str(current[key].mapped_data.get("currency") or "").strip().upper()
        )
        if old_currency and new_currency and old_currency != new_currency:
            raise ValueError(
                f"DELTA_CURRENCY_CHANGED:{key[1]}:{old_currency}:{new_currency}"
            )


__all__ = [
    "classify_critical_price_change",
    "classify_ean_change",
    "classify_name_change",
    "ensure_currency_unchanged",
]
