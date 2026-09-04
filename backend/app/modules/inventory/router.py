"""Stable inventory API façade composed from bounded route modules."""

from fastapi import APIRouter

from app.modules.inventory.inventory_routes import router as inventory_router
from app.modules.inventory.inventory_item_routes import router as inventory_item_router
from app.modules.inventory.movement_routes import router as movement_router
from app.modules.inventory.reservation_routes import router as reservation_router
from app.modules.inventory.warehouse_routes import router as warehouse_router

router = APIRouter(tags=["inventory"])
router.routes.extend(warehouse_router.routes)
router.routes.extend(inventory_router.routes)
router.routes.extend(movement_router.routes)
router.routes.extend(reservation_router.routes)
router.routes.extend(inventory_item_router.routes)

__all__ = ["router"]
