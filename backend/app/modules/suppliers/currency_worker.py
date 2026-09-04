from __future__ import annotations

import uuid
from typing import Any

from app.db.session import AsyncSessionLocal
from app.modules.execution.protocols import (
    JobExecutionContext,
    JobResult,
    PermanentJobError,
)
from app.modules.suppliers.currency_automation_service import (
    SupplierCurrencyAutomationService,
)


async def supplier_currency_rate_handler(
    context: JobExecutionContext, payload: dict[str, Any]
) -> JobResult:
    await context.checkpoint()
    try:
        supplier_id = uuid.UUID(str(payload["supplier_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise PermanentJobError("supplier_id nije ispravan") from exc
    async with AsyncSessionLocal() as session:
        rate = await SupplierCurrencyAutomationService(session).refresh(supplier_id)
    await context.checkpoint()
    return JobResult(
        data={"supplier_id": str(supplier_id), "exchange_rate_id": str(rate.id)}
    )


__all__ = ["supplier_currency_rate_handler"]
