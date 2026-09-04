from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    CURRENCY_RATES_READ,
    CURRENCY_RATES_WRITE,
    require_current_permission,
)
from app.db.session import get_db
from app.modules.suppliers.currency_schemas import (
    CurrencyEventList,
    CurrencySettingList,
    CurrencySettingRead,
    CurrencySettingWrite,
    CurrencySourceTestRead,
    CurrencySourceTestRequest,
    ExchangeRateCreate,
    ExchangeRateRead,
    MonitorCurrencyRead,
)
from app.modules.suppliers.currency_service import SupplierCurrencyService
from app.modules.suppliers.currency_automation_service import SupplierCurrencyAutomationService

router = APIRouter(prefix="/supplier-currencies", tags=["supplier-currency-center"])


@router.get("/monitor", response_model=MonitorCurrencyRead)
async def monitor_currency(
    session: AsyncSession = Depends(get_db),
) -> MonitorCurrencyRead:
    require_current_permission(CURRENCY_RATES_READ)
    value = await SupplierCurrencyService(session).monitor()
    return MonitorCurrencyRead(
        currency_code="RSD", rate_to_rsd=value.rate_to_rsd, version=value.version
    )


@router.get("", response_model=CurrencySettingList)
async def list_currency_settings(
    supplier_id: uuid.UUID | None = None, session: AsyncSession = Depends(get_db)
) -> CurrencySettingList:
    require_current_permission(CURRENCY_RATES_READ)
    return await SupplierCurrencyService(session).list_settings(supplier_id=supplier_id)


@router.put("/{supplier_id}", response_model=CurrencySettingRead)
async def save_currency_setting(
    supplier_id: uuid.UUID,
    payload: CurrencySettingWrite,
    session: AsyncSession = Depends(get_db),
) -> CurrencySettingRead:
    require_current_permission(CURRENCY_RATES_WRITE)
    return await SupplierCurrencyService(session).upsert(supplier_id, payload)


@router.get("/{supplier_id}/rates", response_model=list[ExchangeRateRead])
async def list_rates(
    supplier_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
) -> list[ExchangeRateRead]:
    require_current_permission(CURRENCY_RATES_READ)
    return [
        ExchangeRateRead.model_validate(item)
        for item in await SupplierCurrencyService(session).rates(supplier_id, limit)
    ]


@router.post("/{supplier_id}/test-source", response_model=CurrencySourceTestRead)
async def test_currency_source(
    supplier_id: uuid.UUID,
    payload: CurrencySourceTestRequest,
    session: AsyncSession = Depends(get_db),
) -> CurrencySourceTestRead:
    require_current_permission(CURRENCY_RATES_WRITE)
    return await SupplierCurrencyAutomationService(session).test_source(supplier_id, payload)


@router.post("/{supplier_id}/rates", response_model=ExchangeRateRead)
async def add_rate(
    supplier_id: uuid.UUID,
    payload: ExchangeRateCreate,
    session: AsyncSession = Depends(get_db),
) -> ExchangeRateRead:
    require_current_permission(CURRENCY_RATES_WRITE)
    return ExchangeRateRead.model_validate(
        await SupplierCurrencyService(session).add_rate(supplier_id, payload)
    )


@router.get("/{supplier_id}/events", response_model=CurrencyEventList)
async def currency_events(
    supplier_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
) -> CurrencyEventList:
    require_current_permission(CURRENCY_RATES_READ)
    return await SupplierCurrencyService(session).events(supplier_id, limit)


__all__ = ["router"]
