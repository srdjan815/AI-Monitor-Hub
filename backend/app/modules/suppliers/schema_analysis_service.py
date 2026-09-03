from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.pipeline_service import SupplierPipelineOrchestrator
from app.modules.suppliers.pipeline_run_service import SupplierPipelineRunService
from app.modules.suppliers.schema_field_schemas import SchemaFieldRead
from app.modules.suppliers.schema_inference_schemas import (
    InferredSchemaFieldRead,
    SchemaInferenceRead,
)
from app.modules.suppliers.schema_profile_models import (
    SupplierSchemaField,
    SupplierSchemaProfile,
)
from app.modules.suppliers.schema_profile_repository import SupplierSchemaRepository
from app.modules.suppliers.schema_profile_schemas import (
    SchemaProfileAction,
    SchemaProfileCreate,
    SchemaProfileRead,
)
from app.modules.suppliers.source_repository import SupplierSourceRepository


class SupplierSchemaAnalysisService:
    """API-facing command service; phase ordering remains in the Orchestrator."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.runs = SupplierPipelineRunService(session)
        self.orchestrator = SupplierPipelineOrchestrator(session)
        self.schemas = SupplierSchemaRepository(session)
        self.sources = SupplierSourceRepository(session)

    async def analyze(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        data: SchemaProfileCreate,
    ) -> SchemaInferenceRead:
        return await self._execute(
            supplier_id, source_id, schema_create=data
        )

    async def reanalyze(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        profile_id: uuid.UUID,
        data: SchemaProfileAction,
    ) -> SchemaInferenceRead:
        return await self._execute(
            supplier_id,
            source_id,
            reanalyze_profile_id=profile_id,
            reanalyze_action=data,
        )

    async def _execute(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        *,
        schema_create: SchemaProfileCreate | None = None,
        reanalyze_profile_id: uuid.UUID | None = None,
        reanalyze_action: SchemaProfileAction | None = None,
    ) -> SchemaInferenceRead:
        source = await self.sources.get_source(supplier_id, source_id)
        if source is None:
            supplier_error(404, "supplier_source_not_found", "Izvor nije pronađen")
        if not source.is_active or source.status != "ACTIVE":
            supplier_error(
                409,
                "schema_analysis_source_not_active",
                "Konekcija mora prvo biti uspešno testirana i aktivirana.",
            )
        key = f"schema-analysis:{source_id}:{uuid.uuid4()}"
        run = await self.runs.create(
            source_id,
            trigger="MANUAL",
            automation_depth="FETCH_AND_ANALYZE",
            idempotency_key=key,
        )
        result = await self.orchestrator.execute(
            source_id,
            run.id,
            schema_create=schema_create,
            reanalyze_profile_id=reanalyze_profile_id,
            reanalyze_action=reanalyze_action,
        )
        if not result.successful or result.references.analyzed_schema_id is None:
            supplier_error(
                422,
                run.failure_code or "schema_analysis_failed",
                run.failure_message or "Cenovnik nije moguće analizirati.",
            )
        profile_id = uuid.UUID(result.references.analyzed_schema_id)
        profile = await self.schemas.get_profile(source_id, profile_id)
        if profile is None:
            raise RuntimeError("Analyzed Schema Profile disappeared")
        fields = await self.schemas.list_fields(profile.id)
        return self._response(profile, fields)

    @staticmethod
    def _response(
        profile: SupplierSchemaProfile,
        fields: list[SupplierSchemaField],
    ) -> SchemaInferenceRead:
        metadata = profile.analysis_metadata or {}
        header_row_value = metadata.get("header_row")
        sampled_value = metadata.get("sampled_record_count")
        details = metadata.get("fields")
        field_details = details if isinstance(details, dict) else {}
        inferred: list[InferredSchemaFieldRead] = []
        for field in fields:
            detail = field_details.get(field.field_code, {})
            if not isinstance(detail, dict):
                detail = {}
            samples = detail.get("sample_values", [])
            confidence = detail.get("confidence", 0.0)
            inferred.append(
                InferredSchemaFieldRead(
                    field=SchemaFieldRead.model_validate(field),
                    sample_values=(
                        [str(value) for value in samples[:10]]
                        if isinstance(samples, list)
                        else []
                    ),
                    confidence=(
                        float(confidence)
                        if isinstance(confidence, (int, float))
                        else 0.0
                    ),
                )
            )
        return SchemaInferenceRead(
            profile=SchemaProfileRead.model_validate(profile),
            original_filename=(
                str(metadata.get("original_filename"))
                if metadata.get("original_filename")
                else None
            ),
            detected_format=profile.detected_format or "UNKNOWN",
            encoding=profile.encoding,
            delimiter=profile.delimiter,
            header_row=(
                header_row_value if isinstance(header_row_value, int) else None
            ),
            root_path=profile.root_path,
            item_path=profile.record_path,
            record_count=profile.baseline_record_count or 0,
            sampled_record_count=(
                sampled_value
                if isinstance(sampled_value, int)
                else 0
            ),
            fields=inferred,
        )


__all__ = ["SupplierSchemaAnalysisService"]
