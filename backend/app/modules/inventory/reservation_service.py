from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.modules.inventory.enums import MovementType, ReservationStatus
from app.modules.inventory.inventory_service_support import InventoryServiceSupport
from app.modules.inventory.models import (
    Inventory,
    InventoryMovement,
    InventoryReservation,
)
from app.modules.inventory.schemas import (
    InventoryReservationCreate,
    InventoryReservationFulfill,
)


class ReservationService(InventoryServiceSupport):
    """Atomic reservation, release, cancellation, fulfillment, and expiry."""

    async def get_reservation(self, reservation_id: uuid.UUID) -> InventoryReservation:
        reservation = await self.repository.get_reservation(reservation_id)
        if reservation is None:
            raise HTTPException(status_code=404, detail="Rezervacija nije pronađena")
        return reservation

    def _reservation_payload_matches(
        self,
        reservation: InventoryReservation,
        data: InventoryReservationCreate,
    ) -> bool:
        return (
            reservation.product_id == data.product_id
            and reservation.warehouse_id == data.warehouse_id
            and reservation.quantity == data.quantity
            and reservation.reference_type
            == self._normalize_optional(data.reference_type)
            and reservation.reference_id == self._normalize_optional(data.reference_id)
        )

    def _existing_reservation_or_conflict(
        self,
        reservation: InventoryReservation,
        data: InventoryReservationCreate,
    ) -> InventoryReservation:
        if not self._reservation_payload_matches(reservation, data):
            raise HTTPException(
                status_code=409,
                detail="Eksterna referenca pripada drugoj rezervaciji",
            )
        return reservation

    async def create_reservation(
        self, data: InventoryReservationCreate
    ) -> InventoryReservation:
        external_reference = self._normalize_optional(data.external_reference)
        if external_reference is not None:
            existing = await self.repository.get_reservation_by_external_reference(
                external_reference
            )
            if existing is not None:
                return self._existing_reservation_or_conflict(existing, data)
        try:
            await self._lock_active_product(data.product_id)
            await self._lock_active_warehouses({data.warehouse_id})
            inventory = await self.repository.get_inventory_for_update(
                data.warehouse_id, data.product_id
            )
            if inventory is None:
                raise HTTPException(
                    status_code=422,
                    detail="Zaliha za rezervaciju ne postoji",
                )
            if not inventory.is_active:
                raise HTTPException(
                    status_code=422,
                    detail="Zaliha za rezervaciju nije aktivna",
                )
            if inventory.quantity_available < data.quantity:
                raise HTTPException(
                    status_code=422,
                    detail="Nedovoljna raspoloživa količina",
                )
            inventory.quantity_reserved += data.quantity
            inventory.version += 1
            await self.repository.flush_balance(inventory)
            reservation = InventoryReservation(
                reservation_number=self._reservation_number(),
                product_id=data.product_id,
                warehouse_id=data.warehouse_id,
                quantity=data.quantity,
                status=ReservationStatus.ACTIVE.value,
                external_reference=external_reference,
                reference_type=self._normalize_optional(data.reference_type),
                reference_id=self._normalize_optional(data.reference_id),
                note=self._normalize_optional(data.note),
                expires_at=data.expires_at,
            )
            await self.repository.add_reservation(reservation)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            if external_reference is not None:
                existing = await self.repository.get_reservation_by_external_reference(
                    external_reference
                )
                if existing is not None:
                    return self._existing_reservation_or_conflict(existing, data)
            raise HTTPException(
                status_code=409,
                detail="Broj rezervacije ili eksterna referenca već postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(reservation)
        return reservation

    async def _finalize_reservation(
        self,
        reservation_id: uuid.UUID,
        *,
        status: ReservationStatus,
    ) -> InventoryReservation:
        now = datetime.now(UTC)
        try:
            reservation = await self.repository.get_reservation_for_update(
                reservation_id
            )
            if reservation is None:
                raise HTTPException(
                    status_code=404, detail="Rezervacija nije pronađena"
                )
            if reservation.status not in {
                ReservationStatus.ACTIVE.value,
                ReservationStatus.PARTIALLY_FULFILLED.value,
            }:
                raise HTTPException(
                    status_code=409,
                    detail="Finalizovana rezervacija se ne može menjati",
                )
            inventory = await self.repository.get_inventory_for_update(
                reservation.warehouse_id, reservation.product_id
            )
            remaining = reservation.remaining_quantity
            if inventory is None or inventory.quantity_reserved < remaining:
                raise HTTPException(
                    status_code=409,
                    detail="Stanje rezervisane količine nije konzistentno",
                )
            inventory.quantity_reserved -= remaining
            inventory.version += 1
            reservation.status = status.value
            if status == ReservationStatus.RELEASED:
                reservation.released_at = now
            else:
                reservation.cancelled_at = now
            reservation.version += 1
            await self.repository.flush_balance(inventory)
            await self.repository.flush_reservation(reservation)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(reservation)
        return reservation

    async def release_reservation(
        self, reservation_id: uuid.UUID
    ) -> InventoryReservation:
        return await self._finalize_reservation(
            reservation_id, status=ReservationStatus.RELEASED
        )

    async def cancel_reservation(
        self, reservation_id: uuid.UUID
    ) -> InventoryReservation:
        return await self._finalize_reservation(
            reservation_id, status=ReservationStatus.CANCELLED
        )

    @staticmethod
    def _matches_fulfillment(
        movement: InventoryMovement,
        reservation: InventoryReservation,
        quantity: int,
    ) -> bool:
        return (
            movement.movement_type == MovementType.ISSUE.value
            and movement.product_id == reservation.product_id
            and movement.source_warehouse_id == reservation.warehouse_id
            and movement.quantity == quantity
            and movement.reference_type == "RESERVATION"
            and movement.reference_id == str(reservation.id)
        )

    @staticmethod
    def _can_fulfill_inventory(
        inventory: Inventory | None,
        quantity: int,
    ) -> bool:
        return bool(
            inventory is not None
            and inventory.is_active
            and inventory.quantity_reserved >= quantity
            and inventory.quantity_on_hand >= quantity
        )

    async def _existing_fulfillment(
        self,
        reservation: InventoryReservation,
        quantity: int,
        external_reference: str | None,
    ) -> InventoryReservation | None:
        if external_reference is None:
            return None
        existing = await self.repository.get_movement_by_external_reference(
            external_reference
        )
        if existing is None:
            return None
        if not self._matches_fulfillment(existing, reservation, quantity):
            raise HTTPException(
                status_code=409,
                detail="Eksterna referenca pripada drugoj realizaciji",
            )
        return reservation

    async def fulfill_reservation(
        self,
        reservation_id: uuid.UUID,
        data: InventoryReservationFulfill,
    ) -> InventoryReservation:
        external_reference = self._normalize_optional(data.external_reference)
        try:
            reservation = await self.repository.get_reservation_for_update(
                reservation_id
            )
            if reservation is None:
                raise HTTPException(
                    status_code=404, detail="Rezervacija nije pronađena"
                )
            existing_result = await self._existing_fulfillment(
                reservation, data.quantity, external_reference
            )
            if existing_result is not None:
                return existing_result
            if reservation.status not in {
                ReservationStatus.ACTIVE.value,
                ReservationStatus.PARTIALLY_FULFILLED.value,
            }:
                raise HTTPException(
                    status_code=409,
                    detail="Rezervacija se ne može realizovati",
                )
            if data.quantity > reservation.remaining_quantity:
                raise HTTPException(
                    status_code=422,
                    detail="Količina prelazi preostalu rezervaciju",
                )
            inventory = await self.repository.get_inventory_for_update(
                reservation.warehouse_id, reservation.product_id
            )
            if not self._can_fulfill_inventory(inventory, data.quantity):
                raise HTTPException(
                    status_code=409,
                    detail="Stanje zalihe nije dovoljno za realizaciju",
                )
            assert inventory is not None
            inventory.quantity_reserved -= data.quantity
            inventory.quantity_on_hand -= data.quantity
            inventory.version += 1
            reservation.fulfilled_quantity += data.quantity
            reservation.version += 1
            now = datetime.now(UTC)
            if reservation.remaining_quantity == 0:
                reservation.status = ReservationStatus.FULFILLED.value
                reservation.fulfilled_at = now
            else:
                reservation.status = ReservationStatus.PARTIALLY_FULFILLED.value
            movement = InventoryMovement(
                movement_number=self._movement_number(),
                movement_type=MovementType.ISSUE.value,
                product_id=reservation.product_id,
                source_warehouse_id=reservation.warehouse_id,
                quantity=data.quantity,
                reference_type="RESERVATION",
                reference_id=str(reservation.id),
                external_reference=external_reference,
                note=self._normalize_optional(data.note),
                occurred_at=now,
            )
            await self.repository.flush_balance(inventory)
            await self.repository.flush_reservation(reservation)
            await self.repository.add_movement(movement)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            recovered = await self._find_fulfillment_retry(
                reservation_id,
                data.quantity,
                external_reference,
            )
            if recovered is not None:
                return recovered
            raise HTTPException(
                status_code=409,
                detail="Realizacija sa eksternom referencom već postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(reservation)
        return reservation

    async def _find_fulfillment_retry(
        self,
        reservation_id: uuid.UUID,
        quantity: int,
        external_reference: str | None,
    ) -> InventoryReservation | None:
        if external_reference is None:
            return None
        existing = await self.repository.get_movement_by_external_reference(
            external_reference
        )
        persisted = await self.repository.get_reservation(reservation_id)
        if (
            existing is not None
            and persisted is not None
            and self._matches_fulfillment(existing, persisted, quantity)
        ):
            return persisted
        return None

    async def expire_reservations(self, limit: int) -> tuple[int, int]:
        now = datetime.now(UTC)
        processed = 0
        skipped = 0
        try:
            reservations = await self.repository.list_expired_reservations_for_update(
                now, limit
            )
            for reservation in reservations:
                inventory = await self.repository.get_inventory_for_update(
                    reservation.warehouse_id, reservation.product_id
                )
                remaining = reservation.remaining_quantity
                if inventory is None or inventory.quantity_reserved < remaining:
                    skipped += 1
                    continue
                inventory.quantity_reserved -= remaining
                inventory.version += 1
                reservation.status = ReservationStatus.EXPIRED.value
                reservation.version += 1
                await self.repository.flush_balance(inventory)
                await self.repository.flush_reservation(reservation)
                processed += 1
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return processed, skipped
