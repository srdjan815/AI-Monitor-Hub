from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_LEGACY_OFFSET, MAX_SEARCH_CHARS
from app.db.session import get_db
from app.modules.product_content.constants import (
    DEFAULT_PAGE_LIMIT,
    MAX_CHANGE_LIMIT,
    MAX_PAGE_LIMIT,
)
from app.modules.product_content.query_services import ContentQueryService

router = APIRouter()


@router.get("/products/{product_id:uuid}/export")
async def content_export(
    product_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await ContentQueryService(session).export(product_id)


@router.get("/changes")
async def content_changes(
    cursor: int = Query(
        default=0,
        ge=0,
        le=9_223_372_036_854_775_807,
    ),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_CHANGE_LIMIT),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    return await ContentQueryService(session).changes(cursor, limit)


@router.get("/search")
async def global_content_search(
    query: str = Query(min_length=1, max_length=MAX_SEARCH_CHARS),
    language_id: uuid.UUID | None = None,
    status: str | None = Query(default=None, max_length=32),
    approval: str | None = Query(default=None, max_length=32),
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await ContentQueryService(session).global_search(
        text=query,
        language_id=language_id,
        status=status,
        approval=approval,
        offset=offset,
        limit=limit,
    )
