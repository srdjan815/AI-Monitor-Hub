from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.suppliers.eol_schemas import (
    EolBatchCreate,
    EolBatchRead,
    EolCandidateList,
)
from app.modules.suppliers.eol_service import SupplierEolService

router = APIRouter(prefix="/eol-products", tags=["supplier-eol-products"])


@router.get("", response_model=EolCandidateList, summary="EOL kandidati")
async def list_eol_products(
    inactivity_months: int = Query(6, ge=1, le=12),
    supplier_id: uuid.UUID | None = None,
    search: str | None = Query(None, max_length=500),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0, le=MAX_LEGACY_OFFSET),
    session: AsyncSession = Depends(get_db),
) -> EolCandidateList:
    return await SupplierEolService(session).list_candidates(
        inactivity_months=inactivity_months,
        supplier_id=supplier_id,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/deactivation-batches",
    response_model=EolBatchRead,
    status_code=201,
    summary="Pripremi deaktivaciju",
)
async def prepare_deactivation(
    payload: EolBatchCreate, session: AsyncSession = Depends(get_db)
) -> EolBatchRead:
    return await SupplierEolService(session).prepare_batch(payload)


__all__ = ["router"]
