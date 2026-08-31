from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.pipeline_models import (
    SupplierSchemaCompatibilityReport,
    SupplierSourceArtifact,
    SupplierSourcePipelineRun,
    SupplierSourceSchedule,
)
from app.modules.suppliers.models import Supplier, SupplierSource


class SupplierPipelineRepository:
    """Pipeline persistence boundary; mutations flush and never commit."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        entity: (
            SupplierSourceArtifact
            | SupplierSourcePipelineRun
            | SupplierSourceSchedule
            | SupplierSchemaCompatibilityReport
        ),
    ) -> None:
        self.session.add(entity)
        await self.session.flush()

    async def mutate(self, entity: object, changes: dict[str, object]) -> None:
        for field, value in changes.items():
            setattr(entity, field, value)
        await self.session.flush()

    async def schedule(
        self,
        source_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierSourceSchedule | None:
        query = select(SupplierSourceSchedule).where(
            SupplierSourceSchedule.source_connection_id == source_id
        )
        if for_update:
            query = query.with_for_update()
        return (await self.session.execute(query)).scalar_one_or_none()

    async def due_schedules(
        self,
        now: datetime,
        *,
        limit: int,
    ) -> list[SupplierSourceSchedule]:
        rows = await self.session.execute(
            select(SupplierSourceSchedule)
            .where(
                SupplierSourceSchedule.status == "ENABLED",
                SupplierSourceSchedule.next_run_at.is_not(None),
                SupplierSourceSchedule.next_run_at <= now,
            )
            .order_by(
                SupplierSourceSchedule.next_run_at,
                SupplierSourceSchedule.id,
            )
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        return list(rows.scalars())

    async def list_schedules(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[
        list[tuple[SupplierSourceSchedule, SupplierSource, Supplier]],
        int,
    ]:
        total = await self.session.scalar(
            select(func.count(SupplierSourceSchedule.id))
        )
        rows = await self.session.execute(
            select(SupplierSourceSchedule, SupplierSource, Supplier)
            .join(
                SupplierSource,
                SupplierSource.id == SupplierSourceSchedule.source_connection_id,
            )
            .join(Supplier, Supplier.id == SupplierSource.supplier_id)
            .order_by(Supplier.company_name, SupplierSource.name)
            .limit(limit)
            .offset(offset)
        )
        return list(rows.tuples()), int(total or 0)

    async def update_schedule_result(
        self,
        schedule_id: uuid.UUID,
        *,
        status: str,
        duration_ms: int,
        consecutive_failures: int,
        version: int,
    ) -> None:
        await self.session.execute(
            update(SupplierSourceSchedule)
            .where(
                SupplierSourceSchedule.id == schedule_id,
                SupplierSourceSchedule.version == version,
            )
            .values(
                last_result=status,
                last_duration_ms=duration_ms,
                consecutive_failures=consecutive_failures,
                version=version + 1,
            )
            .execution_options(synchronize_session=False)
        )
        await self.session.flush()

    async def pipeline_run(
        self,
        source_id: uuid.UUID,
        run_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierSourcePipelineRun | None:
        query = select(SupplierSourcePipelineRun).where(
            SupplierSourcePipelineRun.id == run_id,
            SupplierSourcePipelineRun.source_connection_id == source_id,
        )
        if for_update:
            query = query.with_for_update()
        return (await self.session.execute(query)).scalar_one_or_none()

    async def pipeline_by_idempotency(
        self, idempotency_key: str
    ) -> SupplierSourcePipelineRun | None:
        return (
            await self.session.execute(
                select(SupplierSourcePipelineRun).where(
                    SupplierSourcePipelineRun.idempotency_key == idempotency_key
                )
            )
        ).scalar_one_or_none()

    async def active_pipeline(
        self, source_id: uuid.UUID
    ) -> SupplierSourcePipelineRun | None:
        return (
            await self.session.execute(
                select(SupplierSourcePipelineRun).where(
                    SupplierSourcePipelineRun.source_connection_id == source_id,
                    SupplierSourcePipelineRun.status.in_(("PENDING", "RUNNING")),
                )
            )
        ).scalar_one_or_none()

    async def list_pipeline_runs(
        self,
        source_id: uuid.UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[SupplierSourcePipelineRun], int]:
        filters = [SupplierSourcePipelineRun.source_connection_id == source_id]
        total = await self.session.scalar(
            select(func.count(SupplierSourcePipelineRun.id)).where(*filters)
        )
        rows = await self.session.execute(
            select(SupplierSourcePipelineRun)
            .where(*filters)
            .order_by(
                SupplierSourcePipelineRun.created_at.desc(),
                SupplierSourcePipelineRun.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(rows.scalars()), int(total or 0)

    async def artifact(
        self, source_id: uuid.UUID, artifact_id: uuid.UUID
    ) -> SupplierSourceArtifact | None:
        return (
            await self.session.execute(
                select(SupplierSourceArtifact).where(
                    SupplierSourceArtifact.id == artifact_id,
                    SupplierSourceArtifact.source_connection_id == source_id,
                )
            )
        ).scalar_one_or_none()

    async def compatibility_report(
        self, run_id: uuid.UUID
    ) -> SupplierSchemaCompatibilityReport | None:
        return (
            await self.session.execute(
                select(SupplierSchemaCompatibilityReport).where(
                    SupplierSchemaCompatibilityReport.pipeline_run_id == run_id
                )
            )
        ).scalar_one_or_none()


__all__ = ["SupplierPipelineRepository"]
