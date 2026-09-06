from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Health = Literal["OK", "UPOZORENJE", "KRITIČNO", "NEPOZNATO"]
Category = Literal["LOGOVI", "PRIVREMENI_FAJLOVI"]


class CapacityRead(BaseModel):
    total_bytes: int | None
    used_bytes: int | None
    free_bytes: int | None
    used_percent: float | None
    status: Health


class RuntimeRead(BaseModel):
    processor_count: int
    processor_load_percent: float | None
    memory: CapacityRead
    disk: CapacityRead
    measured_at: datetime


class StorageCategoryRead(BaseModel):
    code: str
    label: str
    size_bytes: int
    file_count: int
    status: Health
    cleanup_allowed: bool
    protection_reason: str | None = None
    scan_truncated: bool = False


class SystemInventoryRead(BaseModel):
    runtime: RuntimeRead
    database_size_bytes: int
    categories: list[StorageCategoryRead]


class CleanupPreviewRequest(BaseModel):
    category: Category
    older_than_days: int = Field(ge=1, le=3650)


class CleanupExecuteRequest(CleanupPreviewRequest):
    confirmation_token: str = Field(min_length=40, max_length=500)


class CleanupPreviewRead(BaseModel):
    category: Category
    older_than_days: int
    candidate_files: int
    candidate_bytes: int
    expires_at: datetime
    confirmation_token: str


class CleanupResultRead(BaseModel):
    audit_id: uuid.UUID
    status: str
    deleted_files: int
    deleted_bytes: int


class CleanupAuditRead(BaseModel):
    id: uuid.UUID
    category: str
    older_than_days: int
    status: str
    deleted_files: int
    deleted_bytes: int
    actor_id: str
    error_message: str | None
    created_at: datetime


class ArchiveSettingWrite(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    relative_path: str = Field(
        min_length=1, max_length=500, pattern=r"^[A-Za-z0-9._/-]+$"
    )
    snapshot_relative_path: str = Field(
        default="snapshots", min_length=1, max_length=500, pattern=r"^[A-Za-z0-9._/-]+$"
    )
    enabled: bool = False
    local_retention_days: int = Field(default=30, ge=1, le=3650)
    expected_version: int | None = Field(default=None, ge=1, le=2_147_483_647)


class ArchiveSettingRead(BaseModel):
    id: uuid.UUID
    backend_type: str
    display_name: str
    relative_path: str
    snapshot_relative_path: str
    enabled: bool
    local_retention_days: int
    last_tested_at: datetime | None
    last_test_status: str | None
    last_test_message: str | None
    version: int


class ArchiveStatusRead(BaseModel):
    setting: ArchiveSettingRead | None
    pending_transfers: int
    verified_transfers: int
    failed_transfers: int
    verified_bytes: int
    duplicate_artifacts: int
    duplicate_bytes: int


class ArchiveTestRead(BaseModel):
    status: Literal["SUCCEEDED", "FAILED"]
    message: str


class ArchiveProcessRead(BaseModel):
    attempted: int
    verified: int
    failed: int


__all__ = [
    "CleanupAuditRead",
    "CleanupExecuteRequest",
    "CleanupPreviewRead",
    "CleanupPreviewRequest",
    "CleanupResultRead",
    "ArchiveProcessRead",
    "ArchiveSettingRead",
    "ArchiveSettingWrite",
    "ArchiveStatusRead",
    "ArchiveTestRead",
    "SystemInventoryRead",
    "Health",
]
