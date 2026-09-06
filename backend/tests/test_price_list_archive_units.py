from __future__ import annotations

import hashlib
import uuid
from types import SimpleNamespace
from typing import Any, cast

from app.core.config import settings
from app.modules.suppliers.price_list_archive_download import (
    _archive_path,
    _download_name,
    _local_path,
    _verified,
)
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


def test_archive_item_handles_sparse_legacy_record() -> None:
    record = cast(
        Any,
        SimpleNamespace(
            id=uuid.uuid4(),
            record_number=3,
            source_key="LEGACY-1",
            validation_status="ACCEPTED",
            warning_count=0,
            error_count=0,
            raw_data={"legacy": True},
            mapped_data={},
        ),
    )

    item = PriceListArchiveService._item(record)

    assert item.product_code == "LEGACY-1"
    assert item.ean is None
    assert item.name is None
    assert item.price is None
    assert item.currency is None
    assert item.stock is None
    assert item.category is None


def test_download_name_preserves_safe_original_and_falls_back() -> None:
    assert _download_name(" cenovnik.xlsx ", "ACQ-1", "XLSX") == "cenovnik.xlsx"
    assert _download_name("../tajna.txt", "ACQ-2", "CSV") == "ACQ-2.csv"
    assert _download_name(None, "ACQ-3", None) == "ACQ-3"


def test_download_verification_requires_exact_size_and_checksum(tmp_path: Any) -> None:
    payload = b"originalni cenovnik"
    source = tmp_path / "cenovnik.csv"
    source.write_bytes(payload)
    checksum = hashlib.sha256(payload).hexdigest()

    assert _verified(source, checksum, len(payload)) is True
    assert _verified(source, checksum, None) is True
    assert _verified(source, checksum, len(payload) + 1) is False
    assert _verified(source, "0" * 64, len(payload)) is False
    assert _verified(tmp_path / "ne-postoji.csv", checksum, len(payload)) is False


def test_local_download_path_is_confined_to_artifact_root(tmp_path: Any) -> None:
    root = str(tmp_path)
    assert _local_path("cenovnik.csv", root) == (tmp_path / "cenovnik.csv").resolve()
    assert _local_path(None, root) is None
    assert _local_path("../tajna.txt", root) is None


def test_archive_download_path_is_confined_to_configured_mount(
    tmp_path: Any, monkeypatch: Any
) -> None:
    monkeypatch.setattr(settings, "system_archive_mount_root", str(tmp_path))

    expected = (tmp_path / "cenovnici" / "blobs" / "cenovnik.csv").resolve()
    assert _archive_path("cenovnici", "blobs/cenovnik.csv") == expected
    assert _archive_path("cenovnici", None) is None
    assert _archive_path("cenovnici", "/tajna.txt") is None
    assert _archive_path("cenovnici", "../tajna.txt") is None
