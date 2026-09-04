from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.suppliers.acquisition_adapters import (
    SourceAdapterRegistry,
    UrllibHttpClient,
)
from app.modules.suppliers.mapping_profile_repository import SupplierMappingRepository
from app.modules.suppliers.pipeline_contracts import (
    PipelineContext,
    PipelinePhaseResult,
    PipelineReferences,
    PipelineResult,
)
from app.modules.suppliers.pipeline_models import SupplierSchemaCompatibilityReport
from app.modules.suppliers.pipeline_compatibility_service import (
    SupplierPipelineCompatibilityService,
)
from app.modules.suppliers.pipeline_repository import SupplierPipelineRepository
from app.modules.suppliers.pipeline_failure_support import failed_phase_results
from app.modules.suppliers.pipeline_incident_service import (
    SupplierPipelineIncidentService,
)
from app.modules.suppliers.repository import SupplierRepository
from app.modules.suppliers.schema_compatibility_service import (
    SupplierSchemaCompatibilityService,
)
from app.modules.suppliers.schema_inference_service import (
    SupplierSchemaInferenceService,
)
from app.modules.suppliers.schema_profile_models import SupplierSchemaProfile
from app.modules.suppliers.schema_profile_repository import SupplierSchemaRepository
from app.modules.suppliers.source_artifact_service import SupplierSourceArtifactService
from app.modules.suppliers.source_repository import SupplierSourceRepository
from app.modules.suppliers.source_secrets import source_secret_provider

logger = logging.getLogger(__name__)


class SupplierPipelineOrchestratorSupport:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SupplierPipelineRepository(session)
        self.suppliers = SupplierRepository(session)
        self.sources = SupplierSourceRepository(session)
        self.schemas = SupplierSchemaRepository(session)
        self.mappings = SupplierMappingRepository(session)
        self.artifacts = SupplierSourceArtifactService(session)
        self.inference = SupplierSchemaInferenceService(session)
        self.compatibility = SupplierSchemaCompatibilityService()
        self.adapters = SourceAdapterRegistry(
            UrllibHttpClient(),
            source_secret_provider,
            settings.acquisition_max_artifact_bytes,
        )

    async def _context(
        self, source_id: uuid.UUID, run_id: uuid.UUID
    ) -> PipelineContext:
        run = await self.repository.pipeline_run(source_id, run_id)
        source = await self.sources.get_source_by_id(source_id)
        supplier = (
            await self.suppliers.get_supplier(source.supplier_id)
            if source is not None
            else None
        )
        if run is None or source is None or supplier is None:
            raise ValueError("pipeline_run_not_found")
        schema = await self.schemas.active_profile(source.id)
        mapping = await self.mappings.active_profile(schema.id) if schema else None
        fields = await self.schemas.list_fields(schema.id) if schema else []
        rules = await self.mappings.list_rules(mapping.id) if mapping else []
        schedule = (
            await self.repository.schedule(source.id) if run.schedule_id else None
        )
        return PipelineContext(
            supplier=supplier,
            source=source,
            run=run,
            trigger=run.trigger_type,
            idempotency_key=run.idempotency_key,
            logger=logger,
            schedule=schedule,
            active_schema=schema,
            active_mapping=mapping,
            active_schema_fields=tuple(fields),
            active_mapping_rules=tuple(rules),
        )

    async def _compare(
        self,
        context: PipelineContext,
        analyzed: SupplierSchemaProfile,
    ) -> tuple[SupplierSchemaCompatibilityReport, str]:
        assert context.active_schema is not None
        assert context.artifact is not None
        analyzed_fields = await self.schemas.list_fields(analyzed.id)
        result = self.compatibility.compare(
            context.active_schema,
            context.active_schema_fields,
            analyzed,
            analyzed_fields,
            mapped_field_ids={
                str(rule.schema_field_id) for rule in context.active_mapping_rules
            },
            baseline_record_count=context.active_schema.baseline_record_count,
            current_record_count=context.artifact.record_count,
        )
        persistence = SupplierPipelineCompatibilityService(self.repository)
        report = await persistence.upsert(context, analyzed, result)
        await self.repository.mutate(
            context.run,
            {
                "active_schema_profile_id": context.active_schema.id,
                "analyzed_schema_profile_id": analyzed.id,
                "active_mapping_profile_id": (
                    context.active_mapping.id if context.active_mapping else None
                ),
                "current_phase": "SCHEMA_COMPARE",
                "version": context.run.version + 1,
            },
        )
        await self.session.commit()
        await self.session.refresh(report)
        return report, result.status

    async def _running(self, context: PipelineContext) -> None:
        await self.repository.mutate(
            context.run,
            {
                "status": "RUNNING",
                "started_at": datetime.now(UTC),
                "active_schema_profile_id": (
                    context.active_schema.id if context.active_schema else None
                ),
                "active_mapping_profile_id": (
                    context.active_mapping.id if context.active_mapping else None
                ),
                "version": context.run.version + 1,
            },
        )
        await self.session.commit()

    async def _phase(
        self,
        context: PipelineContext,
        phase: str,
        *,
        started_at: datetime,
        started_clock: float,
        reference_id: str | None = None,
        processed_records: int = 0,
        warning_count: int = 0,
        error_count: int = 0,
        error_code: str | None = None,
        status: str = "SUCCEEDED",
        result_code: str | None = None,
    ) -> PipelineResult:
        completed_at = datetime.now(UTC)
        phase_result = PipelinePhaseResult(
            status=status,  # type: ignore[arg-type]
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=max(0, int((time.monotonic() - started_clock) * 1000)),
            error_code=error_code,
            warning_count=warning_count,
            reference_id=reference_id,
            processed_records=processed_records,
            error_count=error_count,
            result_code=result_code,
        )
        phase_results = {
            **context.run.phase_results,
            phase: phase_result.as_dict(),
        }
        await self.repository.mutate(
            context.run,
            {
                "current_phase": phase,
                "phase_results": phase_results,
                "artifact_id": context.artifact.id if context.artifact else None,
                "version": context.run.version + 1,
            },
        )
        await self.session.commit()
        return PipelineResult(
            status="SUCCEEDED",
            completed_phase=phase,  # type: ignore[arg-type]
            references=PipelineReferences(
                artifact_id=str(context.artifact.id) if context.artifact else None
            ),
            telemetry=phase_result.as_dict(),  # type: ignore[arg-type]
        )

    async def _system_failure(
        self,
        context: PipelineContext,
        code: str,
        message: str,
        *,
        source_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
    ) -> None:
        source_id = source_id or context.source.id
        run_id = run_id or context.run.id
        await self.session.rollback()
        run = await self.repository.pipeline_run(source_id, run_id, for_update=True)
        if run is None:
            raise RuntimeError("Pipeline Run disappeared during failure handling")
        await self.repository.mutate(
            run,
            {
                "status": "FAILED",
                "phase_results": failed_phase_results(
                    run.phase_results,
                    run.current_phase,
                    code,
                ),
                "failure_code": code,
                "failure_message": message[:1000],
                "completed_at": datetime.now(UTC),
                "version": run.version + 1,
            },
        )
        if run.schedule_id is not None:
            schedule = await self.repository.schedule(source_id, for_update=True)
            if schedule is not None:
                await self.repository.update_schedule_result(
                    schedule.id,
                    status="FAILED",
                    duration_ms=0,
                    consecutive_failures=schedule.consecutive_failures + 1,
                    version=schedule.version,
                )
        await self.session.commit()
        fresh_context = await self._context(source_id, run_id)
        await SupplierPipelineIncidentService(self.session).record_failure(
            fresh_context, code, message
        )

    async def _success(
        self,
        context: PipelineContext,
        phase: str,
        references: PipelineReferences,
        started: float,
        *,
        warnings: list[str] | None = None,
    ) -> PipelineResult:
        duration = int((time.monotonic() - started) * 1000)
        await self.repository.mutate(
            context.run,
            {
                "status": "SUCCEEDED",
                "current_phase": phase,
                "completed_at": datetime.now(UTC),
                "acquisition_run_id": (
                    uuid.UUID(references.acquisition_run_id)
                    if references.acquisition_run_id
                    else None
                ),
                "version": context.run.version + 1,
            },
        )
        await self._schedule_result(context, "SUCCEEDED", duration)
        await self.session.commit()
        if context.run.automation_depth == "FULL_PIPELINE":
            await SupplierPipelineIncidentService(self.session).resolve_after_success(
                context
            )
        return PipelineResult(
            status="SUCCEEDED",
            completed_phase=phase,  # type: ignore[arg-type]
            warnings=warnings or [],
            references=references,
            telemetry={"duration_ms": duration},
        )

    async def _business_failure(
        self,
        context: PipelineContext,
        phase: str,
        code: str,
        message: str,
        references: PipelineReferences,
        started: float,
    ) -> PipelineResult:
        duration = int((time.monotonic() - started) * 1000)
        await self.repository.mutate(
            context.run,
            {
                "status": "FAILED",
                "current_phase": phase,
                "phase_results": failed_phase_results(
                    context.run.phase_results,
                    phase,
                    code,
                ),
                "failure_code": code,
                "failure_message": message[:1000],
                "completed_at": datetime.now(UTC),
                "version": context.run.version + 1,
            },
        )
        await self._schedule_result(context, "FAILED", duration)
        await self.session.commit()
        await SupplierPipelineIncidentService(self.session).record_failure(
            context, code, message
        )
        return PipelineResult(
            status="FAILED",
            completed_phase=phase,  # type: ignore[arg-type]
            errors=[message],
            references=references,
            telemetry={"duration_ms": duration, "business_failure": True},
        )

    async def _schedule_result(
        self, context: PipelineContext, status: str, duration: int
    ) -> None:
        if context.schedule is None:
            return
        failures = (
            0 if status == "SUCCEEDED" else context.schedule.consecutive_failures + 1
        )
        await self.repository.update_schedule_result(
            context.schedule.id,
            status=status,
            duration_ms=duration,
            consecutive_failures=failures,
            version=context.schedule.version,
        )


__all__ = ["SupplierPipelineOrchestratorSupport"]
