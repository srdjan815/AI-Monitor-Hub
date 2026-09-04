from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.modules.suppliers.currency_conversion import (
    convert_supplier_price,
    rate_for_pricing,
)
from app.modules.suppliers.currency_contracts import SnapshotCurrencyPlan
from app.modules.suppliers.currency_schemas import CurrencySettingWrite


def test_monitor_rsd_setting_requires_fixed_rate() -> None:
    with pytest.raises(ValidationError):
        CurrencySettingWrite(currency_code="rsd", rate_mode="MANUAL")


def test_automatic_rate_requires_https_source() -> None:
    with pytest.raises(ValidationError):
        CurrencySettingWrite(
            currency_code="EUR",
            rate_mode="AUTOMATIC",
            automatic_source_url="http://supplier.example/rate",
        )


def test_snapshot_conversion_preserves_source_and_uses_decimal_half_up() -> None:
    rate_id = uuid.uuid4()
    plan = SnapshotCurrencyPlan(
        setting=SimpleNamespace(id=uuid.uuid4()),
        rate=SimpleNamespace(id=rate_id, rate_to_rsd=Decimal("117.36000000")),
        currency_code="EUR",
    )
    original = {"product_code": "A-1", "price": "10.125", "currency": "EUR"}

    converted = convert_supplier_price(original, plan)

    assert converted == {
        **original,
        "source_price": "10.125",
        "source_currency": "EUR",
        "exchange_rate": "117.36",
        "exchange_rate_id": str(rate_id),
        "price_rsd": "1188.27",
    }
    assert original == {"product_code": "A-1", "price": "10.125", "currency": "EUR"}


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("118.70499999", "118.70"),
        ("118.70500000", "118.71"),
        ("118.79500000", "118.80"),
    ],
)
def test_rate_for_pricing_uses_financial_half_up_rounding(
    source: str, expected: str
) -> None:
    assert rate_for_pricing(Decimal(source)) == Decimal(expected)


def test_rate_payload_rejects_non_iso_currency() -> None:
    with pytest.raises(ValidationError):
        CurrencySettingWrite(currency_code="EVR", rate_mode="MANUAL")


def test_currency_code_is_normalized() -> None:
    value = CurrencySettingWrite(currency_code=" eur ", rate_mode="MANUAL")
    assert value.currency_code == "EUR"
