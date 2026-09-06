from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
import uuid

from app.modules.suppliers.price_observation_repository import observation_values


def _snapshot() -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid.uuid4(),
        supplier_id=uuid.uuid4(),
        source_connection_id=uuid.uuid4(),
        source_currency="EUR",
        exchange_rate_to_rsd=Decimal("118.70"),
        finalized_at=now,
        created_at=now,
    )


def test_observation_preserves_normalized_price_dimensions() -> None:
    snapshot = _snapshot()
    item = SimpleNamespace(
        id=uuid.uuid4(),
        source_identifier="EPI-1",
        item_fingerprint="f" * 64,
        mapped_data={
            "product_code": " EPI-1 ",
            "ean": "8600000000001",
            "name": "Monitor",
            "category": "MONITORI",
            "source_price": "100.00",
            "source_currency": "eur",
            "exchange_rate": "118.70",
            "price_rsd": "11870.00",
            "stock": "4",
        },
    )

    value = observation_values(snapshot, item)

    assert value is not None
    assert value["product_code"] == "EPI-1"
    assert value["product_code_normalized"] == "epi-1"
    assert value["identity_key"] == "ean:8600000000001"
    assert value["source_currency"] == "EUR"
    assert value["source_price"] == Decimal("100.00")
    assert value["price_rsd"] == Decimal("11870.00")
    assert value["stock"] == Decimal("4")


def test_observation_rejects_missing_identity_or_invalid_price() -> None:
    snapshot = _snapshot()
    base = {
        "id": uuid.uuid4(),
        "item_fingerprint": "f" * 64,
    }
    missing_identity = SimpleNamespace(
        **base, source_identifier=None, mapped_data={"price": "10"}
    )
    invalid_price = SimpleNamespace(
        **base,
        source_identifier="A",
        mapped_data={"product_code": "A", "price": "nije-cena"},
    )

    assert observation_values(snapshot, missing_identity) is None
    assert observation_values(snapshot, invalid_price) is None


def test_observation_does_not_persist_negative_stock() -> None:
    snapshot = _snapshot()
    item = SimpleNamespace(
        id=uuid.uuid4(),
        source_identifier="A",
        item_fingerprint="f" * 64,
        mapped_data={"product_code": "A", "price": "10", "stock": "-1"},
    )

    value = observation_values(snapshot, item)

    assert value is not None
    assert value["stock"] is None


def test_observation_falls_back_to_rsd_for_invalid_currency() -> None:
    snapshot = _snapshot()
    item = SimpleNamespace(
        id=uuid.uuid4(),
        source_identifier="A",
        item_fingerprint="f" * 64,
        mapped_data={
            "product_code": "A",
            "price": "10",
            "source_currency": "nepoznato",
        },
    )

    value = observation_values(snapshot, item)

    assert value is not None
    assert value["source_currency"] == "RSD"
