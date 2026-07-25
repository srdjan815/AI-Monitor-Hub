from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.modules.suppliers.acquisition_context import AcquisitionContext
from app.modules.suppliers.acquisition_models import (
    SupplierAcquisitionIssue,
    SupplierStagedRecord,
)
from app.modules.suppliers.acquisition_transformations import MappingExecutor
from app.modules.suppliers.acquisition_validation import (
    RowProblem,
    SchemaRecordValidator,
)


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    records: list[SupplierStagedRecord]
    issues: list[SupplierAcquisitionIssue]
    accepted: int
    rejected: int
    warnings: int
    errors: int


class AcquisitionProcessor:
    def __init__(self) -> None:
        self.validator = SchemaRecordValidator()
        self.mapper = MappingExecutor()

    def process(
        self,
        run_id: uuid.UUID,
        rows: list[dict[str, object]],
        context: AcquisitionContext,
    ) -> ProcessingResult:
        staged: list[SupplierStagedRecord] = []
        issues: list[SupplierAcquisitionIssue] = []
        accepted = rejected = warnings = errors = 0
        for number, raw in enumerate(rows, start=1):
            validation = self.validator.validate(raw, context.fields)
            mapping = self.mapper.execute(validation.values, context.rules)
            problems = [*validation.problems, *mapping.problems]
            row_errors = sum(problem.severity == "ERROR" for problem in problems)
            row_warnings = len(problems) - row_errors
            status = "REJECTED" if row_errors else "ACCEPTED"
            record_id = uuid.uuid4()
            record = SupplierStagedRecord(
                id=record_id,
                acquisition_run_id=run_id,
                record_number=number,
                source_key=validation.source_key,
                source_identifier=validation.source_identifier,
                raw_data=raw,
                mapped_data=mapping.mapped,
                validation_status=status,
                warning_count=row_warnings,
                error_count=row_errors,
            )
            staged.append(record)
            issues.extend(self._issues(run_id, record_id, number, problems))
            accepted += status == "ACCEPTED"
            rejected += status == "REJECTED"
            warnings += row_warnings
            errors += row_errors
        return ProcessingResult(
            records=staged,
            issues=issues,
            accepted=accepted,
            rejected=rejected,
            warnings=warnings,
            errors=errors,
        )

    @staticmethod
    def _issues(
        run_id: uuid.UUID,
        record_id: uuid.UUID,
        number: int,
        problems: list[RowProblem],
    ) -> list[SupplierAcquisitionIssue]:
        return [
            SupplierAcquisitionIssue(
                acquisition_run_id=run_id,
                staged_record_id=record_id,
                record_number=number,
                schema_field_id=problem.schema_field_id,
                mapping_rule_id=problem.mapping_rule_id,
                error_code=problem.code,
                severity=problem.severity,
                message=problem.message[:1000],
                technical_context=None,
            )
            for problem in problems
        ]


__all__ = ["AcquisitionProcessor", "ProcessingResult"]
