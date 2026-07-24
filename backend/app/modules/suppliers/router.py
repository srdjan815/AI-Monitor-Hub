from fastapi import APIRouter

from app.modules.suppliers.contact_router import router as contact_router
from app.modules.suppliers.source_router import router as source_router
from app.modules.suppliers.supplier_router import router as supplier_router

router = APIRouter()
router.include_router(supplier_router)
router.include_router(contact_router)
router.include_router(source_router)

__all__ = ["router"]
