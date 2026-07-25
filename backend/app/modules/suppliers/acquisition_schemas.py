from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.limits import MAX_DB_INTEGER
from app.modules.suppliers.enums import (
    AcquisitionIssueSeverity,
    AcquisitionRecordStatus,
    AcquisitionStatus,
    AcquisitionTriggerType,
)


class AcquisitionExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)


class AcquisitionRetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)


class AcquisitionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    acquisition_code: str = Field(max_length=50)
    supplier_id: uuid.UUID
    source_connection_id: uuid.UUID
    schema_profile_id: uuid.UUID
    mapping_profile_id: uuid.UUID
    schema_version_reference: int
    mapping_version_reference: int
    trigger_type: AcquisitionTriggerType
    status: AcquisitionStatus
    idempotency_key: str | None
    source_type: str
    original_filename: str | None
    artifact_reference: str | None
    content_type: str | None
    checksum: str | None
    artifact_size_bytes: int | None
    total_record_count: int
    accepted_record_count: int
    rejected_record_count: int
    warning_count: int
    error_count: int
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    failure_code: str | None
    failure_message: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class AcquisitionRunListResponse(BaseModel):
    items: list[AcquisitionRunRead]
    total: int


class AcquisitionStatistics(BaseModel):
    run_id: uuid.UUID
    status: AcquisitionStatus
    total_record_count: int
    accepted_record_count: int
    rejected_record_count: int
    warning_count: int
    error_count: int


class StagedRecordSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    acquisition_run_id: uuid.UUID
    record_number: int
    source_key: str | None
    source_identifier: str | None
    validation_status: AcquisitionRecordStatus
    warning_count: int
    error_count: int
    created_at: datetime


class StagedRecordRead(StagedRecordSummary):
    raw_data: dict[str, object]
    mapped_data: dict[str, object]


class StagedRecordListResponse(BaseModel):
    items: list[StagedRecordSummary]
    total: int


class AcquisitionIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    acquisition_run_id: uuid.UUID
    staged_record_id: uuid.UUID | None
    record_number: int
    schema_field_id: uuid.UUID | None
    mapping_rule_id: uuid.UUID | None
    error_code: str
    severity: AcquisitionIssueSeverity
    message: str
    technical_context: dict[str, object] | None
    created_at: datetime


class AcquisitionIssueListResponse(BaseModel):
    items: list[AcquisitionIssueRead]
    total: int


class AcquisitionListFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: AcquisitionStatus | None = None
    trigger_type: AcquisitionTriggerType | None = None
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0, le=MAX_DB_INTEGER)


__all__ = [
    "AcquisitionExecuteRequest",
    "AcquisitionIssueListResponse",
    "AcquisitionIssueRead",
    "AcquisitionListFilters",
    "AcquisitionRetryRequest",
    "AcquisitionRunListResponse",
    "AcquisitionRunRead",
    "AcquisitionStatistics",
    "StagedRecordListResponse",
    "StagedRecordRead",
    "StagedRecordSummary",
]
