from __future__ import annotations

from dataclasses import dataclass

from app.modules.suppliers.currency_models import SupplierCurrencySetting, SupplierExchangeRate


@dataclass(frozen=True, slots=True)
class SnapshotCurrencyPlan:
    setting: SupplierCurrencySetting
    rate: SupplierExchangeRate
    currency_code: str


__all__ = ["SnapshotCurrencyPlan"]
