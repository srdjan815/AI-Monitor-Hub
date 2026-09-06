from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.core.limits import BoundedJsonObject


class PriceListArchiveFilter(BaseModel):
    id: uuid.UUID
    name: str
    supplier_id: uuid.UUID | None = None


class PriceListArchiveFilters(BaseModel):
    suppliers: list[PriceListArchiveFilter]
    sources: list[PriceListArchiveFilter]


class PriceListArchiveEntry(BaseModel):
    acquisition_run_id: uuid.UUID
    acquisition_code: str
    supplier_id: uuid.UUID
    supplier_name: str
    source_connection_id: uuid.UUID
    source_name: str
    original_filename: str | None
    imported_at: datetime
    completed_at: datetime | None
    status: str
    total_records: int
    accepted_records: int
    rejected_records: int
    size_bytes: int | None
    checksum_sha256: str | None
    artifact_code: str | None
    storage_status: str
    archive_reference: str | None


class PriceListArchivePage(BaseModel):
    items: list[PriceListArchiveEntry]
    total: int
    limit: int
    offset: int


class ArchivedPriceListItem(BaseModel):
    id: uuid.UUID
    record_number: int
    product_code: str | None
    ean: str | None
    name: str | None
    price: str | None
    currency: str | None
    stock: str | None
    category: str | None
    validation_status: str
    warning_count: int
    error_count: int
    raw_data: BoundedJsonObject
    mapped_data: BoundedJsonObject


class ArchivedPriceListItemPage(BaseModel):
    acquisition_run_id: uuid.UUID
    items: list[ArchivedPriceListItem]
    total: int
    limit: int
    offset: int


__all__ = [
    "ArchivedPriceListItem",
    "ArchivedPriceListItemPage",
    "PriceListArchiveEntry",
    "PriceListArchiveFilter",
    "PriceListArchiveFilters",
    "PriceListArchivePage",
]
