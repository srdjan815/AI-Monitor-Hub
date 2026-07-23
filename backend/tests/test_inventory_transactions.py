from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError

from app.modules.inventory.models import InventoryMovement
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.schemas import (
    InventoryCreate,
    InventoryMovementCreate,
    WarehouseCreate,
)
from app.modules.inventory.service import InventoryService


def persistence_error() -> IntegrityError:
    return IntegrityError("INSERT", {}, RuntimeError("forced failure"))


def service_with_mocks() -> tuple[
    InventoryService,
    AsyncMock,
    AsyncMock,
]:
    session = AsyncMock()
    service = InventoryService(session)
    repository = AsyncMock(spec=InventoryRepository)
    service.repository = repository
    return service, session, repository


@pytest.mark.asyncio
async def test_warehouse_create_rolls_back_on_failure() -> None:
    service, session, repository = service_with_mocks()
    repository.get_warehouse_by_code.return_value = None
    repository.create_warehouse.side_effect = persistence_error()

    with pytest.raises(HTTPException) as error:
        await service.create_warehouse(
            WarehouseCreate(code="rollback", name="Rollback Warehouse")
        )

    assert error.value.status_code == 409
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_inventory_create_rolls_back_on_failure() -> None:
    service, session, repository = service_with_mocks()
    repository.get_warehouse.return_value = SimpleNamespace()
    repository.get_product.return_value = SimpleNamespace()
    repository.get_inventory_by_pair.return_value = None
    repository.create_inventory.side_effect = persistence_error()

    with pytest.raises(HTTPException) as error:
        await service.create_inventory(
            InventoryCreate(
                warehouse_id="e2b00af1-c567-4c1d-b881-3d79fd165365",
                product_id="dfa50789-70ec-4c28-bc7d-db6f9c8d3da5",
                quantity_on_hand=10,
                quantity_reserved=2,
            )
        )

    assert error.value.status_code == 409
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_movement_rolls_back_when_balance_update_fails() -> None:
    service, session, repository = service_with_mocks()
    repository.get_product_for_update.return_value = SimpleNamespace(
        is_active=True
    )
    service._apply_balance_changes = AsyncMock(
        side_effect=RuntimeError("balance failure")
    )

    with pytest.raises(RuntimeError, match="balance failure"):
        await service.create_movement(
            InventoryMovementCreate(
                movement_type="RECEIPT",
                product_id="dfa50789-70ec-4c28-bc7d-db6f9c8d3da5",
                destination_warehouse_id=(
                    "e2b00af1-c567-4c1d-b881-3d79fd165365"
                ),
                quantity=1,
            )
        )

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
    repository.add_movement.assert_not_awaited()


@pytest.mark.asyncio
async def test_transfer_rolls_back_when_destination_update_fails() -> None:
    service, session, repository = service_with_mocks()
    repository.get_product_for_update.return_value = SimpleNamespace(
        is_active=True
    )
    service._apply_balance_changes = AsyncMock(
        side_effect=RuntimeError("destination failure")
    )

    with pytest.raises(RuntimeError, match="destination failure"):
        await service.create_movement(
            InventoryMovementCreate(
                movement_type="TRANSFER",
                product_id="dfa50789-70ec-4c28-bc7d-db6f9c8d3da5",
                source_warehouse_id=(
                    "e2b00af1-c567-4c1d-b881-3d79fd165365"
                ),
                destination_warehouse_id=(
                    "10655c30-d794-425c-bb44-8316b933e488"
                ),
                quantity=1,
            )
        )

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
    repository.add_movement.assert_not_awaited()


@pytest.mark.asyncio
async def test_balance_lookup_uses_row_locking() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    repository = InventoryRepository(session)

    await repository.get_inventory_for_update(uuid.uuid4(), uuid.uuid4())

    statement = session.execute.await_args.args[0]
    assert statement._for_update_arg is not None


def test_movement_number_has_database_uniqueness_constraint() -> None:
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in InventoryMovement.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("movement_number",) in unique_columns
