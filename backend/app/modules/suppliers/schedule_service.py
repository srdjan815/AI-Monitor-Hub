from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.core.security import current_actor_id
from app.modules.execution.models import Job
from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.pipeline_models import (
    SupplierSourcePipelineRun,
    SupplierSourceSchedule,
)
from app.modules.suppliers.pipeline_repository import SupplierPipelineRepository
from app.modules.suppliers.pipeline_scheduler import (
    SupplierPipelineScheduleCalculator,
)
from app.modules.suppliers.pipeline_recovery_service import (
    SupplierPipelineRecoveryService,
)
from app.modules.suppliers.models import SupplierSource
from app.modules.suppliers.incident_models import SupplierIncident
from app.modules.suppliers.incident_support import SupplierIncidentSupport
from app.modules.suppliers.mapping_profile_repository import SupplierMappingRepository
from app.modules.suppliers.schema_profile_repository import SupplierSchemaRepository
from app.modules.suppliers.schedule_schemas import (
    AutomationDepth,
    PipelineRunNowRequest,
    PipelineRunQueued,
    SupplierScheduleList,
    SupplierScheduleListItem,
    SupplierScheduleRead,
    SupplierScheduleWrite,
)
from app.modules.suppliers.source_repository import SupplierSourceRepository


class SupplierScheduleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SupplierPipelineRepository(session)
        self.sources = SupplierSourceRepository(session)

    async def _source(
        self, supplier_id: uuid.UUID, source_id: uuid.UUID
    ) -> SupplierSource:
        source = await self.sources.get_source(supplier_id, source_id)
        if source is None:
            supplier_error(
                404, "supplier_source_not_found", "Konekcija nije pronaÄ‘ena"
            )
        return source

    async def get(
        self, supplier_id: uuid.UUID, source_id: uuid.UUID
    ) -> SupplierScheduleRead | None:
        await self._source(supplier_id, source_id)
        schedule = await self.repository.schedule(source_id)
        return (
            SupplierScheduleRead.model_validate(schedule)
            if schedule is not None
            else None
        )

    async def save(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        data: SupplierScheduleWrite,
    ) -> SupplierScheduleRead:
        source = await self._source(supplier_id, source_id)
        if not source.is_active:
            supplier_error(
                409,
                "supplier_schedule_source_inactive",
                "Arhivirana konekcija ne moÅ¾e imati aktivan raspored",
            )
        if data.status == "ENABLED" and source.status != "ACTIVE":
            supplier_error(
                409,
                "supplier_schedule_source_not_ready",
                "Raspored se moÅ¾e uključiti tek kada je konekcija ACTIVE",
            )
        schedule = await self.repository.schedule(source_id, for_update=True)
        if schedule is not None and data.version != schedule.version:
            supplier_error(
                409,
                "supplier_schedule_version_conflict",
                "Raspored je u meÄ‘uvremenu izmenjen; osveÅ¾ite podatke",
            )
        if schedule is None and data.version is not None:
            supplier_error(
                409,
                "supplier_schedule_version_conflict",
                "Raspored joÅ¡ ne postoji",
            )
        configuration = data.configuration()
        next_run_at = None
        if data.status == "ENABLED":
            preview = type(
                "SchedulePreview",
                (),
                {
                    "timezone": data.timezone,
                    "schedule_type": data.schedule_type,
                    "schedule_configuration": configuration,
                },
            )()
            try:
                next_run_at = SupplierPipelineScheduleCalculator.next_run(
                    preview, datetime.now(UTC)
                )
            except ValueError as exc:
                supplier_error(
                    422,
                    str(exc),
                    "Raspored nije ispravno podeÅ¡en",
                )
        values: dict[str, object] = {
            "status": data.status,
            "schedule_type": data.schedule_type,
            "timezone": data.timezone,
            "schedule_configuration": configuration,
            "automation_depth": data.automation_depth,
            "next_run_at": next_run_at,
            "timeout_seconds": data.timeout_seconds,
            "max_attempts": data.max_attempts,
        }
        try:
            if schedule is None:
                schedule = SupplierSourceSchedule(
                    source_connection_id=source_id,
                    **values,
                )
                await self.repository.add(schedule)
            else:
                values["version"] = schedule.version + 1
                await self.repository.mutate(schedule, values)
            await self.session.commit()
        except (IntegrityError, StaleDataError) as exc:
            await self.session.rollback()
            supplier_error(
                409,
                "supplier_schedule_conflict",
                "Raspored nije saÄuvan zbog paralelne izmene",
            )
            raise AssertionError from exc
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(schedule)
        return SupplierScheduleRead.model_validate(schedule)

    async def report_not_ready(
        self, supplier_id: uuid.UUID, source_id: uuid.UUID
    ) -> SupplierIncident:
        source = await self._source(supplier_id, source_id)
        schema = await SupplierSchemaRepository(self.session).active_profile(source.id)
        mapping = (
            await SupplierMappingRepository(self.session).active_profile(schema.id)
            if schema is not None
            else None
        )
        missing: list[str] = []
        if source.status != "ACTIVE":
            missing.append("aktivna konekcija cenovnika")
        if schema is None:
            missing.append("aktivna schema")
        if mapping is None:
            missing.append("aktivno mapiranje")
        if not missing:
            supplier_error(
                409,
                "supplier_schedule_source_ready",
                "Konekcija je spremna i ne zahteva incident konfiguracije",
            )
        return await SupplierIncidentSupport(self.session).create_or_occurrence(
            incident_id=uuid.uuid4(),
            supplier_id=supplier_id,
            source_id=source.id,
            source_domain="SOURCE_CONNECTION",
            incident_type="CONFIGURATION_REVIEW_REQUIRED",
            severity="MEDIUM",
            priority="P3",
            title="Dobavljaču nije potpuno integrisan cenovnik",
            description=(
                f"Konekcija {source.name} nije uključena u automatski raspored. "
                f"Nedostaje: {', '.join(missing)}."
            ),
            source_entity_id=source.id,
            context={
                "source_status": source.status,
                "missing": missing,
                "automation_action": "SKIPPED_NOT_READY",
            },
        )

    async def list(self, *, limit: int, offset: int) -> SupplierScheduleList:
        rows, total = await self.repository.list_schedules(
            limit=limit,
            offset=offset,
        )
        items = [
            SupplierScheduleListItem(
                **SupplierScheduleRead.model_validate(schedule).model_dump(),
                supplier_id=supplier.id,
                supplier_name=supplier.company_name,
                source_name=source.name,
                source_code=source.source_code,
            )
            for schedule, source, supplier in rows
        ]
        return SupplierScheduleList(items=items, total=total)

    async def run_now(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        data: PipelineRunNowRequest,
    ) -> PipelineRunQueued:
        source = await self._source(supplier_id, source_id)
        if not source.is_active or source.status != "ACTIVE":
            supplier_error(
                409,
                "pipeline_source_not_active",
                "Samo aktivna i proverena konekcija moÅ¾e pokrenuti pipeline",
            )
        existing = await self.repository.pipeline_by_idempotency(data.idempotency_key)
        if existing is not None and existing.job_id is not None:
            return PipelineRunQueued(
                pipeline_run_id=existing.id,
                pipeline_code=existing.pipeline_code,
                job_id=existing.job_id,
                status=existing.status,
                automation_depth=cast(AutomationDepth, existing.automation_depth),
            )
        await self.repository.lock_global_pipeline_dispatch()
        recovery = SupplierPipelineRecoveryService(self.session)
        recovery.repository = self.repository
        await recovery.recover_global()
        if await self.repository.blocking_pipeline_global() is not None:
            supplier_error(
                409,
                "supplier_pipeline_already_running",
                "Drugi dobavljački pipeline je već pokrenut; pokušajte ponovo kada se završi",
            )
        schedule = await self.repository.schedule(source_id)
        timeout_seconds = schedule.timeout_seconds if schedule is not None else 300
        max_attempts = schedule.max_attempts if schedule is not None else 3
        run = SupplierSourcePipelineRun(
            source_connection_id=source_id,
            trigger_type="MANUAL",
            automation_depth=data.automation_depth,
            status="PENDING",
            current_phase="CURRENCY_RATE",
            phase_results={},
            idempotency_key=data.idempotency_key,
            created_by=current_actor_id() or "system",
        )
        try:
            await self.repository.add(run)
            job = Job(
                job_type="supplier.pipeline",
                queue="default",
                priority=100,
                status="PENDING",
                payload={
                    "source_id": str(source_id),
                    "pipeline_run_id": str(run.id),
                    "timeout_seconds": timeout_seconds,
                },
                max_attempts=max_attempts,
                available_at=datetime.now(UTC),
                idempotency_key=f"{data.idempotency_key}:job",
                created_by=current_actor_id() or "system",
            )
            self.session.add(job)
            await self.session.flush()
            await self.repository.mutate(run, {"job_id": job.id})
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            supplier_error(
                409,
                "supplier_pipeline_conflict",
                "Pipeline je veÄ‡ pokrenut ili je zahtev veÄ‡ obraÄ‘en",
            )
            raise AssertionError from exc
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(run)
        return PipelineRunQueued(
            pipeline_run_id=run.id,
            pipeline_code=run.pipeline_code,
            job_id=job.id,
            status=run.status,
            automation_depth=cast(AutomationDepth, run.automation_depth),
        )


__all__ = ["SupplierScheduleService"]
