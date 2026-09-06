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


__all__ = [
    "CleanupAuditRead",
    "CleanupExecuteRequest",
    "CleanupPreviewRead",
    "CleanupPreviewRequest",
    "CleanupResultRead",
    "SystemInventoryRead",
    "Health",
]
