from fastapi import APIRouter
from app.api.routes.health import router as health_router

# Create main API router
api_router = APIRouter()

# Include all route routers
api_router.include_router(health_router, prefix="/health", tags=["health"])