from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

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
from app.modules.suppliers.gtin_normalization import (
    GtinNormalizationStatus,
    normalize_to_ean13,
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
        fields = list(context.fields)
        rules = list(context.rules)
        ean_field_ids = {
            rule.schema_field_id
            for rule in rules
            if rule.target_attribute in {"ean", "upc", "barcode", "gtin"}
        }
        target_attributes = {rule.target_attribute for rule in rules}
        validates_identifiers = bool(
            target_attributes & {"ean", "upc", "barcode", "gtin"}
        )
        validates_price = "price" in target_attributes
        validates_name = "name" in target_attributes
        ean_rule = next(
            (rule for rule in rules if rule.is_active and rule.target_attribute == "ean"),
            None,
        )
        for number, raw in enumerate(rows, start=1):
            validation = self.validator.validate(
                raw,
                fields,
                validate_unknown_fields=False,
                strict_field_ids=ean_field_ids,
            )
            mapping = self.mapper.execute(validation.values, rules)
            problems = [*validation.problems, *mapping.problems]
            ean_problem = (
                self._ean_problem(
                    mapping.mapped,
                    schema_field_id=ean_rule.schema_field_id,
                    mapping_rule_id=ean_rule.id,
                )
                if ean_rule is not None
                else None
            )
            if ean_problem is not None:
                problems.append(ean_problem)
            identifier_problem = (
                self._identifier_problem(mapping.mapped)
                if validates_identifiers
                else None
            )
            if identifier_problem is not None:
                problems.append(identifier_problem)
            price_problem = (
                self._price_problem(mapping.mapped) if validates_price else None
            )
            if price_problem is not None:
                problems.append(price_problem)
            name_problem = (
                self._name_problem(mapping.mapped) if validates_name else None
            )
            if name_problem is not None:
                problems.append(name_problem)
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
        self._reject_duplicate_product_codes(run_id, staged, issues)
        accepted = sum(record.validation_status == "ACCEPTED" for record in staged)
        rejected = len(staged) - accepted
        warnings = sum(record.warning_count for record in staged)
        errors = sum(record.error_count for record in staged)
        return ProcessingResult(
            records=staged,
            issues=issues,
            accepted=accepted,
            rejected=rejected,
            warnings=warnings,
            errors=errors,
        )

    @staticmethod
    def _reject_duplicate_product_codes(
        run_id: uuid.UUID,
        records: list[SupplierStagedRecord],
        issues: list[SupplierAcquisitionIssue],
    ) -> None:
        grouped: dict[str, list[SupplierStagedRecord]] = {}
        for record in records:
            code = str(record.mapped_data.get("product_code") or "").strip()
            if code:
                grouped.setdefault(code.casefold(), []).append(record)
        for duplicates in grouped.values():
            if len(duplicates) < 2:
                continue
            for record in duplicates:
                record.validation_status = "REJECTED"
                record.error_count += 1
                issues.append(
                    SupplierAcquisitionIssue(
                        acquisition_run_id=run_id,
                        staged_record_id=record.id,
                        record_number=record.record_number,
                        error_code="acquisition_product_code_duplicate",
                        severity="ERROR",
                        message=(
                            "Šifra artikla dobavljača ponovljena je više puta u "
                            "istom cenovniku; svi redovi sa tom šifrom su blokirani"
                        ),
                        technical_context=None,
                    )
                )

    @staticmethod
    def _ean_problem(
        mapped: dict[str, object],
        *,
        schema_field_id: uuid.UUID | None = None,
        mapping_rule_id: uuid.UUID | None = None,
    ) -> RowProblem | None:
        result = normalize_to_ean13(mapped.get("ean"))
        mapped["ean"] = result.value
        if result.status in {
            GtinNormalizationStatus.EAN13_VALID,
            GtinNormalizationStatus.UPC_A_CONVERTED_TO_EAN13,
        }:
            return None
        return RowProblem(
            code=f"acquisition_ean_{result.status.value.lower()}",
            message=result.message,
            schema_field_id=schema_field_id,
            mapping_rule_id=mapping_rule_id,
        )

    @staticmethod
    def _identifier_problem(
        mapped: dict[str, object],
    ) -> RowProblem | None:
        product_code = str(mapped.get("product_code") or "").strip()
        ean = str(mapped.get("ean") or "").strip()
        if product_code and ean:
            return None
        if not product_code and not ean:
            message = "Artikal mora imati šifru proizvoda i EAN kod"
        elif not product_code:
            message = "Artiklu nedostaje obavezna šifra proizvoda"
        else:
            message = "Artiklu nedostaje obavezan EAN kod"
        return RowProblem(
            code="acquisition_product_identifier_missing",
            message=message,
        )

    @staticmethod
    def _price_problem(mapped: dict[str, object]) -> RowProblem | None:
        value = mapped.get("price")
        try:
            valid = value is not None and Decimal(str(value)) > 0
        except InvalidOperation:
            valid = False
        if valid:
            return None
        return RowProblem(
            code="acquisition_product_price_invalid",
            message="Artikal mora imati cenu veću od nule",
        )

    @staticmethod
    def _name_problem(mapped: dict[str, object]) -> RowProblem | None:
        if str(mapped.get("name") or "").strip():
            return None
        return RowProblem(
            code="acquisition_product_name_missing",
            message="Artiklu nedostaje obavezan naziv proizvoda",
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
