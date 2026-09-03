from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.core.security import current_actor_id
from app.modules.inventory.enums import MovementType
from app.modules.inventory.inventory_service_support import InventoryServiceSupport
from app.modules.inventory.models import InventoryMovement
from app.modules.inventory.schemas import InventoryMovementCreate


class InventoryMovementService(InventoryServiceSupport):
    """Atomic stock movement creation, balance application, and reversal."""

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

    def _movement_payload_matches(
        self,
        movement: InventoryMovement,
        data: InventoryMovementCreate,
    ) -> bool:
        return (
            movement.movement_type == data.movement_type.value
            and movement.product_id == data.product_id
            and movement.source_warehouse_id == data.source_warehouse_id
            and movement.destination_warehouse_id == data.destination_warehouse_id
            and movement.quantity == data.quantity
            and movement.reference_type == self._normalize_optional(data.reference_type)
            and movement.reference_id == self._normalize_optional(data.reference_id)
            and movement.note == self._normalize_optional(data.note)
            and movement.created_by
            == (current_actor_id() or self._normalize_optional(data.created_by))
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
        if destination_required != (destination_warehouse_id is not None):
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

    async def create_movement(
        self,
        data: InventoryMovementCreate,
    ) -> InventoryMovement:
        external_reference = self._normalize_optional(data.external_reference)
        if external_reference is not None:
            existing = await self.repository.get_movement_by_external_reference(
                external_reference
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
                reference_type=self._normalize_optional(data.reference_type),
                reference_id=self._normalize_optional(data.reference_id),
                external_reference=external_reference,
                note=self._normalize_optional(data.note),
                occurred_at=data.occurred_at,
                created_by=current_actor_id()
                or self._normalize_optional(data.created_by),
            )
            await self.repository.add_movement(movement)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            if external_reference is not None:
                existing = await self.repository.get_movement_by_external_reference(
                    external_reference
                )
                if existing is not None:
                    return self._existing_movement_or_conflict(existing, data)
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
            original = await self.repository.get_movement_for_update(movement_id)
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
                created_by=current_actor_id() or self._normalize_optional(created_by),
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
