from __future__ import annotations

import ast
import inspect
from pathlib import Path
from unittest.mock import MagicMock

from app.modules.inventory.balance_repository import (
    WarehouseBalanceRepository,
)
from app.modules.inventory.balance_service import WarehouseBalanceService
from app.modules.inventory.movement_repository import MovementRepository
from app.modules.inventory.movement_service import InventoryMovementService
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.reservation_repository import (
    ReservationRepository,
)
from app.modules.inventory.reservation_service import ReservationService
from app.modules.inventory.service import InventoryService


INVENTORY_ROOT = Path(__file__).resolve().parents[1] / "app" / "modules" / "inventory"
PUBLIC_METHODS = {
    "cancel_reservation",
    "create_inventory",
    "create_movement",
    "create_reservation",
    "create_warehouse",
    "deactivate_inventory",
    "deactivate_warehouse",
    "expire_reservations",
    "fulfill_reservation",
    "get_inventory",
    "get_movement",
    "get_reservation",
    "get_warehouse",
    "release_reservation",
    "reverse_movement",
    "update_inventory",
    "update_warehouse",
}


def _public_coroutines(model: type[object]) -> set[str]:
    return {
        name
        for name, member in inspect.getmembers(
            model,
            predicate=inspect.iscoroutinefunction,
        )
        if not name.startswith("_")
    }


def test_inventory_service_facade_preserves_public_surface() -> None:
    assert _public_coroutines(InventoryService) == PUBLIC_METHODS
    assert {
        "create_warehouse",
        "update_warehouse",
        "create_inventory",
        "update_inventory",
    } <= _public_coroutines(WarehouseBalanceService)
    assert {
        "create_movement",
        "reverse_movement",
    } <= _public_coroutines(InventoryMovementService)
    assert {
        "create_reservation",
        "release_reservation",
        "cancel_reservation",
        "fulfill_reservation",
    } <= _public_coroutines(ReservationService)


def test_inventory_facades_share_one_session_context() -> None:
    session = MagicMock()
    service = InventoryService(session)
    repository = InventoryRepository(session)
    assert service.session is session
    assert service.repository.session is session
    assert repository.session is session


def test_inventory_repository_responsibilities_are_disjoint() -> None:
    assert hasattr(WarehouseBalanceRepository, "flush_balance")
    assert not hasattr(WarehouseBalanceRepository, "add_movement")
    assert not hasattr(WarehouseBalanceRepository, "add_reservation")
    assert hasattr(MovementRepository, "add_movement")
    assert not hasattr(MovementRepository, "flush_balance")
    assert hasattr(ReservationRepository, "add_reservation")
    assert not hasattr(ReservationRepository, "add_movement")


def test_inventory_repositories_remain_flush_only() -> None:
    for path in (
        INVENTORY_ROOT / "balance_repository.py",
        INVENTORY_ROOT / "movement_repository.py",
        INVENTORY_ROOT / "reservation_repository.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        forbidden = [
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"commit", "rollback"}
        ]
        assert forbidden == [], path.name
