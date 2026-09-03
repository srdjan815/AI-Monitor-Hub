from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.suppliers.article_review_schemas import (
    ArticleReviewDecision,
    ArticleReviewEventList,
    ArticleReviewList,
    ArticleReviewRead,
)
from app.modules.suppliers.article_review_service import SupplierArticleReviewService

router = APIRouter(prefix="/article-reviews", tags=["supplier-article-review-center"])


@router.get("", response_model=ArticleReviewList, summary="Lista kontrola artikala")
async def list_reviews(
    supplier_id: uuid.UUID | None = None,
    source_id: uuid.UUID | None = None,
    review_status: str | None = Query(default=None, alias="status", max_length=32),
    issue_code: str | None = Query(default=None, max_length=100),
    severity: str | None = Query(default=None, max_length=16),
    product_code: str | None = Query(default=None, max_length=500),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0, le=MAX_LEGACY_OFFSET),
    session: AsyncSession = Depends(get_db),
) -> ArticleReviewList:
    return await SupplierArticleReviewService(session).list_reviews(
        supplier_id=supplier_id,
        source_id=source_id,
        status=review_status,
        issue_code=issue_code,
        severity=severity,
        product_code=product_code,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{review_id}", response_model=ArticleReviewRead, summary="Detalji kontrole artikla"
)
async def get_review(
    review_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> ArticleReviewRead:
    return await SupplierArticleReviewService(session).get(review_id)


@router.get(
    "/{review_id}/events",
    response_model=ArticleReviewEventList,
    summary="Audit istorija kontrole",
)
async def review_events(
    review_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0, le=MAX_LEGACY_OFFSET),
    session: AsyncSession = Depends(get_db),
) -> ArticleReviewEventList:
    return await SupplierArticleReviewService(session).events(
        review_id, limit=limit, offset=offset
    )


@router.post(
    "/{review_id}/approve",
    response_model=ArticleReviewRead,
    summary="Pusti artikal dalje",
)
async def approve(
    review_id: uuid.UUID,
    payload: ArticleReviewDecision,
    session: AsyncSession = Depends(get_db),
) -> ArticleReviewRead:
    return await SupplierArticleReviewService(session).decide(
        review_id,
        approved=True,
        expected_version=payload.expected_version,
        comment=payload.comment,
    )


@router.post(
    "/{review_id}/reject", response_model=ArticleReviewRead, summary="Odbij artikal"
)
async def reject(
    review_id: uuid.UUID,
    payload: ArticleReviewDecision,
    session: AsyncSession = Depends(get_db),
) -> ArticleReviewRead:
    return await SupplierArticleReviewService(session).decide(
        review_id,
        approved=False,
        expected_version=payload.expected_version,
        comment=payload.comment,
    )


__all__ = ["router"]
