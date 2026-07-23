from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import Product
from app.modules.inventory.enums import MovementType, ReservationStatus
from app.modules.inventory.models import (
    Inventory,
    InventoryMovement,
    InventoryReservation,
    Warehouse,
)
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.schemas import (
    InventoryCreate,
    InventoryMovementCreate,
    InventoryReservationCreate,
    InventoryReservationFulfill,
    InventoryUpdate,
    WarehouseCreate,
    WarehouseUpdate,
)


class InventoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = InventoryRepository(session)

    @staticmethod
    def _normalize_optional(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    async def _get_warehouse_or_404(
        self,
        warehouse_id: uuid.UUID,
    ) -> Warehouse:
        warehouse = await self.repository.get_warehouse(warehouse_id)
        if warehouse is None:
            raise HTTPException(
                status_code=404,
                detail="Skladište nije pronađeno",
            )
        return warehouse

    async def _get_inventory_or_404(
        self,
        inventory_id: uuid.UUID,
    ) -> Inventory:
        inventory = await self.repository.get_inventory(inventory_id)
        if inventory is None:
            raise HTTPException(
                status_code=404,
                detail="Zaliha nije pronađena",
            )
        return inventory

    async def _get_product_or_404(self, product_id: uuid.UUID) -> Product:
        product = await self.repository.get_product(product_id)
        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Proizvod nije pronađen",
            )
        return product

    @staticmethod
    def _validate_quantities(
        *,
        quantity_on_hand: int,
        quantity_reserved: int,
        minimum_stock: int,
        reorder_point: int,
    ) -> None:
        if min(
            quantity_on_hand,
            quantity_reserved,
            minimum_stock,
            reorder_point,
        ) < 0:
            raise HTTPException(
                status_code=422,
                detail="Količine ne mogu biti negativne",
            )
        if quantity_reserved > quantity_on_hand:
            raise HTTPException(
                status_code=422,
                detail="Rezervisana količina ne može biti veća od stanja",
            )

    async def create_warehouse(
        self,
        data: WarehouseCreate,
    ) -> Warehouse:
        code = data.code.strip().lower()
        name = data.name.strip()
        if not code or not name:
            raise HTTPException(
                status_code=422,
                detail="Kod i naziv skladišta su obavezni",
            )
        if await self.repository.get_warehouse_by_code(code):
            raise HTTPException(
                status_code=409,
                detail="Kod skladišta već postoji",
            )

        warehouse = Warehouse(
            code=code,
            name=name,
            description=self._normalize_optional(data.description),
            is_active=data.is_active,
        )
        try:
            await self.repository.create_warehouse(warehouse)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Kod skladišta već postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(warehouse)
        return warehouse

    async def get_warehouse(
        self,
        warehouse_id: uuid.UUID,
    ) -> Warehouse:
        return await self._get_warehouse_or_404(warehouse_id)

    async def update_warehouse(
        self,
        warehouse_id: uuid.UUID,
        data: WarehouseUpdate,
    ) -> Warehouse:
        warehouse = await self._get_warehouse_or_404(warehouse_id)
        changes = data.model_dump(exclude_unset=True)
        if "name" in changes:
            changes["name"] = changes["name"].strip()
            if not changes["name"]:
                raise HTTPException(
                    status_code=422,
                    detail="Naziv skladišta je obavezan",
                )
        if "description" in changes:
            changes["description"] = self._normalize_optional(
                changes["description"]
            )

        actual_changes = {
            field: value
            for field, value in changes.items()
            if getattr(warehouse, field) != value
        }
        if actual_changes:
            actual_changes["version"] = warehouse.version + 1

        try:
            await self.repository.update_warehouse(
                warehouse,
                actual_changes,
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(warehouse)
        return warehouse

    async def deactivate_warehouse(self, warehouse_id: uuid.UUID) -> None:
        warehouse = await self._get_warehouse_or_404(warehouse_id)
        if not warehouse.is_active:
            return
        try:
            await self.repository.deactivate_warehouse(warehouse)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(warehouse)

    async def create_inventory(
        self,
        data: InventoryCreate,
    ) -> Inventory:
        await self._get_warehouse_or_404(data.warehouse_id)
        await self._get_product_or_404(data.product_id)
        self._validate_quantities(
            quantity_on_hand=data.quantity_on_hand,
            quantity_reserved=data.quantity_reserved,
            minimum_stock=data.minimum_stock,
            reorder_point=data.reorder_point,
        )
        if await self.repository.get_inventory_by_pair(
            data.warehouse_id,
            data.product_id,
        ):
            raise HTTPException(
                status_code=409,
                detail="Zaliha za skladište i proizvod već postoji",
            )

        inventory = Inventory(**data.model_dump())
        try:
            await self.repository.create_inventory(inventory)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Zaliha za skladište i proizvod već postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(inventory)
        return inventory

    async def get_inventory(
        self,
        inventory_id: uuid.UUID,
    ) -> Inventory:
        return await self._get_inventory_or_404(inventory_id)

    async def update_inventory(
        self,
        inventory_id: uuid.UUID,
        data: InventoryUpdate,
    ) -> Inventory:
        inventory = await self._get_inventory_or_404(inventory_id)
        changes = data.model_dump(exclude_unset=True)

        warehouse_id = changes.get("warehouse_id", inventory.warehouse_id)
        product_id = changes.get("product_id", inventory.product_id)
        if warehouse_id is None or product_id is None:
            raise HTTPException(
                status_code=422,
                detail="Skladište i proizvod su obavezni",
            )
        if "warehouse_id" in changes:
            await self._get_warehouse_or_404(warehouse_id)
        if "product_id" in changes:
            await self._get_product_or_404(product_id)

        quantities = {
            "quantity_on_hand": changes.get(
                "quantity_on_hand", inventory.quantity_on_hand
            ),
            "quantity_reserved": changes.get(
                "quantity_reserved", inventory.quantity_reserved
            ),
            "minimum_stock": changes.get(
                "minimum_stock", inventory.minimum_stock
            ),
            "reorder_point": changes.get(
                "reorder_point", inventory.reorder_point
            ),
        }
        if any(value is None for value in quantities.values()):
            raise HTTPException(
                status_code=422,
                detail="Količine ne mogu biti null",
            )
        self._validate_quantities(**quantities)

        if (
            warehouse_id != inventory.warehouse_id
            or product_id != inventory.product_id
        ):
            existing = await self.repository.get_inventory_by_pair(
                warehouse_id,
                product_id,
            )
            if existing is not None and existing.id != inventory.id:
                raise HTTPException(
                    status_code=409,
                    detail="Zaliha za skladište i proizvod već postoji",
                )

        actual_changes = {
            field: value
            for field, value in changes.items()
            if getattr(inventory, field) != value
        }
        if actual_changes:
            actual_changes["version"] = inventory.version + 1

        try:
            await self.repository.update_inventory(
                inventory,
                actual_changes,
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Zaliha za skladište i proizvod već postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(inventory)
        return inventory

    async def deactivate_inventory(self, inventory_id: uuid.UUID) -> None:
        inventory = await self._get_inventory_or_404(inventory_id)
        if not inventory.is_active:
            return
        try:
            await self.repository.deactivate_inventory(inventory)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(inventory)

    async def get_movement(
        self,
        movement_id: uuid.UUID,
    ) -> InventoryMovement:
        movement = await self.repository.get_movement(movement_id)
        if movement is None:
            raise HTTPException(
                status_code=404,
                detail="Kretanje zaliha nije pronađeno",
            )
        return movement

    @staticmethod
    def _movement_number() -> str:
        date_part = datetime.now(UTC).strftime("%Y%m%d")
        random_part = uuid.uuid4().hex[:8].upper()
        return f"MOV-{date_part}-{random_part}"

    @staticmethod
    def _reservation_number() -> str:
        date_part = datetime.now(UTC).strftime("%Y%m%d")
        random_part = uuid.uuid4().hex[:8].upper()
        return f"RES-{date_part}-{random_part}"

    def _movement_payload_matches(
        self,
        movement: InventoryMovement,
        data: InventoryMovementCreate,
    ) -> bool:
        return (
            movement.movement_type == data.movement_type.value
            and movement.product_id == data.product_id
            and movement.source_warehouse_id == data.source_warehouse_id
            and movement.destination_warehouse_id
            == data.destination_warehouse_id
            and movement.quantity == data.quantity
            and movement.reference_type
            == self._normalize_optional(data.reference_type)
            and movement.reference_id
            == self._normalize_optional(data.reference_id)
            and movement.note == self._normalize_optional(data.note)
            and movement.created_by
            == self._normalize_optional(data.created_by)
        )

    def _existing_movement_or_conflict(
        self,
        movement: InventoryMovement,
        data: InventoryMovementCreate,
    ) -> InventoryMovement:
        if not self._movement_payload_matches(movement, data):
            raise HTTPException(
                status_code=409,
                detail="Eksterna referenca pripada drugom kretanju",
            )
        return movement

    @staticmethod
    def _movement_warehouses(
        movement_type: MovementType,
        source_warehouse_id: uuid.UUID | None,
        destination_warehouse_id: uuid.UUID | None,
    ) -> tuple[uuid.UUID | None, uuid.UUID | None]:
        source_required = movement_type in {
            MovementType.ISSUE,
            MovementType.ADJUSTMENT_OUT,
            MovementType.TRANSFER,
        }
        destination_required = movement_type in {
            MovementType.RECEIPT,
            MovementType.ADJUSTMENT_IN,
            MovementType.TRANSFER,
        }
        if source_required != (source_warehouse_id is not None):
            raise HTTPException(
                status_code=422,
                detail="Neispravna izvorna lokacija za tip kretanja",
            )
        if destination_required != (
            destination_warehouse_id is not None
        ):
            raise HTTPException(
                status_code=422,
                detail="Neispravna odredišna lokacija za tip kretanja",
            )
        if (
            movement_type == MovementType.TRANSFER
            and source_warehouse_id == destination_warehouse_id
        ):
            raise HTTPException(
                status_code=422,
                detail="Izvorno i odredišno skladište moraju biti različiti",
            )
        return source_warehouse_id, destination_warehouse_id

    async def _lock_active_product(
        self,
        product_id: uuid.UUID,
    ) -> Product:
        product = await self.repository.get_product_for_update(product_id)
        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Proizvod nije pronađen",
            )
        if not product.is_active:
            raise HTTPException(
                status_code=422,
                detail="Proizvod nije aktivan",
            )
        return product

    async def _lock_active_warehouses(
        self,
        warehouse_ids: set[uuid.UUID],
    ) -> None:
        for warehouse_id in sorted(warehouse_ids, key=str):
            warehouse = await self.repository.get_warehouse_for_update(
                warehouse_id
            )
            if warehouse is None:
                raise HTTPException(
                    status_code=404,
                    detail="Skladište nije pronađeno",
                )
            if not warehouse.is_active:
                raise HTTPException(
                    status_code=422,
                    detail="Skladište nije aktivno",
                )

    async def _apply_balance_changes(
        self,
        *,
        movement_type: MovementType,
        product_id: uuid.UUID,
        source_warehouse_id: uuid.UUID | None,
        destination_warehouse_id: uuid.UUID | None,
        quantity: int,
    ) -> None:
        warehouse_ids = {
            warehouse_id
            for warehouse_id in (
                source_warehouse_id,
                destination_warehouse_id,
            )
            if warehouse_id is not None
        }
        await self._lock_active_warehouses(warehouse_ids)

        balances: dict[uuid.UUID, Inventory | None] = {}
        for warehouse_id in sorted(warehouse_ids, key=str):
            balances[warehouse_id] = (
                await self.repository.get_inventory_for_update(
                    warehouse_id,
                    product_id,
                )
            )

        if source_warehouse_id is not None:
            source = balances[source_warehouse_id]
            if source is None:
                raise HTTPException(
                    status_code=422,
                    detail="Izvorna zaliha ne postoji",
                )
            new_on_hand = source.quantity_on_hand - quantity
            if new_on_hand < 0:
                raise HTTPException(
                    status_code=422,
                    detail="Nedovoljna količina na stanju",
                )
            if new_on_hand < source.quantity_reserved:
                raise HTTPException(
                    status_code=422,
                    detail="Promena bi ugrozila rezervisanu količinu",
                )
            source.quantity_on_hand = new_on_hand
            source.version += 1
            await self.repository.flush_balance(source)

        if destination_warehouse_id is not None:
            destination = balances[destination_warehouse_id]
            if destination is None:
                destination = Inventory(
                    warehouse_id=destination_warehouse_id,
                    product_id=product_id,
                    quantity_on_hand=quantity,
                )
                await self.repository.add_inventory(destination)
            else:
                destination.quantity_on_hand += quantity
                destination.version += 1
                await self.repository.flush_balance(destination)

    async def create_movement(
        self,
        data: InventoryMovementCreate,
    ) -> InventoryMovement:
        external_reference = self._normalize_optional(
            data.external_reference
        )
        if external_reference is not None:
            existing = (
                await self.repository.get_movement_by_external_reference(
                    external_reference
                )
            )
            if existing is not None:
                return self._existing_movement_or_conflict(existing, data)

        source_id, destination_id = self._movement_warehouses(
            data.movement_type,
            data.source_warehouse_id,
            data.destination_warehouse_id,
        )

        try:
            await self._lock_active_product(data.product_id)
            await self._apply_balance_changes(
                movement_type=data.movement_type,
                product_id=data.product_id,
                source_warehouse_id=source_id,
                destination_warehouse_id=destination_id,
                quantity=data.quantity,
            )
            movement = InventoryMovement(
                movement_number=self._movement_number(),
                movement_type=data.movement_type.value,
                product_id=data.product_id,
                source_warehouse_id=source_id,
                destination_warehouse_id=destination_id,
                quantity=data.quantity,
                reference_type=self._normalize_optional(
                    data.reference_type
                ),
                reference_id=self._normalize_optional(data.reference_id),
                external_reference=external_reference,
                note=self._normalize_optional(data.note),
                occurred_at=data.occurred_at,
                created_by=self._normalize_optional(data.created_by),
            )
            await self.repository.add_movement(movement)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            if external_reference is not None:
                existing = (
                    await self.repository.get_movement_by_external_reference(
                        external_reference
                    )
                )
                if existing is not None:
                    return self._existing_movement_or_conflict(
                        existing, data
                    )
            raise HTTPException(
                status_code=409,
                detail="Broj kretanja ili eksterna referenca već postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(movement)
        return movement

    async def reverse_movement(
        self,
        movement_id: uuid.UUID,
        *,
        created_by: str | None = None,
    ) -> InventoryMovement:
        now = datetime.now(UTC)
        try:
            original = await self.repository.get_movement_for_update(
                movement_id
            )
            if original is None:
                raise HTTPException(
                    status_code=404,
                    detail="Kretanje zaliha nije pronađeno",
                )
            if original.is_reversed:
                raise HTTPException(
                    status_code=409,
                    detail="Kretanje je već stornirano",
                )
            if original.reversal_movement_id is not None:
                raise HTTPException(
                    status_code=409,
                    detail="Storno kretanje se ne može ponovo stornirati",
                )

            movement_type = MovementType(original.movement_type)
            opposite = {
                MovementType.RECEIPT: MovementType.ADJUSTMENT_OUT,
                MovementType.ISSUE: MovementType.ADJUSTMENT_IN,
                MovementType.ADJUSTMENT_IN: MovementType.ADJUSTMENT_OUT,
                MovementType.ADJUSTMENT_OUT: MovementType.ADJUSTMENT_IN,
                MovementType.TRANSFER: MovementType.TRANSFER,
            }[movement_type]

            if movement_type == MovementType.TRANSFER:
                source_id = original.destination_warehouse_id
                destination_id = original.source_warehouse_id
            elif opposite in {
                MovementType.ADJUSTMENT_OUT,
                MovementType.ISSUE,
            }:
                source_id = original.destination_warehouse_id
                destination_id = None
            else:
                source_id = None
                destination_id = original.source_warehouse_id

            await self._lock_active_product(original.product_id)
            await self._apply_balance_changes(
                movement_type=opposite,
                product_id=original.product_id,
                source_warehouse_id=source_id,
                destination_warehouse_id=destination_id,
                quantity=original.quantity,
            )
            reversal = InventoryMovement(
                movement_number=self._movement_number(),
                movement_type=opposite.value,
                product_id=original.product_id,
                source_warehouse_id=source_id,
                destination_warehouse_id=destination_id,
                quantity=original.quantity,
                reference_type="REVERSAL",
                reference_id=str(original.id),
                note=f"Storno kretanja {original.movement_number}",
                occurred_at=now,
                created_by=self._normalize_optional(created_by),
                reversal_movement_id=original.id,
            )
            await self.repository.add_movement(reversal)
            await self.repository.mark_movement_reversed(
                original,
                reversed_at=now,
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Storno kretanje nije moglo biti sačuvano",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(reversal)
        return reversal

    async def get_reservation(
        self, reservation_id: uuid.UUID
    ) -> InventoryReservation:
        reservation = await self.repository.get_reservation(reservation_id)
        if reservation is None:
            raise HTTPException(
                status_code=404, detail="Rezervacija nije pronađena"
            )
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
            and reservation.reference_id
            == self._normalize_optional(data.reference_id)
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
        external_reference = self._normalize_optional(
            data.external_reference
        )
        if external_reference is not None:
            existing = (
                await self.repository.get_reservation_by_external_reference(
                    external_reference
                )
            )
            if existing is not None:
                return self._existing_reservation_or_conflict(
                    existing, data
                )
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
                reference_type=self._normalize_optional(
                    data.reference_type
                ),
                reference_id=self._normalize_optional(data.reference_id),
                note=self._normalize_optional(data.note),
                expires_at=data.expires_at,
            )
            await self.repository.add_reservation(reservation)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            if external_reference is not None:
                existing = (
                    await self.repository
                    .get_reservation_by_external_reference(
                        external_reference
                    )
                )
                if existing is not None:
                    return self._existing_reservation_or_conflict(
                        existing, data
                    )
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
            reservation = (
                await self.repository.get_reservation_for_update(
                    reservation_id
                )
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

    async def fulfill_reservation(
        self,
        reservation_id: uuid.UUID,
        data: InventoryReservationFulfill,
    ) -> InventoryReservation:
        external_reference = self._normalize_optional(
            data.external_reference
        )
        try:
            reservation = (
                await self.repository.get_reservation_for_update(
                    reservation_id
                )
            )
            if reservation is None:
                raise HTTPException(
                    status_code=404, detail="Rezervacija nije pronađena"
                )
            if external_reference is not None:
                existing = (
                    await self.repository.get_movement_by_external_reference(
                        external_reference
                    )
                )
                if existing is not None:
                    equivalent = (
                        existing.movement_type
                        == MovementType.ISSUE.value
                        and existing.product_id == reservation.product_id
                        and existing.source_warehouse_id
                        == reservation.warehouse_id
                        and existing.quantity == data.quantity
                        and existing.reference_type == "RESERVATION"
                        and existing.reference_id == str(reservation.id)
                    )
                    if not equivalent:
                        raise HTTPException(
                            status_code=409,
                            detail="Eksterna referenca pripada drugoj "
                            "realizaciji",
                        )
                    return reservation
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
            if (
                inventory is None
                or not inventory.is_active
                or inventory.quantity_reserved < data.quantity
                or inventory.quantity_on_hand < data.quantity
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Stanje zalihe nije dovoljno za realizaciju",
                )
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
                reservation.status = (
                    ReservationStatus.PARTIALLY_FULFILLED.value
                )
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
            if external_reference is not None:
                existing = (
                    await self.repository.get_movement_by_external_reference(
                        external_reference
                    )
                )
                persisted = await self.repository.get_reservation(
                    reservation_id
                )
                if (
                    existing is not None
                    and persisted is not None
                    and existing.movement_type == MovementType.ISSUE.value
                    and existing.product_id == persisted.product_id
                    and existing.source_warehouse_id
                    == persisted.warehouse_id
                    and existing.quantity == data.quantity
                    and existing.reference_type == "RESERVATION"
                    and existing.reference_id == str(persisted.id)
                ):
                    return persisted
            raise HTTPException(
                status_code=409,
                detail="Realizacija sa eksternom referencom već postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(reservation)
        return reservation

    async def expire_reservations(self, limit: int) -> tuple[int, int]:
        now = datetime.now(UTC)
        processed = 0
        skipped = 0
        try:
            reservations = (
                await self.repository.list_expired_reservations_for_update(
                    now, limit
                )
            )
            for reservation in reservations:
                inventory = await self.repository.get_inventory_for_update(
                    reservation.warehouse_id, reservation.product_id
                )
                remaining = reservation.remaining_quantity
                if (
                    inventory is None
                    or inventory.quantity_reserved < remaining
                ):
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
