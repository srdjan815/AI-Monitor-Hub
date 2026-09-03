from fastapi import APIRouter, Depends
from app.api.routes.auth import router as auth_router, session_router
from app.api.routes.health import router as health_router
from app.core.security import authorize_request
from app.modules.execution.router import router as execution_router
from app.modules.catalog.router import router as catalog_router
from app.modules.inventory.router import router as inventory_router
from app.modules.product_content.router import router as product_content_router
from app.modules.suppliers.router import router as supplier_router

# Create main API router
api_router = APIRouter()

# Include all route routers
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(session_router)
protected = [Depends(authorize_request)]
api_router.include_router(auth_router, dependencies=protected)
api_router.include_router(execution_router, dependencies=protected)
api_router.include_router(catalog_router, dependencies=protected)
api_router.include_router(inventory_router, dependencies=protected)
api_router.include_router(product_content_router, dependencies=protected)
api_router.include_router(supplier_router, dependencies=protected)
