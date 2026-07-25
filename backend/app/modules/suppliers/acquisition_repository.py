from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.acquisition_models import (
    SupplierAcquisitionIssue,
    SupplierAcquisitionRun,
    SupplierStagedRecord,
)


class SupplierAcquisitionRepository:
    """Acquisition queries and flush-only persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_run(self, run: SupplierAcquisitionRun) -> None:
        self.session.add(run)
        await self.session.flush()

    async def get_run(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        run_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierAcquisitionRun | None:
        query = select(SupplierAcquisitionRun).where(
            SupplierAcquisitionRun.id == run_id,
            SupplierAcquisitionRun.supplier_id == supplier_id,
            SupplierAcquisitionRun.source_connection_id == source_id,
        )
        if for_update:
            query = query.with_for_update()
        return (await self.session.execute(query)).scalar_one_or_none()

    async def by_idempotency(
        self,
        source_id: uuid.UUID,
        key: str,
    ) -> SupplierAcquisitionRun | None:
        return (
            await self.session.execute(
                select(SupplierAcquisitionRun).where(
                    SupplierAcquisitionRun.source_connection_id == source_id,
                    SupplierAcquisitionRun.idempotency_key == key,
                )
            )
        ).scalar_one_or_none()

    async def list_runs(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        *,
        status: str | None = None,
        trigger_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SupplierAcquisitionRun], int]:
        filters = [
            SupplierAcquisitionRun.supplier_id == supplier_id,
            SupplierAcquisitionRun.source_connection_id == source_id,
        ]
        if status:
            filters.append(SupplierAcquisitionRun.status == status)
        if trigger_type:
            filters.append(SupplierAcquisitionRun.trigger_type == trigger_type)
        total = await self.session.scalar(
            select(func.count(SupplierAcquisitionRun.id)).where(*filters)
        )
        rows = await self.session.execute(
            select(SupplierAcquisitionRun)
            .where(*filters)
            .order_by(
                SupplierAcquisitionRun.created_at.desc(),
                SupplierAcquisitionRun.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(rows.scalars()), int(total or 0)

    async def mutate_run(
        self,
        run: SupplierAcquisitionRun,
        changes: dict[str, object],
    ) -> None:
        for field, value in changes.items():
            setattr(run, field, value)
        await self.session.flush()

    async def add_results(
        self,
        records: list[SupplierStagedRecord],
        issues: list[SupplierAcquisitionIssue],
    ) -> None:
        self.session.add_all(records)
        await self.session.flush()
        self.session.add_all(issues)
        await self.session.flush()

    async def list_records(
        self,
        run_id: uuid.UUID,
        *,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SupplierStagedRecord], int]:
        filters = [SupplierStagedRecord.acquisition_run_id == run_id]
        if status:
            filters.append(SupplierStagedRecord.validation_status == status)
        total = await self.session.scalar(
            select(func.count(SupplierStagedRecord.id)).where(*filters)
        )
        rows = await self.session.execute(
            select(SupplierStagedRecord)
            .where(*filters)
            .order_by(SupplierStagedRecord.record_number)
            .limit(limit)
            .offset(offset)
        )
        return list(rows.scalars()), int(total or 0)

    async def get_record(
        self,
        run_id: uuid.UUID,
        record_id: uuid.UUID,
    ) -> SupplierStagedRecord | None:
        return (
            await self.session.execute(
                select(SupplierStagedRecord).where(
                    SupplierStagedRecord.id == record_id,
                    SupplierStagedRecord.acquisition_run_id == run_id,
                )
            )
        ).scalar_one_or_none()

    async def list_issues(
        self,
        run_id: uuid.UUID,
        *,
        severity: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SupplierAcquisitionIssue], int]:
        filters = [SupplierAcquisitionIssue.acquisition_run_id == run_id]
        if severity:
            filters.append(SupplierAcquisitionIssue.severity == severity)
        total = await self.session.scalar(
            select(func.count(SupplierAcquisitionIssue.id)).where(*filters)
        )
        rows = await self.session.execute(
            select(SupplierAcquisitionIssue)
            .where(*filters)
            .order_by(
                SupplierAcquisitionIssue.record_number,
                SupplierAcquisitionIssue.id,
            )
            .limit(limit)
            .offset(offset)
        )
        return list(rows.scalars()), int(total or 0)


__all__ = ["SupplierAcquisitionRepository"]
