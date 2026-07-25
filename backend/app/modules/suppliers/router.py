from fastapi import APIRouter

from app.modules.suppliers.contact_router import router as contact_router
from app.modules.suppliers.acquisition_execution_router import (
    router as acquisition_execution_router,
)
from app.modules.suppliers.acquisition_query_router import (
    router as acquisition_query_router,
)
from app.modules.suppliers.mapping_profile_router import (
    router as mapping_profile_router,
)
from app.modules.suppliers.mapping_rule_router import router as mapping_rule_router
from app.modules.suppliers.schema_field_router import router as schema_field_router
from app.modules.suppliers.schema_profile_router import router as schema_profile_router
from app.modules.suppliers.source_router import router as source_router
from app.modules.suppliers.snapshot_archive_router import (
    router as snapshot_archive_router,
)
from app.modules.suppliers.snapshot_execution_router import (
    router as snapshot_execution_router,
)
from app.modules.suppliers.snapshot_query_router import router as snapshot_query_router
from app.modules.suppliers.supplier_router import router as supplier_router
from app.modules.suppliers.delta_router import router as delta_router

router = APIRouter()
router.include_router(supplier_router)
router.include_router(contact_router)
router.include_router(source_router)
router.include_router(schema_profile_router)
router.include_router(schema_field_router)
router.include_router(mapping_profile_router)
router.include_router(mapping_rule_router)
router.include_router(acquisition_execution_router)
router.include_router(acquisition_query_router)
router.include_router(snapshot_execution_router)
router.include_router(snapshot_archive_router)
router.include_router(snapshot_query_router)
router.include_router(delta_router)

__all__ = ["router"]
