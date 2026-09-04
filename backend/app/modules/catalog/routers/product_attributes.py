"""Stable product-attribute API façade composed from bounded route modules."""

from fastapi import APIRouter

from app.modules.catalog.routers.attribute_admin_routes import router as admin_router
from app.modules.catalog.routers.attribute_category_routes import (
    router as category_router,
)
from app.modules.catalog.routers.attribute_discovery_routes import (
    router as discovery_router,
)
from app.modules.catalog.routers.attribute_export_routes import router as export_router
from app.modules.catalog.routers.attribute_value_routes import router as value_router

router = APIRouter()
router.routes.extend(admin_router.routes)
router.routes.extend(category_router.routes)
router.routes.extend(value_router.routes)
router.routes.extend(discovery_router.routes)
router.routes.extend(export_router.routes)

__all__ = ["router"]
