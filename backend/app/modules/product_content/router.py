from fastapi import APIRouter

from app.modules.product_content.routers import ROUTERS

router = APIRouter(prefix="/content", tags=["product-content"])

for child_router in ROUTERS:
    router.include_router(child_router)

__all__ = ["router"]
