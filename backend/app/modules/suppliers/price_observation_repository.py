from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.retention_models import SupplierPriceObservation
from app.modules.suppliers.snapshot_models import SupplierSnapshot, SupplierSnapshotItem


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _currency(value: object) -> str:
    code = str(value or "").strip().upper()
    return code if re.fullmatch(r"[A-Z]{3}", code) else "RSD"


def observation_values(
    snapshot: SupplierSnapshot, item: SupplierSnapshotItem
) -> dict[str, object] | None:
    data = item.mapped_data
    code = str(data.get("product_code") or item.source_identifier or "").strip()
    price_rsd = _decimal(data.get("price_rsd") or data.get("price"))
    if not code or price_rsd is None or price_rsd < 0:
        return None
    normalized = code.casefold()
    ean = str(data.get("ean") or "").strip() or None
    source_price = _decimal(data.get("source_price") or data.get("price"))
    exchange_rate = _decimal(data.get("exchange_rate") or snapshot.exchange_rate_to_rsd)
    stock = _decimal(data.get("stock"))
    if stock is not None and stock < 0:
        stock = None
    currency = _currency(
        data.get("source_currency") or data.get("currency") or snapshot.source_currency
    )
    return {
        "snapshot_id": snapshot.id,
        "snapshot_item_id": item.id,
        "supplier_id": snapshot.supplier_id,
        "source_connection_id": snapshot.source_connection_id,
        "product_code": code,
        "product_code_normalized": normalized,
        "identity_key": (
            f"ean:{ean}"
            if ean
            else f"supplier:{snapshot.supplier_id}:code:{normalized}"
        ),
        "ean": ean,
        "product_name": str(data.get("name") or "").strip() or None,
        "category_name": str(data.get("category") or "").strip() or None,
        "source_currency": currency,
        "source_price": source_price,
        "exchange_rate_to_rsd": exchange_rate,
        "price_rsd": price_rsd,
        "stock": stock,
        "item_fingerprint": item.item_fingerprint,
        "observed_at": snapshot.finalized_at or snapshot.created_at,
    }


class SupplierPriceObservationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def preserve_snapshot(
        self, snapshot: SupplierSnapshot, items: list[SupplierSnapshotItem]
    ) -> int:
        values = [
            value
            for item in items
            if (value := observation_values(snapshot, item)) is not None
        ]
        if not values:
            return 0
        statement = insert(SupplierPriceObservation).values(values)
        statement = statement.on_conflict_do_nothing(
            index_elements=[SupplierPriceObservation.snapshot_item_id]
        )
        await self.session.execute(statement)
        return len(values)


__all__ = ["SupplierPriceObservationRepository", "observation_values"]
