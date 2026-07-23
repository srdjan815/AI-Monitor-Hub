from fastapi import APIRouter
from app.api.routes.health import router as health_router
from app.modules.execution.router import router as execution_router
from app.modules.catalog.router import router as catalog_router
from app.modules.inventory.router import router as inventory_router

# Create main API router
api_router = APIRouter()

# Include all route routers
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(execution_router)
api_router.include_router(catalog_router)
api_router.include_router(inventory_router)
