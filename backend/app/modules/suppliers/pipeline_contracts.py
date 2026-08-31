from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Literal

from app.modules.suppliers.mapping_profile_models import SupplierMappingProfile
from app.modules.suppliers.mapping_profile_models import SupplierMappingRule
from app.modules.suppliers.models import Supplier, SupplierSource
from app.modules.suppliers.pipeline_models import (
    SupplierSourceArtifact,
    SupplierSourcePipelineRun,
    SupplierSourceSchedule,
)
from app.modules.suppliers.schema_profile_models import SupplierSchemaProfile
from app.modules.suppliers.schema_profile_models import SupplierSchemaField

PipelineStatus = Literal["SUCCEEDED", "FAILED", "SKIPPED", "CANCELLED"]
PipelinePhase = Literal[
    "FETCH",
    "ARTIFACT_SAVE",
    "TECHNICAL_VALIDATE",
    "SCHEMA_ANALYZE",
    "SCHEMA_COMPARE",
    "MAPPING",
    "BUSINESS_VALIDATE",
    "STAGING",
    "COMMIT",
    "SNAPSHOT",
    "DELTA",
    "INCIDENT",
]


@dataclass(frozen=True, slots=True)
class PipelineContext:
    supplier: Supplier
    source: SupplierSource
    run: SupplierSourcePipelineRun
    trigger: str
    idempotency_key: str
    logger: logging.Logger
    schedule: SupplierSourceSchedule | None = None
    artifact: SupplierSourceArtifact | None = None
    active_schema: SupplierSchemaProfile | None = None
    active_mapping: SupplierMappingProfile | None = None
    active_schema_fields: tuple[SupplierSchemaField, ...] = ()
    active_mapping_rules: tuple[SupplierMappingRule, ...] = ()

    def with_artifact(self, artifact: SupplierSourceArtifact) -> PipelineContext:
        if self.artifact is not None and self.artifact.id != artifact.id:
            raise ValueError("pipeline_context_artifact_is_immutable")
        return replace(self, artifact=artifact)


@dataclass(frozen=True, slots=True)
class PipelinePhaseResult:
    status: PipelineStatus
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    error_code: str | None = None
    warning_count: int = 0
    reference_id: str | None = None
    processed_records: int = 0
    error_count: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_ms": self.duration_ms,
            "error_code": self.error_code,
            "warning_count": self.warning_count,
            "reference_id": self.reference_id,
            "processed_records": self.processed_records,
            "error_count": self.error_count,
        }


@dataclass(slots=True)
class PipelineReferences:
    artifact_id: str | None = None
    analyzed_schema_id: str | None = None
    compatibility_report_id: str | None = None
    acquisition_run_id: str | None = None
    snapshot_id: str | None = None
    delta_run_id: str | None = None
    incident_id: str | None = None


@dataclass(slots=True)
class PipelineResult:
    status: PipelineStatus
    completed_phase: PipelinePhase
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    references: PipelineReferences = field(default_factory=PipelineReferences)
    telemetry: dict[str, int | float | str | bool | None] = field(
        default_factory=dict
    )

    @property
    def successful(self) -> bool:
        return self.status == "SUCCEEDED"


__all__ = [
    "PipelineContext",
    "PipelinePhase",
    "PipelinePhaseResult",
    "PipelineReferences",
    "PipelineResult",
    "PipelineStatus",
]
