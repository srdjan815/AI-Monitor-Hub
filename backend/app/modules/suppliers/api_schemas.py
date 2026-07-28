from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.modules.suppliers.enums import IncidentPriority
from app.modules.suppliers.incident_schemas import IncidentRead


class SupplierApiPage(BaseModel):
    items: list[IncidentRead]
    total: int
    limit: int
    offset: int
    has_more: bool


class SupplierApiErrorDetail(BaseModel):
    code: str
    message: str
    details: object | None = None
    field_errors: list[object] = Field(default_factory=list)


class SupplierApiErrorResponse(BaseModel):
    detail: object
    code: str
    request_id: str
    correlation_id: str
    error: SupplierApiErrorDetail


CANONICAL_ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    code: {
        "model": SupplierApiErrorResponse,
        "description": description,
    }
    for code, description in {
        400: "Neispravan zahtev",
        401: "Autentikacija je obavezna",
        403: "Nedovoljna dozvola",
        404: "Resurs nije pronađen",
        409: "Konflikt ili nedozvoljena promena stanja",
        413: "Payload je prevelik",
        422: "Validacija zahteva nije uspela",
        429: "Prekoračeno ograničenje zahteva",
        500: "Interna greška bez javnog stack trace-a",
    }.items()
}


class SupplierPlatformSearchResult(BaseModel):
    resource_type: Literal[
        "supplier",
        "source_connection",
        "acquisition",
        "snapshot",
        "delta",
        "incident",
    ]
    id: uuid.UUID
    code: str
    display_name: str
    short_context: str | None = None
    status: str | None = None
    resource_path: str


class SupplierPlatformSearchResponse(BaseModel):
    items: list[SupplierPlatformSearchResult]
    total: int
    limit: int
    has_more: bool


class SupplierPlatformCount(BaseModel):
    value: int | None
    permitted: bool


class SupplierPlatformOperation(BaseModel):
    resource_type: str
    id: uuid.UUID
    code: str
    status: str
    occurred_at: datetime
    resource_path: str


class SupplierProcessStatus(BaseModel):
    supplier_id: uuid.UUID
    supplier_name: str
    source_id: uuid.UUID | None
    source_name: str | None
    source_format: str | None
    connection_status: str
    schema_status: str
    mapping_status: str
    acquisition_status: str
    last_success_at: datetime | None
    article_count: int | None
    content_changed: bool | None
    warning: str | None


class SupplierPlatformOverview(BaseModel):
    range_from: datetime
    range_to: datetime
    active_suppliers: SupplierPlatformCount
    active_source_connections: SupplierPlatformCount
    recent_acquisitions: SupplierPlatformCount
    failed_acquisitions: SupplierPlatformCount
    ready_snapshots: SupplierPlatformCount
    archived_snapshots: SupplierPlatformCount
    recent_deltas: SupplierPlatformCount
    active_incidents: SupplierPlatformCount
    overdue_incidents: SupplierPlatformCount
    unassigned_incidents: SupplierPlatformCount
    latest_operations: list[SupplierPlatformOperation]
    recent_failures: list[SupplierPlatformOperation]
    supplier_processes: list[SupplierProcessStatus]


class BulkIncidentAssignItem(BaseModel):
    incident_id: uuid.UUID
    assigned_user_id: str = Field(min_length=1, max_length=255)


class BulkIncidentAssignRequest(BaseModel):
    items: list[BulkIncidentAssignItem] = Field(min_length=1, max_length=100)


class BulkIncidentPriorityItem(BaseModel):
    incident_id: uuid.UUID
    priority: IncidentPriority


class BulkIncidentPriorityRequest(BaseModel):
    items: list[BulkIncidentPriorityItem] = Field(min_length=1, max_length=100)


class BulkItemResult(BaseModel):
    input_reference: str
    status: Literal["SUCCEEDED", "FAILED", "SKIPPED"]
    resource_id: uuid.UUID | None = None
    resource_code: str | None = None
    error_code: str | None = None
    message: str


class BulkOperationResponse(BaseModel):
    requested_count: int
    succeeded_count: int
    failed_count: int
    skipped_count: int
    results: list[BulkItemResult]


class SupplierApiFilters(BaseModel):
    created_from: datetime | None = None
    created_to: datetime | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "SupplierApiFilters":
        if (
            self.created_from is not None
            and self.created_to is not None
            and self.created_from > self.created_to
        ):
            raise ValueError("created_from ne sme biti posle created_to")
        return self


__all__ = [
    "BulkIncidentAssignRequest",
    "BulkIncidentPriorityRequest",
    "BulkItemResult",
    "BulkOperationResponse",
    "CANONICAL_ERROR_RESPONSES",
    "SupplierApiFilters",
    "SupplierApiErrorResponse",
    "SupplierApiPage",
    "SupplierPlatformCount",
    "SupplierPlatformOperation",
    "SupplierPlatformOverview",
    "SupplierPlatformSearchResponse",
    "SupplierPlatformSearchResult",
]
