from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from collections.abc import Sequence
from typing import Literal

from app.modules.suppliers.schema_profile_models import (
    SupplierSchemaField,
    SupplierSchemaProfile,
)

CompatibilityStatus = Literal[
    "COMPATIBLE",
    "COMPATIBLE_WITH_WARNINGS",
    "INCOMPATIBLE",
]
CompatibilitySeverity = Literal["INFO", "WARNING", "ERROR", "CRITICAL"]


@dataclass(frozen=True, slots=True)
class CompatibilityChange:
    code: str
    path: str | None
    classification: CompatibilityStatus
    severity: CompatibilitySeverity
    expected: object | None
    actual: object | None
    message: str


@dataclass(frozen=True, slots=True)
class CompatibilityResult:
    status: CompatibilityStatus
    severity: CompatibilitySeverity
    changes: list[CompatibilityChange] = dataclass_field(default_factory=list)
    warnings: list[str] = dataclass_field(default_factory=list)
    summary: dict[str, int | float | str | bool | None] = dataclass_field(
        default_factory=dict
    )


class SupplierSchemaCompatibilityService:
    def compare(
        self,
        active: SupplierSchemaProfile,
        active_fields: Sequence[SupplierSchemaField],
        analyzed: SupplierSchemaProfile,
        analyzed_fields: Sequence[SupplierSchemaField],
        *,
        mapped_field_ids: set[str],
        baseline_record_count: int | None,
        current_record_count: int | None,
    ) -> CompatibilityResult:
        changes: list[CompatibilityChange] = []
        self._structure(active, analyzed, changes)
        expected = {field.path: field for field in active_fields if field.is_active}
        actual = {field.path: field for field in analyzed_fields if field.is_active}
        for path, field in expected.items():
            candidate = actual.get(path)
            if candidate is None:
                classification: CompatibilityStatus = (
                    "INCOMPATIBLE"
                    if field.required or str(field.id) in mapped_field_ids
                    else "COMPATIBLE_WITH_WARNINGS"
                )
                changes.append(
                    CompatibilityChange(
                        code="FIELD_MISSING",
                        path=path,
                        classification=classification,
                        severity="ERROR" if classification == "INCOMPATIBLE" else "WARNING",
                        expected=field.data_type,
                        actual=None,
                        message="Očekivano polje više ne postoji.",
                    )
                )
            elif candidate.data_type != field.data_type:
                changes.append(
                    CompatibilityChange(
                        code="FIELD_TYPE_CHANGED",
                        path=path,
                        classification="INCOMPATIBLE",
                        severity="ERROR",
                        expected=field.data_type,
                        actual=candidate.data_type,
                        message="Tip postojećeg polja je promenjen.",
                    )
                )
            elif field.required and candidate.nullable:
                changes.append(
                    CompatibilityChange(
                        code="REQUIRED_FIELD_NULLABLE",
                        path=path,
                        classification="INCOMPATIBLE",
                        severity="ERROR",
                        expected=False,
                        actual=True,
                        message="Obavezno polje je postalo nullable.",
                    )
                )
        self._new_fields(expected, actual, mapped_field_ids, changes)
        self._record_count(
            active,
            baseline_record_count,
            current_record_count,
            changes,
        )
        status = self._status(changes)
        severity = self._severity(changes)
        return CompatibilityResult(
            status=status,
            severity=severity,
            changes=changes,
            warnings=[
                change.message
                for change in changes
                if change.severity == "WARNING"
            ],
            summary={
                "expected_field_count": len(expected),
                "actual_field_count": len(actual),
                "change_count": len(changes),
                "baseline_record_count": baseline_record_count,
                "current_record_count": current_record_count,
            },
        )

    @staticmethod
    def _structure(
        active: SupplierSchemaProfile,
        analyzed: SupplierSchemaProfile,
        changes: list[CompatibilityChange],
    ) -> None:
        for code, path, expected, actual in (
            ("FORMAT_CHANGED", None, active.detected_format, analyzed.detected_format),
            ("ROOT_PATH_CHANGED", active.root_path, active.root_path, analyzed.root_path),
            ("RECORD_PATH_CHANGED", active.record_path, active.record_path, analyzed.record_path),
            ("DELIMITER_CHANGED", None, active.delimiter, analyzed.delimiter),
        ):
            if expected is not None and expected != actual:
                changes.append(
                    CompatibilityChange(
                        code=code,
                        path=path,
                        classification="INCOMPATIBLE",
                        severity="ERROR",
                        expected=expected,
                        actual=actual,
                        message="Tehnička struktura izvora je promenjena.",
                    )
                )

    @staticmethod
    def _new_fields(
        expected: dict[str, SupplierSchemaField],
        actual: dict[str, SupplierSchemaField],
        mapped_field_ids: set[str],
        changes: list[CompatibilityChange],
    ) -> None:
        del mapped_field_ids
        normalized = {field.field_code.lower() for field in expected.values()}
        for path, field in actual.items():
            if path in expected:
                continue
            collision = field.field_code.lower() in normalized
            changes.append(
                CompatibilityChange(
                    code="FIELD_NORMALIZATION_COLLISION" if collision else "OPTIONAL_FIELD_ADDED",
                    path=path,
                    classification="INCOMPATIBLE" if collision else "COMPATIBLE_WITH_WARNINGS",
                    severity="ERROR" if collision else "WARNING",
                    expected=None,
                    actual=field.data_type,
                    message=(
                        "Novo polje kolidira sa postojećim normalizovanim nazivom."
                        if collision
                        else "Dodato je novo opciono polje."
                    ),
                )
            )

    @staticmethod
    def _record_count(
        active: SupplierSchemaProfile,
        baseline: int | None,
        current: int | None,
        changes: list[CompatibilityChange],
    ) -> None:
        policy = active.compatibility_policy
        minimum = policy.get("minimum_record_count")
        maximum_drop = policy.get("maximum_drop_percentage")
        if current is None:
            return
        if isinstance(minimum, int) and current < minimum:
            changes.append(
                CompatibilityChange(
                    code="RECORD_COUNT_BELOW_POLICY",
                    path=None,
                    classification="INCOMPATIBLE",
                    severity="ERROR",
                    expected=minimum,
                    actual=current,
                    message="Broj zapisa je ispod odobrenog minimuma.",
                )
            )
        if (
            baseline
            and isinstance(maximum_drop, (int, float))
            and baseline > 0
            and (baseline - current) / baseline * 100 > maximum_drop
        ):
            changes.append(
                CompatibilityChange(
                    code="RECORD_COUNT_DROP",
                    path=None,
                    classification="INCOMPATIBLE",
                    severity="ERROR",
                    expected=maximum_drop,
                    actual=(baseline - current) / baseline * 100,
                    message="Broj zapisa je opao iznad odobrenog praga.",
                )
            )

    @staticmethod
    def _status(changes: list[CompatibilityChange]) -> CompatibilityStatus:
        if any(item.classification == "INCOMPATIBLE" for item in changes):
            return "INCOMPATIBLE"
        if changes:
            return "COMPATIBLE_WITH_WARNINGS"
        return "COMPATIBLE"

    @staticmethod
    def _severity(
        changes: list[CompatibilityChange],
    ) -> CompatibilitySeverity:
        order = {"INFO": 0, "WARNING": 1, "ERROR": 2, "CRITICAL": 3}
        return max(
            (item.severity for item in changes),
            key=lambda item: order[item],
            default="INFO",
        )


__all__ = [
    "CompatibilityChange",
    "CompatibilityResult",
    "SupplierSchemaCompatibilityService",
]
