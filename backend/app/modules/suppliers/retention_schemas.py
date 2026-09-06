from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RetentionPolicyWrite(BaseModel):
    enabled: bool = False
    staging_retention_days: int = Field(ge=1, le=3650)
    snapshot_online_days: int = Field(ge=1, le=3650)
    minimum_online_snapshots: int = Field(ge=2, le=100)
    cleanup_batch_size: int = Field(ge=1, le=10_000)
    expected_version: int | None = Field(default=None, ge=1, le=2_147_483_647)


class RetentionPolicyRead(BaseModel):
    source_connection_id: uuid.UUID
    supplier_name: str
    source_name: str
    enabled: bool
    configured: bool
    staging_retention_days: int
    snapshot_online_days: int
    minimum_online_snapshots: int
    cleanup_batch_size: int
    version: int | None


class RetentionPolicyListRead(BaseModel):
    items: list[RetentionPolicyRead]
    total: int


class DataRetentionAnalysisRead(BaseModel):
    run_id: uuid.UUID
    source_connection_id: uuid.UUID
    staging_cutoff: datetime
    snapshot_cutoff: datetime
    candidate_staging_rows: int
    candidate_staging_bytes: int
    referenced_staging_rows: int
    candidate_snapshots: int
    candidate_snapshot_items: int
    candidate_snapshot_bytes: int
    observations_preserved: int
    snapshots_ready_for_offload: int
    snapshots_requiring_archive: int
    protected_snapshots: int
    execution_allowed: bool
    blockers: list[str]
    created_at: datetime


class RetentionRunRead(BaseModel):
    id: uuid.UUID
    source_connection_id: uuid.UUID
    source_name: str
    status: str
    staging_cutoff: datetime
    snapshot_cutoff: datetime
    candidate_staging_rows: int
    candidate_snapshots: int
    preserved_observations: int
    deleted_staging_rows: int
    offloaded_snapshot_items: int
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    failure_message: str | None


__all__ = [
    "DataRetentionAnalysisRead",
    "RetentionPolicyListRead",
    "RetentionPolicyRead",
    "RetentionPolicyWrite",
    "RetentionRunRead",
]
