from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.currency_automation_service import (
    SupplierCurrencyAutomationService,
)
from app.modules.suppliers.pipeline_contracts import PipelineContext, PipelineResult


class CurrencyPhaseOwner(Protocol):
    session: AsyncSession

    async def _phase(
        self,
        context: PipelineContext,
        phase: str,
        *,
        started_at: datetime,
        started_clock: float,
        reference_id: str | None = None,
        processed_records: int = 0,
        result_code: str | None = None,
    ) -> PipelineResult: ...


async def run_currency_phase(
    owner: CurrencyPhaseOwner, context: PipelineContext
) -> None:
    started_at, started_clock = datetime.now(UTC), time.monotonic()
    result = await SupplierCurrencyAutomationService(owner.session).preflight(
        context.source
    )
    await owner._phase(
        context,
        "CURRENCY_RATE",
        started_at=started_at,
        started_clock=started_clock,
        reference_id=str(result.rate.id) if result.rate else None,
        result_code=result.status,
    )


__all__ = ["run_currency_phase"]
