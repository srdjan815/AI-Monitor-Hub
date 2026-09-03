from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_CURSOR_CHARS, MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.product_content.constants import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
)
from app.modules.product_content.models import LandingPage
from app.core.api_pagination import (
    require_cursor_mode,
    revision_page,
    time_page,
)
from app.modules.product_content.schemas import LandingWrite, RollbackRequest
from app.modules.product_content.services import ReferenceService, serialize

router = APIRouter()


@router.post("/products/{product_id:uuid}/landing-pages", status_code=201)
async def create_landing(
    product_id: uuid.UUID,
    payload: LandingWrite,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = await ReferenceService(session).create_landing(product_id, payload)
    return {"id": row.id, "slug": row.slug, "revision": row.revision}


@router.get("/landing-pages")
async def list_landing_pages(
    response: Response,
    product_id: uuid.UUID | None = None,
    current_only: bool = True,
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    pagination: Literal["offset", "cursor"] | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    service = ReferenceService(session)
    cursor_mode = cursor is not None or pagination == "cursor"
    if not cursor_mode:
        rows = await service.list_revisions(
            "landing",
            product_id,
            current_only,
            offset=offset,
            limit=limit,
        )
        return [serialize(row) for row in rows]

    require_cursor_mode(pagination=pagination, offset=offset)
    filters = {
        "product_id": str(product_id) if product_id else None,
        "current_only": current_only,
        "limit": limit,
        "order": "created_at_desc,id_desc",
    }
    rows = await time_page(
        session,
        response,
        cursor=cursor,
        resource="content.landing_pages",
        filters=filters,
        limit=limit,
        loader=lambda page_limit, snapshot_at, after: service.list_revisions(
            "landing",
            product_id,
            current_only,
            offset=0,
            limit=page_limit,
            snapshot_at=snapshot_at,
            after=after,
        ),
        timestamp_of=lambda row: row.created_at,
        id_of=lambda row: row.id,
    )
    return [serialize(row) for row in rows]


@router.get("/landing-pages/{page_id:uuid}")
async def get_landing_page(
    page_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(
        await ReferenceService(session).required(LandingPage, page_id, "Landing page")
    )


@router.patch("/landing-pages/{page_id:uuid}", status_code=201)
async def revise_landing_page(
    page_id: uuid.UUID,
    payload: LandingWrite,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(await ReferenceService(session).revise_landing(page_id, payload))


@router.delete("/landing-pages/{page_id:uuid}")
async def delete_landing_page(
    page_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(
        await ReferenceService(session).deactivate_revision("landing", page_id)
    )


@router.get("/landing-pages/{landing_key:uuid}/history")
async def landing_history(
    landing_key: uuid.UUID,
    response: Response,
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    service = ReferenceService(session)
    rows = await revision_page(
        response,
        cursor=cursor,
        resource="content.landing_history",
        filters={
            "landing_key": str(landing_key),
            "limit": limit,
            "order": "revision_desc",
        },
        limit=limit,
        loader=lambda page_limit, after, snapshot: (
            service.revision_history_page(
                "landing",
                landing_key,
                limit=page_limit,
                after_revision=after,
                snapshot_revision=snapshot,
            )
        ),
        revision_of=lambda row: row.revision,
    )
    return [serialize(row) for row in rows]


@router.post("/landing-pages/{landing_key:uuid}/rollback", status_code=201)
async def rollback_landing_page(
    landing_key: uuid.UUID,
    payload: RollbackRequest,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(
        await ReferenceService(session).rollback_revision(
            "landing", landing_key, payload.revision
        )
    )
