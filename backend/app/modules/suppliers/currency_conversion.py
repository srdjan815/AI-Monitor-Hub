from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from app.modules.suppliers.currency_contracts import SnapshotCurrencyPlan
from app.modules.suppliers.errors import supplier_error


def convert_supplier_price(
    mapped: dict[str, object], plan: SnapshotCurrencyPlan | None
) -> dict[str, object]:
    if plan is None:
        return mapped
    try:
        source_price = Decimal(str(mapped.get("price")))
    except (InvalidOperation, TypeError):
        supplier_error(
            409, "PRICE_CONVERSION_FAILED", "Cena nije podobna za preračunavanje"
        )
    converted = (source_price * plan.rate.rate_to_rsd).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return {
        **mapped,
        "source_price": format(source_price, "f"),
        "source_currency": plan.currency_code,
        "exchange_rate": format(plan.rate.rate_to_rsd, ".8f"),
        "exchange_rate_id": str(plan.rate.id),
        "price_rsd": format(converted, ".2f"),
    }


__all__ = ["convert_supplier_price"]
