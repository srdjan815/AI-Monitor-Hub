from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.suppliers.price_list_archive_schemas import (
    ArchivedPriceListItemPage,
    PriceListArchiveFilters,
    PriceListArchivePage,
)
from app.modules.suppliers.price_list_archive_service import PriceListArchiveService

router = APIRouter(
    prefix="/price-list-archive",
    tags=["supplier-price-list-archive"],
)


@router.get("/filters", response_model=PriceListArchiveFilters)
async def archive_filters(
    session: AsyncSession = Depends(get_db),
) -> PriceListArchiveFilters:
    return await PriceListArchiveService(session).filters()


@router.get("", response_model=PriceListArchivePage)
async def archived_price_lists(
    supplier_id: uuid.UUID | None = None,
    source_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = Query(None, max_length=500),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=MAX_LEGACY_OFFSET),
    session: AsyncSession = Depends(get_db),
) -> PriceListArchivePage:
    return await PriceListArchiveService(session).entries(
        supplier_id=supplier_id,
        source_id=source_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/{run_id}/items", response_model=ArchivedPriceListItemPage)
async def archived_price_list_items(
    run_id: uuid.UUID,
    search: str | None = Query(None, max_length=500),
    validation_status: str | None = Query(None, pattern="^(ACCEPTED|REJECTED)$"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0, le=MAX_LEGACY_OFFSET),
    session: AsyncSession = Depends(get_db),
) -> ArchivedPriceListItemPage:
    try:
        return await PriceListArchiveService(session).items(
            run_id,
            search=search,
            validation_status=validation_status,
            limit=limit,
            offset=offset,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


__all__ = ["router"]
