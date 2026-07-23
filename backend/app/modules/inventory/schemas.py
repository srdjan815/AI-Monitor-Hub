from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.inventory.enums import MovementType, ReservationStatus


class WarehouseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    is_active: bool = True


class WarehouseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class WarehouseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class WarehouseList(BaseModel):
    items: list[WarehouseRead]
    total: int


class InventoryCreate(BaseModel):
    warehouse_id: uuid.UUID
    product_id: uuid.UUID
    quantity_on_hand: int = Field(default=0, ge=0)
    quantity_reserved: int = Field(default=0, ge=0)
    minimum_stock: int = Field(default=0, ge=0)
    reorder_point: int = Field(default=0, ge=0)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_quantities(self) -> InventoryCreate:
        if self.quantity_reserved > self.quantity_on_hand:
            raise ValueError(
                "quantity_reserved ne sme biti veći od quantity_on_hand"
            )
        return self


class InventoryUpdate(BaseModel):
    warehouse_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    quantity_on_hand: int | None = Field(default=None, ge=0)
    quantity_reserved: int | None = Field(default=None, ge=0)
    minimum_stock: int | None = Field(default=None, ge=0)
    reorder_point: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class InventoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    warehouse_id: uuid.UUID
    product_id: uuid.UUID
    quantity_on_hand: int
    quantity_reserved: int
    quantity_available: int
    minimum_stock: int
    reorder_point: int
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class InventoryList(BaseModel):
    items: list[InventoryRead]
    total: int


class InventoryMovementCreate(BaseModel):
    movement_type: MovementType
    product_id: uuid.UUID
    source_warehouse_id: uuid.UUID | None = None
    destination_warehouse_id: uuid.UUID | None = None
    quantity: int = Field(gt=0)
    reference_type: str | None = Field(default=None, max_length=100)
    reference_id: str | None = Field(default=None, max_length=255)
    external_reference: str | None = Field(default=None, max_length=255)
    note: str | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: str | None = Field(default=None, max_length=120)


class InventoryMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    movement_number: str
    movement_type: MovementType
    product_id: uuid.UUID
    source_warehouse_id: uuid.UUID | None
    destination_warehouse_id: uuid.UUID | None
    quantity: int
    reference_type: str | None
    reference_id: str | None
    external_reference: str | None
    note: str | None
    occurred_at: datetime
    created_at: datetime
    created_by: str | None
    is_reversed: bool
    reversed_at: datetime | None
    reversal_movement_id: uuid.UUID | None
    version: int


class InventoryMovementList(BaseModel):
    items: list[InventoryMovementRead]
    total: int


class InventoryReservationCreate(BaseModel):
    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    quantity: int = Field(gt=0)
    external_reference: str | None = Field(default=None, max_length=255)
    reference_type: str | None = Field(default=None, max_length=100)
    reference_id: str | None = Field(default=None, max_length=255)
    note: str | None = None
    expires_at: datetime | None = None


class InventoryReservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reservation_number: str
    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    quantity: int
    fulfilled_quantity: int
    remaining_quantity: int
    status: ReservationStatus
    reference_type: str | None
    reference_id: str | None
    external_reference: str | None
    note: str | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    fulfilled_at: datetime | None
    released_at: datetime | None
    cancelled_at: datetime | None
    version: int


class InventoryReservationList(BaseModel):
    items: list[InventoryReservationRead]
    total: int


class InventoryReservationFulfill(BaseModel):
    quantity: int = Field(gt=0)
    external_reference: str | None = Field(default=None, max_length=255)
    note: str | None = None


class ReservationReleaseResponse(InventoryReservationRead):
    pass


class ReservationCancelResponse(InventoryReservationRead):
    pass


class ReservationExpireSummary(BaseModel):
    processed: int
    skipped: int
