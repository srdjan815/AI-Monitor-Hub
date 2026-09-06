from __future__ import annotations

from app.modules.suppliers.price_list_archive_service import (
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
