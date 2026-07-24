from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.modules.inventory.enums import MovementType, ReservationStatus
from app.modules.inventory.models import (
    Inventory,
    InventoryMovement,
    InventoryReservation,
)
from app.modules.inventory.reservation_service import ReservationService
from app.modules.inventory.schemas import (
    InventoryReservationCreate,
    InventoryReservationFulfill,
)


def persistence_error() -> IntegrityError:
    return IntegrityError("statement", {}, RuntimeError("forced constraint"))


def reservation_service() -> tuple[ReservationService, AsyncMock, AsyncMock]:
    session = AsyncMock()
    service = ReservationService(session)
    repository = AsyncMock()
    service.repository = repository
    service._lock_active_product = AsyncMock()  # type: ignore[method-assign]
    service._lock_active_warehouses = AsyncMock()  # type: ignore[method-assign]
    return service, session, repository


def balance(
    product_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    *,
    on_hand: int = 10,
    reserved: int = 5,
    active: bool = True,
) -> Inventory:
    return Inventory(
        id=uuid.uuid4(),
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity_on_hand=on_hand,
        quantity_reserved=reserved,
        minimum_stock=0,
        reorder_point=0,
        is_active=active,
        version=1,
    )


def reservation(
    product_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    *,
    quantity: int = 5,
    fulfilled: int = 0,
    status: ReservationStatus = ReservationStatus.ACTIVE,
    external_reference: str | None = None,
    reference_type: str | None = None,
    reference_id: str | None = None,
) -> InventoryReservation:
    return InventoryReservation(
        id=uuid.uuid4(),
        reservation_number=f"RES-{uuid.uuid4().hex[:12]}",
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity=quantity,
        fulfilled_quantity=fulfilled,
        status=status.value,
        external_reference=external_reference,
        reference_type=reference_type,
        reference_id=reference_id,
        note=None,
        expires_at=None,
        version=1,
    )


def reservation_payload(
    product_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    *,
    quantity: int = 5,
    external_reference: str | None = " reservation-key ",
) -> InventoryReservationCreate:
    return InventoryReservationCreate(
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity=quantity,
        external_reference=external_reference,
        reference_type=" order ",
        reference_id=" 42 ",
        note=" note ",
    )


def fulfillment_movement(
    entity: InventoryReservation,
    quantity: int,
    external_reference: str,
) -> InventoryMovement:
    return InventoryMovement(
        id=uuid.uuid4(),
        movement_number=f"MOV-{uuid.uuid4().hex[:12]}",
        movement_type=MovementType.ISSUE.value,
        product_id=entity.product_id,
        source_warehouse_id=entity.warehouse_id,
        destination_warehouse_id=None,
        quantity=quantity,
        reference_type="RESERVATION",
        reference_id=str(entity.id),
        external_reference=external_reference,
        occurred_at=datetime.now(UTC),
        version=1,
    )


@pytest.mark.asyncio
async def test_reservation_lookup_and_idempotency_payload_guards() -> None:
    product_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    data = reservation_payload(product_id, warehouse_id)
    service, _, repository = reservation_service()
    repository.get_reservation.return_value = None
    with pytest.raises(HTTPException) as missing:
        await service.get_reservation(uuid.uuid4())
    assert missing.value.status_code == 404

    entity = reservation(
        product_id,
        warehouse_id,
        external_reference="reservation-key",
        reference_type="order",
        reference_id="42",
    )
    repository.get_reservation.return_value = entity
    assert await service.get_reservation(entity.id) is entity
    assert service._reservation_payload_matches(entity, data)
    assert service._existing_reservation_or_conflict(entity, data) is entity

    conflicting = reservation_payload(product_id, warehouse_id, quantity=4)
    with pytest.raises(HTTPException) as conflict:
        service._existing_reservation_or_conflict(entity, conflicting)
    assert conflict.value.status_code == 409


@pytest.mark.asyncio
async def test_create_reservation_guardrails_and_success() -> None:
    product_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    data = reservation_payload(product_id, warehouse_id)
    existing = reservation(
        product_id,
        warehouse_id,
        external_reference="reservation-key",
        reference_type="order",
        reference_id="42",
    )
    service, session, repository = reservation_service()
    repository.get_reservation_by_external_reference.return_value = existing
    assert await service.create_reservation(data) is existing
    service._lock_active_product.assert_not_awaited()
    session.commit.assert_not_awaited()

    service, session, repository = reservation_service()
    repository.get_reservation_by_external_reference.return_value = reservation(
        product_id,
        warehouse_id,
        quantity=4,
        external_reference="reservation-key",
    )
    with pytest.raises(HTTPException) as conflict:
        await service.create_reservation(data)
    assert conflict.value.status_code == 409

    for inventory, detail in (
        (None, "ne postoji"),
        (balance(product_id, warehouse_id, active=False), "nije aktivna"),
        (balance(product_id, warehouse_id, on_hand=5, reserved=4), "Nedovoljna"),
    ):
        service, session, repository = reservation_service()
        repository.get_reservation_by_external_reference.return_value = None
        repository.get_inventory_for_update.return_value = inventory
        with pytest.raises(HTTPException, match=detail):
            await service.create_reservation(data)
        session.rollback.assert_awaited_once()
        session.commit.assert_not_awaited()

    service, session, repository = reservation_service()
    repository.get_reservation_by_external_reference.return_value = None
    inventory = balance(product_id, warehouse_id, on_hand=10, reserved=2)
    repository.get_inventory_for_update.return_value = inventory
    created = await service.create_reservation(data)
    assert inventory.quantity_reserved == 7
    assert inventory.version == 2
    assert created.external_reference == "reservation-key"
    assert created.reference_type == "order"
    assert created.reference_id == "42"
    assert created.note == "note"
    repository.flush_balance.assert_awaited_once_with(inventory)
    repository.add_reservation.assert_awaited_once_with(created)
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(created)


@pytest.mark.asyncio
async def test_create_reservation_integrity_race_and_generic_failure_rollback() -> None:
    product_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    data = reservation_payload(product_id, warehouse_id)
    matching = reservation(
        product_id,
        warehouse_id,
        external_reference="reservation-key",
        reference_type="order",
        reference_id="42",
    )

    service, session, repository = reservation_service()
    repository.get_reservation_by_external_reference.side_effect = [None, matching]
    repository.get_inventory_for_update.return_value = balance(
        product_id,
        warehouse_id,
        reserved=0,
    )
    repository.add_reservation.side_effect = persistence_error()
    assert await service.create_reservation(data) is matching
    session.rollback.assert_awaited_once()

    service, session, repository = reservation_service()
    repository.get_reservation_by_external_reference.side_effect = [None, None]
    repository.get_inventory_for_update.return_value = balance(
        product_id,
        warehouse_id,
        reserved=0,
    )
    repository.add_reservation.side_effect = persistence_error()
    with pytest.raises(HTTPException) as conflict:
        await service.create_reservation(data)
    assert conflict.value.status_code == 409
    session.rollback.assert_awaited_once()

    service, session, repository = reservation_service()
    repository.get_reservation_by_external_reference.return_value = None
    repository.get_inventory_for_update.return_value = balance(
        product_id,
        warehouse_id,
        reserved=0,
    )
    repository.flush_balance.side_effect = RuntimeError("balance failure")
    with pytest.raises(RuntimeError, match="balance failure"):
        await service.create_reservation(data)
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_release_cancel_and_finalize_invariant_guards() -> None:
    product_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    reservation_id = uuid.uuid4()

    service, session, repository = reservation_service()
    repository.get_reservation_for_update.return_value = None
    with pytest.raises(HTTPException) as missing:
        await service.release_reservation(reservation_id)
    assert missing.value.status_code == 404
    session.rollback.assert_awaited_once()

    service, session, repository = reservation_service()
    repository.get_reservation_for_update.return_value = reservation(
        product_id,
        warehouse_id,
        status=ReservationStatus.FULFILLED,
    )
    with pytest.raises(HTTPException) as finalized:
        await service.cancel_reservation(reservation_id)
    assert finalized.value.status_code == 409

    for inventory in (
        None,
        balance(product_id, warehouse_id, reserved=1),
    ):
        service, session, repository = reservation_service()
        entity = reservation(product_id, warehouse_id, quantity=5, fulfilled=2)
        repository.get_reservation_for_update.return_value = entity
        repository.get_inventory_for_update.return_value = inventory
        with pytest.raises(HTTPException) as inconsistent:
            await service.release_reservation(entity.id)
        assert inconsistent.value.status_code == 409
        session.rollback.assert_awaited_once()

    for target in (ReservationStatus.RELEASED, ReservationStatus.CANCELLED):
        service, session, repository = reservation_service()
        entity = reservation(product_id, warehouse_id, quantity=5, fulfilled=2)
        inventory = balance(product_id, warehouse_id, reserved=5)
        repository.get_reservation_for_update.return_value = entity
        repository.get_inventory_for_update.return_value = inventory
        if target is ReservationStatus.RELEASED:
            returned = await service.release_reservation(entity.id)
            assert entity.released_at is not None
        else:
            returned = await service.cancel_reservation(entity.id)
            assert entity.cancelled_at is not None
        assert returned is entity
        assert entity.status == target.value
        assert entity.version == 2
        assert inventory.quantity_reserved == 2
        assert inventory.version == 2
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once_with(entity)

    service, session, repository = reservation_service()
    entity = reservation(product_id, warehouse_id)
    repository.get_reservation_for_update.return_value = entity
    repository.get_inventory_for_update.return_value = balance(
        product_id,
        warehouse_id,
    )
    repository.flush_reservation.side_effect = RuntimeError("finalize failure")
    with pytest.raises(RuntimeError, match="finalize failure"):
        await service.release_reservation(entity.id)
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_fulfillment_matching_and_inventory_predicates() -> None:
    product_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    entity = reservation(product_id, warehouse_id)
    matching = fulfillment_movement(entity, 2, "fulfillment-key")
    assert ReservationService._matches_fulfillment(matching, entity, 2)
    matching.quantity = 3
    assert not ReservationService._matches_fulfillment(matching, entity, 2)

    assert not ReservationService._can_fulfill_inventory(None, 1)
    assert not ReservationService._can_fulfill_inventory(
        balance(product_id, warehouse_id, active=False),
        1,
    )
    assert not ReservationService._can_fulfill_inventory(
        balance(product_id, warehouse_id, on_hand=5, reserved=0),
        1,
    )
    assert not ReservationService._can_fulfill_inventory(
        balance(product_id, warehouse_id, on_hand=0, reserved=5),
        1,
    )
    assert ReservationService._can_fulfill_inventory(
        balance(product_id, warehouse_id, on_hand=5, reserved=5),
        1,
    )

    service, _, repository = reservation_service()
    assert await service._existing_fulfillment(entity, 2, None) is None
    repository.get_movement_by_external_reference.return_value = None
    assert await service._existing_fulfillment(entity, 2, "fulfillment-key") is None
    repository.get_movement_by_external_reference.return_value = fulfillment_movement(
        entity, 3, "fulfillment-key"
    )
    with pytest.raises(HTTPException) as conflict:
        await service._existing_fulfillment(entity, 2, "fulfillment-key")
    assert conflict.value.status_code == 409
    repository.get_movement_by_external_reference.return_value = fulfillment_movement(
        entity, 2, "fulfillment-key"
    )
    assert await service._existing_fulfillment(entity, 2, "fulfillment-key") is entity


@pytest.mark.asyncio
async def test_fulfill_reservation_guards_partial_and_complete_success() -> None:
    product_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    data = InventoryReservationFulfill(
        quantity=2,
        external_reference=" fulfillment-key ",
        note=" shipped ",
    )

    service, session, repository = reservation_service()
    repository.get_reservation_for_update.return_value = None
    with pytest.raises(HTTPException) as missing:
        await service.fulfill_reservation(uuid.uuid4(), data)
    assert missing.value.status_code == 404
    session.rollback.assert_awaited_once()

    service, session, repository = reservation_service()
    entity = reservation(product_id, warehouse_id)
    repository.get_reservation_for_update.return_value = entity
    service._existing_fulfillment = AsyncMock(return_value=entity)  # type: ignore[method-assign]
    assert await service.fulfill_reservation(entity.id, data) is entity
    session.commit.assert_not_awaited()

    service, session, repository = reservation_service()
    entity = reservation(
        product_id,
        warehouse_id,
        status=ReservationStatus.RELEASED,
    )
    repository.get_reservation_for_update.return_value = entity
    repository.get_movement_by_external_reference.return_value = None
    with pytest.raises(HTTPException) as finalized:
        await service.fulfill_reservation(entity.id, data)
    assert finalized.value.status_code == 409

    service, session, repository = reservation_service()
    entity = reservation(product_id, warehouse_id, quantity=2, fulfilled=1)
    repository.get_reservation_for_update.return_value = entity
    repository.get_movement_by_external_reference.return_value = None
    with pytest.raises(HTTPException) as excessive:
        await service.fulfill_reservation(entity.id, data)
    assert excessive.value.status_code == 422

    service, session, repository = reservation_service()
    entity = reservation(product_id, warehouse_id)
    repository.get_reservation_for_update.return_value = entity
    repository.get_movement_by_external_reference.return_value = None
    repository.get_inventory_for_update.return_value = None
    with pytest.raises(HTTPException) as unavailable:
        await service.fulfill_reservation(entity.id, data)
    assert unavailable.value.status_code == 409

    for fulfilled_before, expected_status in (
        (0, ReservationStatus.PARTIALLY_FULFILLED),
        (3, ReservationStatus.FULFILLED),
    ):
        service, session, repository = reservation_service()
        entity = reservation(
            product_id,
            warehouse_id,
            quantity=5,
            fulfilled=fulfilled_before,
        )
        inventory = balance(product_id, warehouse_id, on_hand=10, reserved=5)
        repository.get_reservation_for_update.return_value = entity
        repository.get_movement_by_external_reference.return_value = None
        repository.get_inventory_for_update.return_value = inventory
        returned = await service.fulfill_reservation(entity.id, data)
        assert returned is entity
        assert entity.status == expected_status.value
        assert entity.fulfilled_quantity == fulfilled_before + 2
        assert entity.version == 2
        assert inventory.quantity_on_hand == 8
        assert inventory.quantity_reserved == 3
        movement = repository.add_movement.await_args.args[0]
        assert movement.external_reference == "fulfillment-key"
        assert movement.note == "shipped"
        assert movement.reference_id == str(entity.id)
        if expected_status is ReservationStatus.FULFILLED:
            assert entity.fulfilled_at is not None
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once_with(entity)


@pytest.mark.asyncio
async def test_fulfillment_integrity_retry_and_failure_rollback() -> None:
    product_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    entity = reservation(product_id, warehouse_id)
    data = InventoryReservationFulfill(
        quantity=2,
        external_reference="fulfillment-key",
    )

    service, session, repository = reservation_service()
    repository.get_reservation_for_update.return_value = entity
    repository.get_movement_by_external_reference.side_effect = [None]
    repository.get_inventory_for_update.return_value = balance(
        product_id,
        warehouse_id,
    )
    repository.add_movement.side_effect = persistence_error()
    service._find_fulfillment_retry = AsyncMock(return_value=entity)  # type: ignore[method-assign]
    assert await service.fulfill_reservation(entity.id, data) is entity
    session.rollback.assert_awaited_once()

    service, session, repository = reservation_service()
    entity = reservation(product_id, warehouse_id)
    repository.get_reservation_for_update.return_value = entity
    repository.get_movement_by_external_reference.return_value = None
    repository.get_inventory_for_update.return_value = balance(
        product_id,
        warehouse_id,
    )
    repository.add_movement.side_effect = persistence_error()
    service._find_fulfillment_retry = AsyncMock(return_value=None)  # type: ignore[method-assign]
    with pytest.raises(HTTPException) as conflict:
        await service.fulfill_reservation(entity.id, data)
    assert conflict.value.status_code == 409

    service, session, repository = reservation_service()
    entity = reservation(product_id, warehouse_id)
    repository.get_reservation_for_update.return_value = entity
    repository.get_movement_by_external_reference.return_value = None
    repository.get_inventory_for_update.return_value = balance(
        product_id,
        warehouse_id,
    )
    repository.flush_balance.side_effect = RuntimeError("fulfillment failed")
    with pytest.raises(RuntimeError, match="fulfillment failed"):
        await service.fulfill_reservation(entity.id, data)
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_find_fulfillment_retry_and_expiry_batch_paths() -> None:
    product_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    entity = reservation(product_id, warehouse_id)
    service, _, repository = reservation_service()
    assert await service._find_fulfillment_retry(entity.id, 2, None) is None

    repository.get_movement_by_external_reference.return_value = fulfillment_movement(
        entity, 2, "fulfillment-key"
    )
    repository.get_reservation.return_value = entity
    assert (
        await service._find_fulfillment_retry(
            entity.id,
            2,
            "fulfillment-key",
        )
        is entity
    )
    repository.get_reservation.return_value = None
    assert (
        await service._find_fulfillment_retry(
            entity.id,
            2,
            "fulfillment-key",
        )
        is None
    )

    process = reservation(product_id, warehouse_id, quantity=4, fulfilled=1)
    process.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    skip_missing = reservation(product_id, warehouse_id, quantity=2)
    skip_inconsistent = reservation(product_id, warehouse_id, quantity=3)
    service, session, repository = reservation_service()
    repository.list_expired_reservations_for_update.return_value = [
        process,
        skip_missing,
        skip_inconsistent,
    ]
    inventory = balance(product_id, warehouse_id, reserved=5)
    repository.get_inventory_for_update.side_effect = [
        inventory,
        None,
        balance(product_id, warehouse_id, reserved=1),
    ]
    processed, skipped = await service.expire_reservations(limit=10)
    assert (processed, skipped) == (1, 2)
    assert process.status == ReservationStatus.EXPIRED.value
    assert process.version == 2
    assert inventory.quantity_reserved == 2
    session.commit.assert_awaited_once()

    service, session, repository = reservation_service()
    repository.list_expired_reservations_for_update.side_effect = RuntimeError(
        "expiry failed"
    )
    with pytest.raises(RuntimeError, match="expiry failed"):
        await service.expire_reservations(limit=10)
    session.rollback.assert_awaited_once()
