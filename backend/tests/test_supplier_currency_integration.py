from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token
from app.modules.suppliers.currency_models import (
    SupplierCurrencyEvent,
    SupplierCurrencySetting,
    SupplierExchangeRate,
)
from app.modules.suppliers.models import Supplier

API_ROOT = "http://localhost:8000/api/v1"
DATABASE_URL = os.getenv(
    "PRODUCT_CONTENT_INTEGRATION_DATABASE_URL", settings.database_url
)


def _bearer(subject: str, role: str = "system_admin") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject, (role,))}"}


async def _purge(supplier_id: str) -> None:
    engine = create_async_engine(DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            sid = uuid.UUID(supplier_id)
            setting_ids = list(
                (
                    await session.scalars(
                        select(SupplierCurrencySetting.id).where(
                            SupplierCurrencySetting.supplier_id == sid
                        )
                    )
                ).all()
            )
            await session.execute(
                delete(SupplierCurrencyEvent).where(
                    SupplierCurrencyEvent.supplier_id == sid
                )
            )
            if setting_ids:
                await session.execute(
                    delete(SupplierExchangeRate).where(
                        SupplierExchangeRate.currency_setting_id.in_(setting_ids)
                    )
                )
            await session.execute(
                delete(SupplierCurrencySetting).where(
                    SupplierCurrencySetting.supplier_id == sid
                )
            )
            await session.execute(delete(Supplier).where(Supplier.id == sid))
            await session.commit()
    finally:
        await engine.dispose()


def test_currency_setting_rate_history_and_permissions() -> None:
    supplier_id = ""
    with httpx.Client(
        base_url=API_ROOT, timeout=15, headers=_bearer("currency-admin")
    ) as client:
        try:
            created = client.post(
                "/suppliers",
                json={
                    "company_name": f"Currency Test {uuid.uuid4().hex[:8]}",
                    "status": "ACTIVE",
                },
            )
            assert created.status_code == 201, created.text
            supplier_id = created.json()["id"]
            monitor = client.get("/suppliers/platform/supplier-currencies/monitor")
            assert monitor.status_code == 200
            assert monitor.json()["currency_code"] == "RSD"
            assert monitor.json()["rate_to_rsd"] == "1.00000000"
            configured = client.put(
                f"/suppliers/platform/supplier-currencies/{supplier_id}",
                json={
                    "currency_code": "EUR",
                    "currency_source": "PRICE_LIST",
                    "rate_mode": "MANUAL",
                    "max_rate_age_hours": 48,
                },
            )
            assert configured.status_code == 200, configured.text
            assert configured.json()["rate_status"] == "MISSING"
            rate = client.post(
                f"/suppliers/platform/supplier-currencies/{supplier_id}/rates",
                json={
                    "rate_to_rsd": "117.36",
                    "effective_at": datetime.now(UTC).isoformat(),
                    "source_type": "MANUAL",
                    "note": "Kurs dobavljača za integracioni test",
                },
            )
            assert rate.status_code == 200, rate.text
            history = client.get(
                f"/suppliers/platform/supplier-currencies/{supplier_id}/rates"
            )
            assert history.status_code == 200
            assert history.json()[0]["rate_to_rsd"] == "117.36000000"
            listing = client.get("/suppliers/platform/supplier-currencies")
            row = next(
                item
                for item in listing.json()["items"]
                if item["supplier_id"] == supplier_id
            )
            assert row["rate_status"] == "CURRENT"
            stale = client.put(
                f"/suppliers/platform/supplier-currencies/{supplier_id}",
                json={
                    "currency_code": "EUR",
                    "currency_source": "PRICE_LIST",
                    "rate_mode": "MANUAL",
                    "max_rate_age_hours": 48,
                    "expected_version": 999,
                },
            )
            assert stale.status_code == 409
            with httpx.Client(
                base_url=API_ROOT,
                timeout=15,
                headers=_bearer("currency-reader", "read_only"),
            ) as reader:
                assert (
                    reader.get("/suppliers/platform/supplier-currencies").status_code
                    == 200
                )
                assert (
                    reader.put(
                        f"/suppliers/platform/supplier-currencies/{supplier_id}",
                        json={"currency_code": "RSD", "rate_mode": "FIXED"},
                    ).status_code
                    == 403
                )
        finally:
            if supplier_id:
                asyncio.run(_purge(supplier_id))
