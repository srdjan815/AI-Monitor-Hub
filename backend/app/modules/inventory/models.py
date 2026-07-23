from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin
from app.modules.catalog.models import Product
from app.modules.inventory.enums import MovementType, ReservationStatus


class Warehouse(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "warehouses"
    __table_args__ = (
        UniqueConstraint("code", name="uq_warehouses_code"),
        Index("ix_warehouses_active", "is_active"),
    )

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    inventory_records: Mapped[list[Inventory]] = relationship(
        back_populates="warehouse"
    )


class Inventory(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "inventory"
    __table_args__ = (
        UniqueConstraint(
            "warehouse_id",
            "product_id",
            name="uq_inventory_warehouse_product",
        ),
        CheckConstraint(
            "quantity_on_hand >= 0",
            name="quantity_on_hand_nonnegative",
        ),
        CheckConstraint(
            "quantity_reserved >= 0",
            name="quantity_reserved_nonnegative",
        ),
        CheckConstraint(
            "quantity_reserved <= quantity_on_hand",
            name="reserved_not_above_on_hand",
        ),
        CheckConstraint(
            "minimum_stock >= 0",
            name="minimum_stock_nonnegative",
        ),
        CheckConstraint(
            "reorder_point >= 0",
            name="reorder_point_nonnegative",
        ),
        Index("ix_inventory_warehouse_active", "warehouse_id", "is_active"),
        Index("ix_inventory_product_active", "product_id", "is_active"),
    )

    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity_on_hand: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    quantity_reserved: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    minimum_stock: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    reorder_point: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    warehouse: Mapped[Warehouse] = relationship(
        back_populates="inventory_records"
    )
    product: Mapped[Product] = relationship()

    @property
    def quantity_available(self) -> int:
        return self.quantity_on_hand - self.quantity_reserved


class InventoryMovement(UUIDMixin, Base):
    __tablename__ = "inventory_movements"
    __table_args__ = (
        UniqueConstraint(
            "movement_number",
            name="uq_inventory_movements_movement_number",
        ),
        UniqueConstraint(
            "external_reference",
            name="uq_inventory_movements_external_reference",
        ),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint(
            "movement_type IN "
            "('RECEIPT', 'ISSUE', 'ADJUSTMENT_IN', "
            "'ADJUSTMENT_OUT', 'TRANSFER')",
            name="movement_type_valid",
        ),
        CheckConstraint(
            "("
            "movement_type IN ('RECEIPT', 'ADJUSTMENT_IN') "
            "AND source_warehouse_id IS NULL "
            "AND destination_warehouse_id IS NOT NULL"
            ") OR ("
            "movement_type IN ('ISSUE', 'ADJUSTMENT_OUT') "
            "AND source_warehouse_id IS NOT NULL "
            "AND destination_warehouse_id IS NULL"
            ") OR ("
            "movement_type = 'TRANSFER' "
            "AND source_warehouse_id IS NOT NULL "
            "AND destination_warehouse_id IS NOT NULL "
            "AND source_warehouse_id <> destination_warehouse_id"
            ")",
            name="warehouse_combination_valid",
        ),
        Index(
            "ix_inventory_movements_product_occurred",
            "product_id",
            "occurred_at",
        ),
        Index(
            "ix_inventory_movements_source_occurred",
            "source_warehouse_id",
            "occurred_at",
        ),
        Index(
            "ix_inventory_movements_destination_occurred",
            "destination_warehouse_id",
            "occurred_at",
        ),
        Index(
            "ix_inventory_movements_type_occurred",
            "movement_type",
            "occurred_at",
        ),
    )

    movement_number: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    movement_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=MovementType.RECEIPT.value,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=True,
    )
    destination_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    reference_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    external_reference: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_by: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    is_reversed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    reversed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reversal_movement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inventory_movements.id", ondelete="RESTRICT"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    product: Mapped[Product] = relationship()
    source_warehouse: Mapped[Warehouse | None] = relationship(
        foreign_keys=[source_warehouse_id]
    )
    destination_warehouse: Mapped[Warehouse | None] = relationship(
        foreign_keys=[destination_warehouse_id]
    )
    reversed_movement: Mapped[InventoryMovement | None] = relationship(
        remote_side="InventoryMovement.id",
        foreign_keys=[reversal_movement_id],
    )


class InventoryReservation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "inventory_reservations"
    __table_args__ = (
        UniqueConstraint(
            "reservation_number",
            name="uq_inventory_reservations_reservation_number",
        ),
        UniqueConstraint(
            "external_reference",
            name="uq_inventory_reservations_external_reference",
        ),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint(
            "fulfilled_quantity >= 0",
            name="fulfilled_quantity_nonnegative",
        ),
        CheckConstraint(
            "fulfilled_quantity <= quantity",
            name="fulfilled_not_above_quantity",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'PARTIALLY_FULFILLED', 'FULFILLED', "
            "'RELEASED', 'CANCELLED', 'EXPIRED')",
            name="status_valid",
        ),
        Index(
            "ix_inventory_reservations_product_status",
            "product_id",
            "status",
        ),
        Index(
            "ix_inventory_reservations_warehouse_status",
            "warehouse_id",
            "status",
        ),
        Index(
            "ix_inventory_reservations_status_expires",
            "status",
            "expires_at",
        ),
        Index("ix_inventory_reservations_created", "created_at"),
    )

    reservation_number: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    fulfilled_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ReservationStatus.ACTIVE.value
    )
    reference_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    reference_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    external_reference: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fulfilled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    product: Mapped[Product] = relationship()
    warehouse: Mapped[Warehouse] = relationship()

    @property
    def remaining_quantity(self) -> int:
        return self.quantity - self.fulfilled_quantity
