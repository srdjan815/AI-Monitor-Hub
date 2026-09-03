from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_CURSOR_CHARS, MAX_DB_INTEGER, MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.product_content.constants import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
)
from app.modules.product_content.models import ProductContent
from app.core.api_pagination import (
    require_cursor_mode,
    revision_page,
    time_page,
)
from app.modules.product_content.query_services import ContentQueryService
from app.modules.product_content.schemas import (
    ContentRead,
    ContentWrite,
    RollbackRequest,
    WorkflowRequest,
)
from app.modules.product_content.services import RevisionService

router = APIRouter()


@router.post(
    "/products/{product_id:uuid}/entries",
    response_model=ContentRead,
    status_code=201,
)
async def create_content(
    product_id: uuid.UUID,
    payload: ContentWrite,
    session: AsyncSession = Depends(get_db),
) -> ProductContent:
    return await RevisionService(session).create_content(product_id, payload)


@router.patch("/entries/{content_id:uuid}", response_model=ContentRead)
async def revise_content(
    content_id: uuid.UUID,
    payload: ContentWrite,
    session: AsyncSession = Depends(get_db),
) -> ProductContent:
    return await RevisionService(session).revise_content(content_id, payload)


@router.post("/entries/{content_id:uuid}/workflow", response_model=ContentRead)
async def workflow(
    content_id: uuid.UUID,
    payload: WorkflowRequest,
    session: AsyncSession = Depends(get_db),
) -> ProductContent:
    return await RevisionService(session).workflow(content_id, payload)


@router.get("/entries/{content_key:uuid}/history", response_model=list[ContentRead])
async def history(
    content_key: uuid.UUID,
    response: Response,
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    session: AsyncSession = Depends(get_db),
) -> list[ProductContent]:
    service = RevisionService(session)
    return await revision_page(
        response,
        cursor=cursor,
        resource="content.entry_history",
        filters={
            "content_key": str(content_key),
            "limit": limit,
            "order": "revision_desc",
        },
        limit=limit,
        loader=lambda page_limit, after, snapshot: service.history_page(
            content_key,
            limit=page_limit,
            after_revision=after,
            snapshot_revision=snapshot,
        ),
        revision_of=lambda row: row.revision,
    )


@router.post("/entries/{content_key:uuid}/rollback", response_model=ContentRead)
async def rollback(
    content_key: uuid.UUID,
    payload: RollbackRequest,
    session: AsyncSession = Depends(get_db),
) -> ProductContent:
    return await RevisionService(session).rollback(
        content_key, payload.revision, payload.actor
    )


@router.get("/entries", response_model=list[ContentRead])
async def search_content(
    response: Response,
    product_id: uuid.UUID | None = None,
    language_id: uuid.UUID | None = None,
    content_type_id: uuid.UUID | None = None,
    status: str | None = Query(default=None, max_length=32),
    approval: str | None = Query(default=None, max_length=32),
    source: str | None = Query(default=None, max_length=32),
    updated_from: str | None = Query(default=None, max_length=64),
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    pagination: Literal["offset", "cursor"] | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[ProductContent]:
    del updated_from
    service = ContentQueryService(session)
    filters = {
        "product_id": product_id,
        "language_id": language_id,
        "content_type_id": content_type_id,
        "status": status,
        "approval": approval,
        "source": source,
    }
    cursor_mode = cursor is not None or pagination == "cursor"
    if not cursor_mode:
        return await service.search_content(
            **filters,
            offset=offset,
            limit=limit,
        )

    require_cursor_mode(pagination=pagination, offset=offset)
    cursor_filters = {
        **filters,
        "limit": limit,
        "order": "created_at_desc,id_desc",
    }
    return await time_page(
        session,
        response,
        cursor=cursor,
        resource="content.entries",
        filters=cursor_filters,
        limit=limit,
        loader=lambda page_limit, snapshot_at, after: (
            service.search_content(
                **filters,
                offset=0,
                limit=page_limit,
                snapshot_at=snapshot_at,
                after=after,
            )
        ),
        timestamp_of=lambda row: row.created_at,
        id_of=lambda row: row.id,
    )


@router.get("/entries/{content_key:uuid}/diff")
async def content_diff(
    content_key: uuid.UUID,
    from_revision: int = Query(ge=1, le=MAX_DB_INTEGER),
    to_revision: int = Query(ge=1, le=MAX_DB_INTEGER),
    session: AsyncSession = Depends(get_db),
) -> dict:
    return await RevisionService(session).diff(content_key, from_revision, to_revision)
