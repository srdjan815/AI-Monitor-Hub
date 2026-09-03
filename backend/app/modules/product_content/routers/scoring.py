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
from app.core.api_pagination import (
    require_cursor_mode,
    time_page,
)
from app.modules.product_content.query_services import ScoringService
from app.modules.product_content.schemas import ScoringPolicyWrite
from app.modules.product_content.services import serialize

router = APIRouter()


@router.get("/products/{product_id:uuid}/score")
async def content_score(
    product_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await ScoringService(session).content_score(product_id)


@router.post("/scoring-policies", status_code=201)
async def create_scoring_policy(
    payload: ScoringPolicyWrite,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(await ScoringService(session).create_policy(payload))


@router.get("/scoring-policies")
async def list_scoring_policies(
    active_only: bool = True,
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = await ScoringService(session).policies(
        active_only,
        offset=offset,
        limit=limit,
    )
    return [serialize(row) for row in rows]


@router.post("/products/{product_id:uuid}/score/{policy_id:uuid}")
async def weighted_content_score(
    product_id: uuid.UUID,
    policy_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await ScoringService(session).weighted_score(product_id, policy_id)


@router.post("/products/{product_id:uuid}/seo/{seo_id:uuid}/score")
async def seo_score(
    product_id: uuid.UUID,
    seo_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await ScoringService(session).seo_score(product_id, seo_id)


@router.get("/products/{product_id:uuid}/score-history")
async def score_history(
    product_id: uuid.UUID,
    response: Response,
    score_type: str | None = Query(default=None, max_length=20),
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    pagination: Literal["offset", "cursor"] | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    service = ScoringService(session)
    cursor_mode = cursor is not None or pagination == "cursor"
    if not cursor_mode:
        rows = await service.history(
            product_id,
            score_type,
            offset=offset,
            limit=limit,
        )
        return [serialize(row) for row in rows]

    require_cursor_mode(pagination=pagination, offset=offset)
    filters = {
        "product_id": str(product_id),
        "score_type": score_type,
        "limit": limit,
        "order": "calculated_at_desc,id_desc",
    }
    rows = await time_page(
        session,
        response,
        cursor=cursor,
        resource="content.score_history",
        filters=filters,
        limit=limit,
        loader=lambda page_limit, snapshot_at, after: service.history(
            product_id,
            score_type,
            offset=0,
            limit=page_limit,
            snapshot_at=snapshot_at,
            after=after,
        ),
        timestamp_of=lambda row: row.calculated_at,
        id_of=lambda row: row.id,
    )
    return [serialize(row) for row in rows]
