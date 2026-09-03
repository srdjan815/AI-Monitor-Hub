from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DeltaCalculate(BaseModel):
    previous_snapshot_id: uuid.UUID
    current_snapshot_id: uuid.UUID
    idempotency_key: str | None = Field(default=None, max_length=255)


class DeltaCurrentCalculate(BaseModel):
    current_snapshot_id: uuid.UUID
    idempotency_key: str | None = Field(default=None, max_length=255)


class DeltaRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    delta_code: str
    supplier_id: uuid.UUID
    source_connection_id: uuid.UUID
    previous_snapshot_id: uuid.UUID
    current_snapshot_id: uuid.UUID
    status: str
    comparison_version: int
    total_previous_items: int
    total_current_items: int
    added_items: int
    removed_items: int
    modified_items: int
    unchanged_items: int
    price_increased_items: int
    price_decreased_items: int
    stock_increased_items: int
    stock_decreased_items: int
    became_available_items: int
    became_unavailable_items: int
    image_changed_items: int
    identifier_changed_items: int
    warning_count: int
    error_count: int
    anomaly_signals: list[dict[str, object]]
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    failure_code: str | None
    failure_message: str | None
    created_at: datetime


class DeltaRunList(BaseModel):
    items: list[DeltaRunRead]
    total: int


class DeltaItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    delta_run_id: uuid.UUID
    change_type: str
    matching_key_type: str
    matching_key_value: str
    previous_snapshot_item_id: uuid.UUID | None
    current_snapshot_item_id: uuid.UUID | None
    changed_field_count: int
    has_price_change: bool
    has_stock_change: bool
    has_image_change: bool
    has_identifier_change: bool
    change_summary: dict[str, object]
    anomaly_flags: list[str]


class DeltaItemList(BaseModel):
    items: list[DeltaItemRead]
    total: int


class DeltaFieldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    delta_item_id: uuid.UUID
    field_path: str
    field_role: str | None
    change_type: str
    previous_value_type: str | None
    current_value_type: str | None
    previous_value_hash: str | None
    current_value_hash: str | None
    previous_value_preview: str | None
    current_value_preview: str | None
    previous_numeric_value: Decimal | None
    current_numeric_value: Decimal | None
    absolute_numeric_change: Decimal | None
    percentage_numeric_change: Decimal | None


class DeltaFieldList(BaseModel):
    items: list[DeltaFieldRead]
    total: int


class DeltaCompatibility(BaseModel):
    compatible: bool
    code: str
    message: str
    previous_snapshot_id: uuid.UUID
    current_snapshot_id: uuid.UUID


__all__ = ["DeltaCalculate", "DeltaCompatibility", "DeltaCurrentCalculate", "DeltaFieldList", "DeltaFieldRead", "DeltaItemList", "DeltaItemRead", "DeltaRunList", "DeltaRunRead"]
