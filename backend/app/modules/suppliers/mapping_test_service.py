from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.acquisition_transformations import MappingExecutor
from app.modules.suppliers.acquisition_validation import SchemaRecordValidator
from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.mapping_profile_repository import SupplierMappingRepository
from app.modules.suppliers.mapping_test_schemas import (
    MappingTestCell,
    MappingTestRead,
    MappingTestRow,
)
from app.modules.suppliers.pipeline_repository import SupplierPipelineRepository
from app.modules.suppliers.schema_inference_engine import SchemaStructureDetector
from app.modules.suppliers.schema_profile_repository import SupplierSchemaRepository
from app.modules.suppliers.source_artifact_service import SupplierSourceArtifactService


class SupplierMappingTestService:
    """Read-only mapping preview over the Schema baseline Artifact."""

    def __init__(self, session: AsyncSession) -> None:
        self.schemas = SupplierSchemaRepository(session)
        self.mappings = SupplierMappingRepository(session)
        self.pipeline = SupplierPipelineRepository(session)
        self.artifacts = SupplierSourceArtifactService(session)
        self.validator = SchemaRecordValidator()
        self.executor = MappingExecutor()

    async def test(
        self,
        source_id: uuid.UUID,
        schema_id: uuid.UUID,
        mapping_id: uuid.UUID,
        *,
        record_number: int | None = None,
    ) -> MappingTestRead:
        schema = await self.schemas.get_profile(source_id, schema_id)
        mapping = await self.mappings.get_profile(schema_id, mapping_id)
        if schema is None or mapping is None:
            supplier_error(404, "mapping_profile_not_found", "Mapiranje nije pronađeno")
        if schema.baseline_artifact_id is None:
            supplier_error(
                409,
                "mapping_test_artifact_missing",
                "Schema nema sačuvan cenovnik za test mapiranja.",
            )
        artifact = await self.pipeline.artifact(
            source_id, schema.baseline_artifact_id
        )
        if artifact is None:
            supplier_error(
                409,
                "mapping_test_artifact_missing",
                "Sačuvani cenovnik više nije dostupan.",
            )
        fields = await self.schemas.list_fields(schema.id)
        rules = await self.mappings.list_rules(mapping.id)
        if not rules:
            supplier_error(
                409,
                "mapping_profile_empty",
                "Dodajte bar jedno mapiranje pre testa.",
            )
        mapped_field_ids = {rule.schema_field_id for rule in rules}
        for rule in rules:
            configured_ids = (getattr(rule, "transformation_config", None) or {}).get(
                "field_ids", []
            )
            if isinstance(configured_ids, list):
                for field_id in configured_ids:
                    try:
                        mapped_field_ids.add(uuid.UUID(str(field_id)))
                    except (TypeError, ValueError):
                        continue
        mapped_fields = [field for field in fields if field.id in mapped_field_ids]
        structure = SchemaStructureDetector.detect(
            self.artifacts.load(artifact), row_limit=None
        )
        rows: list[MappingTestRow] = []
        warnings = errors = 0
        fields_by_id = {field.id: field for field in fields}
        if record_number is not None and record_number > len(structure.rows):
            supplier_error(
                404,
                "mapping_test_record_not_found",
                "Izabrani artikal nije pronađen u cenovniku.",
            )
        selected_rows = (
            [(record_number, structure.rows[record_number - 1])]
            if record_number is not None
            else list(enumerate(structure.rows[:10], 1))
        )
        for number, raw in selected_rows:
            validated = self.validator.validate(
                raw,
                mapped_fields,
                validate_unknown_fields=False,
            )
            mapped = self.executor.execute(validated.values, rules)
            problems = [*validated.problems, *mapped.problems]
            row_errors = sum(item.severity == "ERROR" for item in problems)
            row_warnings = len(problems) - row_errors
            warnings += row_warnings
            errors += row_errors
            cells: list[MappingTestCell] = []
            for rule in sorted(rules, key=lambda item: item.priority):
                field = fields_by_id.get(rule.schema_field_id)
                original = validated.values.get(rule.schema_field_id)
                problem = next(
                    (
                        item
                        for item in problems
                        if item.mapping_rule_id == rule.id
                        or item.schema_field_id == rule.schema_field_id
                    ),
                    None,
                )
                transformed = mapped.mapped.get(rule.target_attribute)
                cells.append(
                    MappingTestCell(
                        source_field=field.name if field else "Nepoznato polje",
                        original_value=None if original is None else str(original),
                        target_attribute=rule.target_attribute,
                        transformed_value=(
                            None if transformed is None else str(transformed)
                        ),
                        status="GREŠKA" if problem else "ISPRAVNO",
                        error=problem.message if problem else None,
                    )
                )
            rows.append(
                MappingTestRow(
                    row_number=number,
                    status=(
                        "GREŠKA"
                        if row_errors
                        else "UPOZORENJE" if row_warnings else "ISPRAVNO"
                    ),
                    cells=cells,
                )
            )
        return MappingTestRead(
            successful=errors == 0,
            tested_records=len(rows),
            warning_count=warnings,
            error_count=errors,
            rows=rows,
            message=(
                "Test mapiranja je uspešan."
                if errors == 0
                else "Mapiranje sadrži greške. Proverite označena polja."
            ),
        )


__all__ = ["SupplierMappingTestService"]
