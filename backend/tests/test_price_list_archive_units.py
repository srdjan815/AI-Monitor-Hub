from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any, cast

from app.modules.suppliers.price_list_archive_service import (
    PriceListArchiveService,
    _first,
    _storage_status,
    _text,
)


def test_text_normalizes_empty_and_scalar_values() -> None:
    assert _text(None) is None
    assert _text("   ") is None
    assert _text("  artikal  ") == "artikal"
    assert _text(123) == "123"


def test_first_returns_first_non_empty_value() -> None:
    data: dict[str, object] = {"primary": " ", "secondary": " vrednost "}

    assert _first(data, "missing", "primary", "secondary") == "vrednost"
    assert _first(data, "missing", "primary") is None


def test_storage_status_is_fail_safe_for_known_and_unknown_states() -> None:
    assert _storage_status("VERIFIED") == "NAS_VERIFIED"
    assert _storage_status("FAILED") == "TRANSFER_FAILED"
    assert _storage_status("PENDING") == "TRANSFER_PENDING"
    assert _storage_status(None) == "LOCAL"
    assert _storage_status("UNKNOWN") == "LOCAL"


def test_archive_item_prefers_canonical_mapped_fields() -> None:
    mapped = {
        "product_code": "SKU-1",
        "ean": "8600000000011",
        "name": "Monitor",
        "price_rsd": "12000.00",
        "currency": "RSD",
        "stock": "5",
        "category": "Monitori",
    }
    record = cast(
        Any,
        SimpleNamespace(
            id=uuid.uuid4(),
            record_number=1,
            source_key="izvorna-sifra",
            validation_status="ACCEPTED",
            warning_count=0,
            error_count=0,
            raw_data={"Dobavljačka šifra": "SKU-1"},
            mapped_data=mapped,
        ),
    )

    item = PriceListArchiveService._item(record)

    assert item.product_code == "SKU-1"
    assert item.ean == "8600000000011"
    assert item.name == "Monitor"
    assert item.price == "12000.00"
    assert item.currency == "RSD"
    assert item.stock == "5"
    assert item.category == "Monitori"


def test_archive_item_uses_supported_fallback_fields() -> None:
    mapped = {
        "supplier_code": "ALT-1",
        "barcode": "8600000000028",
        "product_name": "Alternativni naziv",
        "net_price": "50.5",
        "source_currency": "EUR",
        "available_quantity": 3,
        "category_name": "Oprema",
    }
    record = cast(
        Any,
        SimpleNamespace(
            id=uuid.uuid4(),
            record_number=2,
            source_key="rezervna-sifra",
            validation_status="REJECTED",
            warning_count=1,
            error_count=2,
            raw_data={},
            mapped_data=mapped,
        ),
    )

    item = PriceListArchiveService._item(record)

    assert item.product_code == "ALT-1"
    assert item.ean == "8600000000028"
    assert item.name == "Alternativni naziv"
    assert item.price == "50.5"
    assert item.currency == "EUR"
    assert item.stock == "3"
    assert item.category == "Oprema"
