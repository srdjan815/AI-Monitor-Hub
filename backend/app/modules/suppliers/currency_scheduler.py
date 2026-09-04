from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.execution.models import Job
from app.modules.suppliers.currency_models import SupplierCurrencySetting
from app.modules.suppliers.currency_automation_service import next_daily_check


class SupplierCurrencyScheduler:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def dispatch_due(self, now: datetime | None = None, limit: int = 25) -> int:
        current = now or datetime.now(UTC)
        settings = list(
            (
                await self.session.scalars(
                    select(SupplierCurrencySetting)
                    .where(
                        SupplierCurrencySetting.is_active.is_(True),
                        SupplierCurrencySetting.rate_mode == "AUTOMATIC",
                        SupplierCurrencySetting.next_check_at <= current,
                    )
                    .order_by(
                        SupplierCurrencySetting.next_check_at,
                        SupplierCurrencySetting.id,
                    )
                    .with_for_update(skip_locked=True)
                    .limit(limit)
                )
            ).all()
        )
        for setting in settings:
            occurrence = setting.next_check_at
            if occurrence is None:
                continue
            self.session.add(
                Job(
                    job_type="supplier.currency_rate",
                    queue="default",
                    priority=90,
                    status="PENDING",
                    payload={
                        "supplier_id": str(setting.supplier_id),
                        "timeout_seconds": 30,
                    },
                    max_attempts=3,
                    available_at=current,
                    idempotency_key=f"supplier-currency:{setting.id}:{occurrence.isoformat()}",
                    created_by="currency-scheduler",
                )
            )
            setting.next_check_at = next_daily_check(setting.daily_check_time, current)
        await self.session.commit()
        return len(settings)


__all__ = ["SupplierCurrencyScheduler"]
