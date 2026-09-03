from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.suppliers.enums import IncidentPriority, IncidentSourceDomain, IncidentType


class ManualIncidentCreate(BaseModel):
    supplier_id: uuid.UUID
    source_connection_id: uuid.UUID | None = None
    incident_type: str = Field(
        pattern="^(MANUAL_DATA_QUALITY_REPORT|MANUAL_SUPPLIER_REPORT|CONFIGURATION_REVIEW_REQUIRED|OTHER)$"
    )
    severity: str = Field(pattern="^(INFO|LOW|MEDIUM|HIGH|CRITICAL)$")
    priority: IncidentPriority
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=2000)
    due_at: datetime | None = None
    assigned_user_id: str | None = Field(default=None, max_length=255)


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    incident_code: str
    supplier_id: uuid.UUID
    source_connection_id: uuid.UUID | None
    incident_type: str
    source_domain: str
    severity: str
    priority: str
    status: str
    title: str
    description: str
    fingerprint: str
    correlation_key: str | None
    occurrence_count: int
    first_detected_at: datetime
    last_detected_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    dismissed_at: datetime | None
    suppressed_at: datetime | None
    suppression_until: datetime | None
    reopened_at: datetime | None
    due_at: datetime | None
    assigned_user_id: str | None
    resolution_code: str | None
    resolution_summary: str | None
    source_acquisition_run_id: uuid.UUID | None
    source_snapshot_id: uuid.UUID | None
    source_snapshot_archive_operation_id: uuid.UUID | None
    source_delta_run_id: uuid.UUID | None
    source_delta_item_id: uuid.UUID | None
    sanitized_context: dict[str, object]
    version: int
    created_at: datetime
    updated_at: datetime


class IncidentList(BaseModel):
    items: list[IncidentRead]
    total: int


class IncidentActionReason(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class ResolveRequest(BaseModel):
    resolution_code: str = Field(min_length=1, max_length=100)
    resolution_summary: str = Field(min_length=1, max_length=1000)


class SuppressRequest(IncidentActionReason):
    suppression_until: datetime | None = None


class AssignRequest(BaseModel):
    assigned_user_id: str = Field(min_length=1, max_length=255)


class PriorityRequest(BaseModel):
    priority: IncidentPriority


class DueDateRequest(BaseModel):
    due_at: datetime | None


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    incident_id: uuid.UUID
    body: str
    created_by: str
    created_at: datetime


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    incident_id: uuid.UUID
    event_type: str
    actor_id: str
    previous_status: str | None
    current_status: str | None
    event_data: dict[str, object]
    created_at: datetime


class EventList(BaseModel):
    items: list[EventRead]
    total: int


class CommentList(BaseModel):
    items: list[CommentRead]
    total: int


class LinkCreate(BaseModel):
    related_incident_id: uuid.UUID
    relationship_type: str = Field(pattern="^(PARENT|CHILD|RELATED)$")


class LinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    incident_id: uuid.UUID
    related_incident_id: uuid.UUID
    relationship_type: str
    created_by: str
    created_at: datetime


class LinkList(BaseModel):
    items: list[LinkRead]
    total: int


class IncidentThresholdConfiguration(BaseModel):
    minimum_count: int | None = Field(default=None, ge=0, le=10_000_000)
    minimum_ratio: float | None = Field(default=None, ge=0, le=1)
    minimum_percentage: float | None = Field(default=None, ge=0, le=1_000_000)


class RuleCreate(BaseModel):
    rule_code: str = Field(min_length=1, max_length=100, pattern="^[A-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=255)
    source_domain: IncidentSourceDomain
    incident_type: IncidentType
    signal_code: str | None = Field(default=None, max_length=100)
    resulting_severity: str = Field(pattern="^(INFO|LOW|MEDIUM|HIGH|CRITICAL)$")
    default_priority: IncidentPriority
    threshold_configuration: IncidentThresholdConfiguration = Field(
        default_factory=IncidentThresholdConfiguration
    )
    supplier_id: uuid.UUID | None = None
    source_connection_id: uuid.UUID | None = None
    auto_reopen: bool = True
    suppression_compatible: bool = True


class RuleUpdate(BaseModel):
    enabled: bool | None = None
    resulting_severity: str | None = Field(
        default=None, pattern="^(INFO|LOW|MEDIUM|HIGH|CRITICAL)$"
    )
    default_priority: IncidentPriority | None = None
    threshold_configuration: IncidentThresholdConfiguration | None = None


class RuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    rule_code: str
    name: str
    source_domain: str
    incident_type: str
    signal_code: str | None
    enabled: bool
    resulting_severity: str
    default_priority: str
    threshold_configuration: dict[str, object]
    auto_reopen: bool
    suppression_compatible: bool
    supplier_id: uuid.UUID | None
    source_connection_id: uuid.UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RuleList(BaseModel):
    items: list[RuleRead]
    total: int


class SummaryRead(BaseModel):
    total_active: int
    open: int
    acknowledged: int
    in_progress: int
    resolved: int
    dismissed: int
    suppressed: int
    priorities: dict[str, int]
    high_or_critical_active: int
    overdue: int
    unassigned: int


class IncidentSyncCandidateResponse(BaseModel):
    source_domain: str
    source_id: uuid.UUID
    candidates: list[dict[str, object]]


__all__ = [
    "AssignRequest",
    "CommentCreate",
    "CommentList",
    "CommentRead",
    "DueDateRequest",
    "EventList",
    "EventRead",
    "IncidentActionReason",
    "IncidentList",
    "IncidentRead",
    "IncidentSyncCandidateResponse",
    "IncidentThresholdConfiguration",
    "LinkCreate",
    "LinkList",
    "LinkRead",
    "ManualIncidentCreate",
    "PriorityRequest",
    "ResolveRequest",
    "RuleCreate",
    "RuleList",
    "RuleRead",
    "RuleUpdate",
    "SummaryRead",
    "SuppressRequest",
]
