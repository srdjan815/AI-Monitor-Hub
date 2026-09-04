from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import current_actor_id
from app.modules.suppliers.pipeline_models import SupplierSourcePipelineRun
from app.modules.suppliers.pipeline_repository import SupplierPipelineRepository
from app.modules.suppliers.pipeline_recovery_service import (
    SupplierPipelineRecoveryService,
)
from app.modules.suppliers.source_repository import SupplierSourceRepository
from app.modules.suppliers.errors import supplier_error


class SupplierPipelineRunService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SupplierPipelineRepository(session)
        self.sources = SupplierSourceRepository(session)

    async def create(
        self,
        source_id: uuid.UUID,
        *,
        trigger: str,
        automation_depth: str,
        idempotency_key: str,
        schedule_id: uuid.UUID | None = None,
        schedule_occurrence_at: datetime | None = None,
        job_id: uuid.UUID | None = None,
    ) -> SupplierSourcePipelineRun:
        existing = await self.repository.pipeline_by_idempotency(idempotency_key)
        if existing is not None:
            return existing
        source = await self.sources.get_source_by_id(source_id)
        if source is None or not source.is_active or source.status != "ACTIVE":
            raise ValueError("pipeline_source_not_active")
        await SupplierPipelineRecoveryService(self.session).recover_source(source_id)
        if await self.repository.active_pipeline(source_id) is not None:
            supplier_error(
                409,
                "supplier_pipeline_already_running",
                "Obrada ovog dobavljača je već pokrenuta. Sačekajte završetak ili proverite Incident centar.",
            )
        run = SupplierSourcePipelineRun(
            source_connection_id=source.id,
            schedule_id=schedule_id,
            job_id=job_id,
            trigger_type=trigger,
            automation_depth=automation_depth,
            status="PENDING",
            current_phase="CURRENCY_RATE",
            phase_results={},
            idempotency_key=idempotency_key,
            schedule_occurrence_at=schedule_occurrence_at,
            created_by=current_actor_id() or "system",
        )
        try:
            await self.repository.add(run)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            existing = await self.repository.pipeline_by_idempotency(idempotency_key)
            if existing is not None:
                return existing
            supplier_error(
                409,
                "supplier_pipeline_already_running",
                "Obrada ovog dobavljača je već pokrenuta. Sačekajte završetak ili proverite Incident centar.",
            )
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(run)
        return run


__all__ = ["SupplierPipelineRunService"]
