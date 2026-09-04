from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Protocol

from app.modules.suppliers.currency_contracts import SnapshotCurrencyPlan
from app.modules.suppliers.currency_models import (
    SupplierCurrencySetting,
    SupplierExchangeRate,
)
from app.modules.suppliers.errors import supplier_error


class CurrencyLookup(Protocol):
    async def active_setting(
        self, supplier_id: uuid.UUID, *, lock: bool = False
    ) -> SupplierCurrencySetting | None: ...
    async def latest_rate(
        self, setting_id: uuid.UUID, at: datetime | None = None
    ) -> SupplierExchangeRate | None: ...


async def build_snapshot_currency_plan(
    lookup: CurrencyLookup,
    supplier_id: uuid.UUID,
    records: Sequence[object],
    at: datetime,
) -> SnapshotCurrencyPlan | None:
    setting = await lookup.active_setting(supplier_id)
    if setting is None:
        return None
    observed = {
        str(getattr(record, "mapped_data").get("currency") or "").strip().upper()
        for record in records
    }
    observed.discard("")
    has_missing = any(
        not str(getattr(record, "mapped_data").get("currency") or "").strip()
        for record in records
    )
    if setting.currency_source == "PRICE_LIST" and (not observed or has_missing):
        supplier_error(
            409,
            "CURRENCY_MISSING",
            "Valuta nedostaje u cenovniku; ceo cenovnik je blokiran",
        )
    if observed and observed != {setting.currency_code}:
        values = ", ".join(sorted(observed))
        supplier_error(
            409,
            "CURRENCY_CHANGED",
            f"Očekivana valuta je {setting.currency_code}, a cenovnik sadrži: {values}",
        )
    rate = await lookup.latest_rate(setting.id, at)
    if rate is None:
        supplier_error(
            409,
            "EXCHANGE_RATE_MISSING",
            "Nema proverenog kursa koji važi za ovaj cenovnik",
        )
    if setting.currency_code != "RSD" and at - rate.effective_at > timedelta(
        hours=setting.max_rate_age_hours
    ):
        supplier_error(
            409, "EXCHANGE_RATE_STALE", "Kurs je zastareo; ceo cenovnik je blokiran"
        )
    return SnapshotCurrencyPlan(setting, rate, setting.currency_code)


__all__ = ["build_snapshot_currency_plan"]
