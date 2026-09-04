from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.acquisition_context import AcquisitionContext
from app.modules.suppliers.acquisition_contracts import AcquisitionFailure
from app.modules.suppliers.acquisition_service import SupplierAcquisitionService
from app.modules.suppliers.currency_automation_service import (
    CurrencyPreflightError,
)
from app.modules.suppliers.pipeline_currency_phase import run_currency_phase
from app.modules.suppliers.delta_service import SupplierDeltaService
from app.modules.suppliers.pipeline_contracts import (
    PipelineContext,
    PipelineReferences,
    PipelineResult,
)
from app.modules.suppliers.schema_profile_models import SupplierSchemaProfile
from app.modules.suppliers.pipeline_orchestrator_support import (
    SupplierPipelineOrchestratorSupport,
)
from app.modules.suppliers.pipeline_run_service import SupplierPipelineRunService
from app.modules.suppliers.schema_profile_schemas import SchemaProfileCreate
from app.modules.suppliers.schema_profile_schemas import SchemaProfileAction
from app.modules.suppliers.snapshot_service import SupplierSnapshotService


class SupplierPipelineOrchestrator(SupplierPipelineOrchestratorSupport):
    """The only component that owns Supplier Pipeline phase ordering."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def execute(
        self,
        source_id: uuid.UUID,
        run_id: uuid.UUID,
        *,
        schema_create: SchemaProfileCreate | None = None,
        reanalyze_profile_id: uuid.UUID | None = None,
        reanalyze_action: SchemaProfileAction | None = None,
    ) -> PipelineResult:
        started = time.monotonic()
        context = await self._context(source_id, run_id)
        context_source_id = context.source.id
        context_run_id = context.run.id
        context.logger.info(
            "Supplier Pipeline started source_id=%s run_id=%s depth=%s",
            context_source_id,
            context_run_id,
            context.run.automation_depth,
        )
        await self._running(context)
        references = PipelineReferences()
        try:
            await run_currency_phase(self, context)
            phase_started, phase_clock = datetime.now(UTC), time.monotonic()
            payload = await self.adapters.resolve(context.source.source_type).acquire(
                context.source
            )
            await self._phase(
                context,
                "FETCH",
                started_at=phase_started,
                started_clock=phase_clock,
                processed_records=0,
            )
            phase_started, phase_clock = datetime.now(UTC), time.monotonic()
            artifact = await self.artifacts.store(context.source.id, payload)
            context = context.with_artifact(artifact)
            references.artifact_id = str(artifact.id)
            await self._phase(
                context,
                "ARTIFACT_SAVE",
                started_at=phase_started,
                started_clock=phase_clock,
                reference_id=str(artifact.id),
                processed_records=artifact.record_count or 0,
            )
            phase_started, phase_clock = datetime.now(UTC), time.monotonic()
            await self._phase(
                context,
                "TECHNICAL_VALIDATE",
                started_at=phase_started,
                started_clock=phase_clock,
                reference_id=str(artifact.id),
                processed_records=artifact.record_count or 0,
            )
            if context.run.automation_depth == "FETCH_ONLY":
                return await self._success(
                    context, "TECHNICAL_VALIDATE", references, started
                )
            analyzed = await self._analyze(
                context,
                references,
                schema_create=schema_create,
                reanalyze_profile_id=reanalyze_profile_id,
                reanalyze_action=reanalyze_action,
            )
            if context.run.automation_depth == "FETCH_AND_ANALYZE":
                return await self._success(
                    context, "SCHEMA_ANALYZE", references, started
                )
            if context.active_schema is None or context.active_mapping is None:
                return await self._business_failure(
                    context,
                    "SCHEMA_COMPARE",
                    "pipeline_active_contract_missing",
                    "FULL_PIPELINE zahteva ACTIVE Schema i ACTIVE Mapping.",
                    references,
                    started,
                )
            phase_started, phase_clock = datetime.now(UTC), time.monotonic()
            report, status = await self._compare(context, analyzed)
            references.compatibility_report_id = str(report.id)
            await self._phase(
                context,
                "SCHEMA_COMPARE",
                started_at=phase_started,
                started_clock=phase_clock,
                reference_id=str(report.id),
                processed_records=artifact.record_count or 0,
                warning_count=(1 if status == "COMPATIBLE_WITH_WARNINGS" else 0),
                error_count=(1 if status == "INCOMPATIBLE" else 0),
                error_code=(
                    "pipeline_schema_incompatible" if status == "INCOMPATIBLE" else None
                ),
                status=("FAILED" if status == "INCOMPATIBLE" else "SUCCEEDED"),
            )
            if status == "INCOMPATIBLE":
                return await self._business_failure(
                    context,
                    "SCHEMA_COMPARE",
                    "pipeline_schema_incompatible",
                    "Artifact nije kompatibilan sa ACTIVE Schema ugovorom.",
                    references,
                    started,
                )
            return await self._complete_full_pipeline(context, references, started)
        except CurrencyPreflightError as exc:
            return await self._business_failure(
                context,
                "CURRENCY_RATE",
                exc.code,
                exc.safe_message,
                references,
                started,
            )
        except AcquisitionFailure as exc:
            if exc.code == "acquisition_http_failed":
                await self._system_failure(
                    context,
                    exc.code,
                    exc.safe_message,
                    source_id=context_source_id,
                    run_id=context_run_id,
                )
                raise
            return await self._business_failure(
                context,
                context.run.current_phase,
                exc.code,
                exc.safe_message,
                references,
                started,
            )
        except Exception:
            await self._system_failure(
                context,
                "pipeline_system_failure",
                "Neočekivana sistemska greška Supplier Pipeline-a.",
                source_id=context_source_id,
                run_id=context_run_id,
            )
            context.logger.exception(
                "Supplier Pipeline system failure source_id=%s run_id=%s",
                context_source_id,
                context_run_id,
            )
            raise

    async def _analyze(
        self,
        context: PipelineContext,
        references: PipelineReferences,
        *,
        schema_create: SchemaProfileCreate | None,
        reanalyze_profile_id: uuid.UUID | None,
        reanalyze_action: SchemaProfileAction | None,
    ) -> SupplierSchemaProfile:
        assert context.artifact is not None
        phase_started, phase_clock = datetime.now(UTC), time.monotonic()
        artifact_payload = self.artifacts.load(context.artifact)
        if reanalyze_profile_id is not None:
            if reanalyze_action is None:
                raise ValueError("pipeline_reanalyze_action_required")
            inferred = await self.inference.reanalyze(
                context.source.id,
                reanalyze_profile_id,
                context.artifact,
                artifact_payload,
                reanalyze_action,
            )
        else:
            inferred = await self.inference.create_from_artifact(
                context.source.id,
                context.artifact,
                artifact_payload,
                schema_create
                or SchemaProfileCreate(
                    name=f"Automatska analiza {context.run.pipeline_code}",
                    description="DRAFT predlog kreiran iz Pipeline Artifact-a.",
                ),
            )
        analyzed = await self.schemas.get_profile(
            context.source.id, inferred.profile.id
        )
        if analyzed is None:
            raise RuntimeError("Inferred Schema disappeared")
        references.analyzed_schema_id = str(analyzed.id)
        await self._phase(
            context,
            "SCHEMA_ANALYZE",
            started_at=phase_started,
            started_clock=phase_clock,
            reference_id=str(analyzed.id),
            processed_records=context.artifact.record_count or 0,
        )
        return analyzed

    async def _complete_full_pipeline(
        self,
        context: PipelineContext,
        references: PipelineReferences,
        started: float,
    ) -> PipelineResult:
        assert context.active_schema is not None
        assert context.active_mapping is not None
        assert context.artifact is not None
        phase_started, phase_clock = datetime.now(UTC), time.monotonic()
        acquisition = await SupplierAcquisitionService(
            self.session
        ).execute_artifact_context(
            AcquisitionContext(
                supplier=context.supplier,
                source=context.source,
                schema=context.active_schema,
                fields=context.active_schema_fields,
                mapping=context.active_mapping,
                rules=context.active_mapping_rules,
            ),
            self.artifacts.load(context.artifact),
            idempotency_key=f"{context.idempotency_key}:acquisition",
        )
        references.acquisition_run_id = str(acquisition.id)
        await self._phase(
            context,
            "BUSINESS_VALIDATE",
            started_at=phase_started,
            started_clock=phase_clock,
            reference_id=str(acquisition.id),
            processed_records=acquisition.total_record_count,
            warning_count=acquisition.warning_count,
            error_count=acquisition.rejected_record_count,
            error_code=acquisition.failure_code,
            status=(
                "SUCCEEDED"
                if acquisition.status in {"SUCCEEDED", "PARTIALLY_SUCCEEDED"}
                else "FAILED"
            ),
        )
        if acquisition.status not in {"SUCCEEDED", "PARTIALLY_SUCCEEDED"}:
            return await self._business_failure(
                context,
                "BUSINESS_VALIDATE",
                acquisition.failure_code or "pipeline_acquisition_failed",
                acquisition.failure_message or "Acquisition nije uspeo.",
                references,
                started,
            )
        phase_started, phase_clock = datetime.now(UTC), time.monotonic()
        snapshot = await SupplierSnapshotService(self.session).create(
            context.source.supplier_id,
            context.source.id,
            acquisition.id,
            retention_class="STANDARD",
            archive_after_days=None,
            preserve_online=False,
            legal_hold=False,
            archive_notes=None,
            pipeline_run_id=context.run.id,
        )
        references.snapshot_id = str(snapshot.id)
        await self._phase(
            context,
            "SNAPSHOT",
            started_at=phase_started,
            started_clock=phase_clock,
            reference_id=str(snapshot.id),
            processed_records=snapshot.total_items,
        )
        warnings: list[str] = []
        phase_started, phase_clock = datetime.now(UTC), time.monotonic()
        try:
            delta = await SupplierDeltaService(self.session).calculate_previous(
                context.source.supplier_id,
                context.source.id,
                snapshot.id,
                f"{context.idempotency_key}:delta",
            )
            references.delta_run_id = str(delta.id)
            await self._phase(
                context,
                "DELTA",
                started_at=phase_started,
                started_clock=phase_clock,
                reference_id=str(delta.id),
                processed_records=delta.total_current_items,
                warning_count=delta.warning_count,
                error_count=delta.error_count,
            )
            phase = "DELTA"
        except Exception as exc:
            if "delta_previous_snapshot_not_found" not in str(exc):
                raise
            warnings.append("Prvi Snapshot nema prethodni Snapshot za Delta.")
            await self._phase(
                context,
                "DELTA",
                started_at=phase_started,
                started_clock=phase_clock,
                warning_count=1,
                status="SKIPPED",
            )
            phase = "SNAPSHOT"
        return await self._success(
            context,
            phase,
            references,
            started,
            warnings=warnings,
        )


__all__ = ["SupplierPipelineOrchestrator", "SupplierPipelineRunService"]
