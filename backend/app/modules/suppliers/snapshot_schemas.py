from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.modules.suppliers.enums import (
    SnapshotArchiveStatus,
    SnapshotStatus,
    SnapshotStorageState,
)


class SnapshotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acquisition_run_id: uuid.UUID
    retention_class: str = Field(default="STANDARD", min_length=1, max_length=50)
    archive_after_days: int | None = Field(default=None, ge=1, le=36_500)
    preserve_online: bool = False
    legal_hold: bool = False
    archive_notes: str | None = Field(default=None, max_length=5000)


class SnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    snapshot_code: str
    supplier_id: uuid.UUID
    source_connection_id: uuid.UUID
    acquisition_run_id: uuid.UUID
    schema_profile_id: uuid.UUID
    mapping_profile_id: uuid.UUID
    schema_version_reference: int
    mapping_version_reference: int
    status: SnapshotStatus
    storage_state: SnapshotStorageState
    total_items: int
    snapshot_fingerprint: str | None
    payload_checksum: str | None
    source_artifact_checksum: str | None
    created_from_acquisition_at: datetime | None
    finalized_at: datetime | None
    archived_at: datetime | None
    restored_at: datetime | None
    archive_reference: str | None
    archive_checksum: str | None
    archive_size_bytes: int | None
    archive_format_version: int | None
    archive_manifest_version: int | None
    created_by: str
    retention_class: str
    archive_after_days: int | None
    preserve_online: bool
    legal_hold: bool
    archive_notes: str | None
    failure_code: str | None
    failure_message: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class SnapshotListResponse(BaseModel):
    items: list[SnapshotRead]
    total: int


class SnapshotStatistics(BaseModel):
    snapshot_id: uuid.UUID
    status: SnapshotStatus
    storage_state: SnapshotStorageState
    total_items: int
    active_item_count: int
    estimated_active_payload_bytes: int


class SnapshotItemSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    snapshot_id: uuid.UUID
    source_staged_record_id: uuid.UUID
    record_number: int
    source_key: str | None
    source_identifier: str | None
    item_fingerprint: str
    created_at: datetime


class SnapshotItemRead(SnapshotItemSummary):
    mapped_data: dict[str, object]
    source_image_links: list[dict[str, object]]


class SnapshotItemListResponse(BaseModel):
    items: list[SnapshotItemSummary]
    total: int


class SnapshotImageLinks(BaseModel):
    snapshot_item_id: uuid.UUID
    links: list[dict[str, object]]


class SnapshotIntegrityRead(BaseModel):
    snapshot_id: uuid.UUID
    valid: bool
    code: str


class SnapshotArchiveExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_source_artifact: bool = False


class SnapshotBulkArchiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_ids: list[
        Annotated[
            str,
            Field(
                min_length=36,
                max_length=36,
                pattern=r"^[0-9a-fA-F-]{36}$",
            ),
        ]
    ] = Field(min_length=1, max_length=100)
    include_source_artifact: bool = False


class SnapshotArchiveOperationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    snapshot_id: uuid.UUID
    status: SnapshotArchiveStatus
    archive_reference: str | None
    archive_checksum: str | None
    archive_size_bytes: int | None
    format_version: int
    manifest_version: int
    include_source_artifact: bool
    verified_at: datetime | None
    completed_at: datetime | None
    failure_code: str | None
    failure_message: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class SnapshotBulkArchiveResult(BaseModel):
    succeeded: list[SnapshotArchiveOperationRead]
    failed: list[dict[str, str]]


class SnapshotOffloadConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: uuid.UUID
    archive_reference: str = Field(min_length=1, max_length=1000)
    archive_checksum: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )
    override_preserve_online: bool = False


class SnapshotCandidateRead(BaseModel):
    snapshot_id: uuid.UUID
    snapshot_code: str
    created_at: datetime
    total_items: int
    estimated_payload_bytes: int
    eligible: bool
    exclusion_reasons: list[str]


class SnapshotCandidateResponse(BaseModel):
    items: list[SnapshotCandidateRead]
    estimated_item_count: int
    estimated_active_payload_bytes: int


__all__ = [
    "SnapshotArchiveExportRequest",
    "SnapshotArchiveOperationRead",
    "SnapshotBulkArchiveRequest",
    "SnapshotBulkArchiveResult",
    "SnapshotCandidateRead",
    "SnapshotCandidateResponse",
    "SnapshotCreate",
    "SnapshotImageLinks",
    "SnapshotIntegrityRead",
    "SnapshotItemListResponse",
    "SnapshotItemRead",
    "SnapshotItemSummary",
    "SnapshotListResponse",
    "SnapshotOffloadConfirm",
    "SnapshotRead",
    "SnapshotStatistics",
]
