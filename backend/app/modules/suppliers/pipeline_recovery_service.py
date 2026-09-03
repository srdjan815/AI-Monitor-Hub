from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.execution.enums import JobStatus
from app.modules.execution.models import Job
from app.modules.suppliers.pipeline_contracts import PipelineContext
from app.modules.suppliers.pipeline_failure_support import failed_phase_results
from app.modules.suppliers.pipeline_incident_service import SupplierPipelineIncidentService
from app.modules.suppliers.pipeline_models import SupplierSourcePipelineRun
from app.modules.suppliers.pipeline_repository import SupplierPipelineRepository
from app.modules.suppliers.repository import SupplierRepository
from app.modules.suppliers.source_repository import SupplierSourceRepository

logger = logging.getLogger(__name__)

TERMINAL_JOB_STATUSES = {
    JobStatus.SUCCEEDED.value,
    JobStatus.FAILED.value,
    JobStatus.CANCELLED.value,
    JobStatus.DEAD_LETTER.value,
}


class SupplierPipelineRecoveryService:
    """Reconciles a terminal worker job with its still-active pipeline run."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SupplierPipelineRepository(session)
        self.sources = SupplierSourceRepository(session)
        self.suppliers = SupplierRepository(session)

    async def recover_source(self, source_id: uuid.UUID) -> bool:
        run = await self.repository.active_pipeline(source_id)
        return await self._recover(run)

    async def recover_global(self) -> bool:
        run = await self.repository.active_pipeline_global()
        return await self._recover(run)

    async def fail_if_active(
        self,
        source_id: uuid.UUID,
        run_id: uuid.UUID,
        *,
        code: str,
        message: str,
    ) -> bool:
        run = await self.repository.pipeline_run(source_id, run_id, for_update=True)
        if run is None or run.status not in {"PENDING", "RUNNING"}:
            await self.session.rollback()
            return False
        await self._fail(run, code=code, message=message)
        return True

    async def _recover(self, run: SupplierSourcePipelineRun | None) -> bool:
        if run is None or getattr(run, "job_id", None) is None:
            return False
        job = await self.session.get(Job, run.job_id)
        if job is None or job.status not in TERMINAL_JOB_STATUSES:
            return False
        code = (
            "pipeline_worker_dead_letter"
            if job.status == JobStatus.DEAD_LETTER.value
            else "pipeline_worker_terminal_mismatch"
        )
        message = (
            "Worker je završio neuspešno, ali pipeline nije bio zatvoren. "
            "Pipeline je automatski oporavljen i može se ponovo pokrenuti."
        )
        await self._fail(run, code=code, message=message)
        return True

    async def _fail(
        self,
        run: SupplierSourcePipelineRun,
        *,
        code: str,
        message: str,
    ) -> None:
        source_id, run_id = run.source_connection_id, run.id
        phase = run.current_phase
        await self.repository.mutate(
            run,
            {
                "status": "FAILED",
                "phase_results": failed_phase_results(run.phase_results, phase, code),
                "failure_code": code,
                "failure_message": message[:1000],
                "completed_at": datetime.now(UTC),
                "version": run.version + 1,
            },
        )
        await self.session.commit()
        source = await self.sources.get_source_by_id(source_id)
        supplier = (
            await self.suppliers.get_supplier(source.supplier_id)
            if source is not None
            else None
        )
        refreshed = await self.repository.pipeline_run(source_id, run_id)
        if source is None or supplier is None or refreshed is None:
            logger.error(
                "Pipeline recovered without incident context source_id=%s run_id=%s",
                source_id,
                run_id,
            )
            return
        context = PipelineContext(
            supplier=supplier,
            source=source,
            run=refreshed,
            trigger=refreshed.trigger_type,
            idempotency_key=refreshed.idempotency_key,
            logger=logger,
        )
        await SupplierPipelineIncidentService(self.session).record_failure(
            context, code, message
        )


__all__ = ["SupplierPipelineRecoveryService", "TERMINAL_JOB_STATUSES"]
