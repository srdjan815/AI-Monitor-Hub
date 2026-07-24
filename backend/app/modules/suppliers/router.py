from fastapi import APIRouter

from app.modules.suppliers.contact_router import router as contact_router
from app.modules.suppliers.mapping_profile_router import (
    router as mapping_profile_router,
)
from app.modules.suppliers.mapping_rule_router import router as mapping_rule_router
from app.modules.suppliers.schema_field_router import router as schema_field_router
from app.modules.suppliers.schema_profile_router import router as schema_profile_router
from app.modules.suppliers.source_router import router as source_router
from app.modules.suppliers.supplier_router import router as supplier_router

router = APIRouter()
router.include_router(supplier_router)
router.include_router(contact_router)
router.include_router(source_router)
router.include_router(schema_profile_router)
router.include_router(schema_field_router)
router.include_router(mapping_profile_router)
router.include_router(mapping_rule_router)

__all__ = ["router"]
