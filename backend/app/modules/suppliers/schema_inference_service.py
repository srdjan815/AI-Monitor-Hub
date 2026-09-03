from __future__ import annotations

import logging
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.acquisition_contracts import (
    AcquiredPayload,
    AcquisitionFailure,
)
from app.modules.suppliers.schema_inference_engine import (
    DetectedStructure,
    SchemaStructureDetector,
)
from app.modules.suppliers.schema_inference_schemas import (
    InferredSchemaFieldRead,
    SchemaInferenceRead,
)
from app.modules.suppliers.schema_field_schemas import SchemaFieldRead
from app.modules.suppliers.schema_profile_models import SupplierSchemaProfile
from app.modules.suppliers.schema_profile_schemas import (
    SchemaProfileAction,
    SchemaProfileCreate,
    SchemaProfileRead,
)
from app.modules.suppliers.schema_service_support import SupplierSchemaServiceSupport
from app.modules.suppliers.schema_type_inference import (
    InferredField,
    SchemaFieldInferer,
)
from app.modules.suppliers.pipeline_models import SupplierSourceArtifact

logger = logging.getLogger(__name__)


class SupplierSchemaInferenceService(SupplierSchemaServiceSupport):
    """Acquire and infer source structure without starting Acquisition."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
    async def create_from_artifact(
        self,
        source_id: uuid.UUID,
        artifact: SupplierSourceArtifact,
        payload: AcquiredPayload,
        data: SchemaProfileCreate,
    ) -> SchemaInferenceRead:
        structure = SchemaStructureDetector.detect(payload)
        name = self._name(data.name)
        profile = SupplierSchemaProfile(
            source_connection_id=source_id,
            name=name,
            description=self._optional(data.description),
            version_number=await self.repository.next_version_number(source_id, name),
            status="DRAFT",
            is_active=True,
            field_count=0,
            detected_format=structure.detected_format,
            encoding=structure.encoding,
            delimiter=structure.delimiter,
            root_path=structure.root_path,
            record_path=structure.item_path,
            baseline_artifact_id=artifact.id,
            baseline_checksum=artifact.checksum_sha256,
            baseline_record_count=artifact.record_count,
            compatibility_policy={},
            analysis_metadata=self._analysis_metadata(
                structure, inferred=[], original_filename=artifact.original_filename
            ),
            last_analyzed_at=artifact.created_at,
        )
        inferred = SchemaFieldInferer.fields(profile.id, structure.rows)
        self._ensure_fields(source_id, inferred)
        profile.analysis_metadata = self._analysis_metadata(
            structure, inferred, original_filename=artifact.original_filename
        )
        try:
            await self.repository.add(profile)
            for item in inferred:
                item.entity.schema_profile_id = profile.id
                await self.repository.add(item.entity)
            await self.repository.mutate(
                profile,
                {"field_count": len(inferred), "version": profile.version + 1},
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            self._integrity(exc)
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(profile)
        return self._response(profile, structure, inferred)

    async def reanalyze(
        self,
        source_id: uuid.UUID,
        profile_id: uuid.UUID,
        artifact: SupplierSourceArtifact,
        payload: AcquiredPayload,
        data: SchemaProfileAction,
    ) -> SchemaInferenceRead:
        structure = SchemaStructureDetector.detect(payload)
        profile = await self._profile(source_id, profile_id, for_update=True)
        self._draft(profile)
        self._version(profile.version, data.version)
        inferred = SchemaFieldInferer.fields(profile.id, structure.rows)
        self._ensure_fields(source_id, inferred)
        try:
            await self.repository.deactivate_fields(profile.id)
            for item in inferred:
                await self.repository.add(item.entity)
            await self.repository.mutate(
                profile,
                {
                    "field_count": len(inferred),
                    "detected_format": structure.detected_format,
                    "encoding": structure.encoding,
                    "delimiter": structure.delimiter,
                    "root_path": structure.root_path,
                    "record_path": structure.item_path,
                    "baseline_artifact_id": artifact.id,
                    "baseline_checksum": artifact.checksum_sha256,
                    "baseline_record_count": artifact.record_count,
                    "analysis_metadata": self._analysis_metadata(
                        structure,
                        inferred,
                        original_filename=artifact.original_filename,
                    ),
                    "last_analyzed_at": artifact.created_at,
                    "version": profile.version + 1,
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            self._integrity(exc)
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(profile)
        return self._response(profile, structure, inferred)

    @staticmethod
    def _analysis_metadata(
        structure: DetectedStructure,
        inferred: list[InferredField],
        *,
        original_filename: str | None,
    ) -> dict[str, object]:
        return {
            "header_row": structure.header_row,
            "sampled_record_count": len(structure.rows),
            "original_filename": original_filename,
            "fields": {
                item.entity.field_code: {
                    "sample_values": item.sample_values,
                    "confidence": item.confidence,
                }
                for item in inferred
            },
        }

    @staticmethod
    def _ensure_fields(
        source_id: uuid.UUID,
        inferred: list[InferredField],
    ) -> None:
        if inferred:
            return
        logger.warning(
            "Schema inference failed source_id=%s reason=no_fields",
            source_id,
        )
        raise AcquisitionFailure(
            "schema_inference_failed",
            "Izvor ne sadrži polja koja se mogu analizirati",
        )

    @staticmethod
    def _response(
        profile: SupplierSchemaProfile,
        structure: DetectedStructure,
        inferred: list[InferredField],
    ) -> SchemaInferenceRead:
        return SchemaInferenceRead(
            profile=SchemaProfileRead.model_validate(profile),
            original_filename=(
                str(profile.analysis_metadata.get("original_filename"))
                if profile.analysis_metadata.get("original_filename")
                else None
            ),
            detected_format=structure.detected_format,
            encoding=structure.encoding,
            delimiter=structure.delimiter,
            header_row=structure.header_row,
            root_path=structure.root_path,
            item_path=structure.item_path,
            record_count=profile.baseline_record_count or 0,
            sampled_record_count=len(structure.rows),
            fields=[
                InferredSchemaFieldRead(
                    field=SchemaFieldRead.model_validate(item.entity),
                    sample_values=item.sample_values,
                    confidence=item.confidence,
                )
                for item in inferred
            ],
        )


__all__ = ["SupplierSchemaInferenceService"]
