from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql import Select

from app.modules.suppliers.article_review_models import (
    SupplierArticleReview,
    SupplierArticleReviewEvent,
)
from app.modules.suppliers.delta_models import (
    SupplierDeltaFieldChange,
    SupplierDeltaItem,
    SupplierDeltaRun,
)
from app.modules.suppliers.models import Supplier, SupplierSource
from app.modules.suppliers.snapshot_models import SupplierSnapshotItem


ReviewRow = tuple[
    SupplierArticleReview,
    SupplierDeltaItem,
    SupplierSnapshotItem | None,
    SupplierSnapshotItem | None,
    str,
    str,
    str,
]


class SupplierArticleReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _detail_query(self) -> Select[Any]:
        previous = aliased(SupplierSnapshotItem)
        current = aliased(SupplierSnapshotItem)
        return (
            select(
                SupplierArticleReview,
                SupplierDeltaItem,
                previous,
                current,
                Supplier.company_name,
                SupplierSource.name,
                SupplierDeltaRun.delta_code,
            )
            .join(
                SupplierDeltaItem,
                SupplierDeltaItem.id == SupplierArticleReview.delta_item_id,
            )
            .join(
                SupplierDeltaRun,
                SupplierDeltaRun.id == SupplierArticleReview.delta_run_id,
            )
            .join(Supplier, Supplier.id == SupplierArticleReview.supplier_id)
            .join(
                SupplierSource,
                SupplierSource.id == SupplierArticleReview.source_connection_id,
            )
            .outerjoin(
                previous, previous.id == SupplierDeltaItem.previous_snapshot_item_id
            )
            .outerjoin(
                current, current.id == SupplierDeltaItem.current_snapshot_item_id
            )
        )

    async def list_reviews(
        self,
        *,
        supplier_id: uuid.UUID | None,
        source_id: uuid.UUID | None,
        status: str | None,
        issue_code: str | None,
        severity: str | None,
        product_code: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[ReviewRow], int]:
        filters = []
        for column, value in (
            (SupplierArticleReview.supplier_id, supplier_id),
            (SupplierArticleReview.source_connection_id, source_id),
            (SupplierArticleReview.status, status),
            (SupplierArticleReview.severity, severity),
        ):
            if value is not None:
                filters.append(column == value)
        if issue_code:
            filters.append(SupplierArticleReview.issue_codes.contains([issue_code]))
        if product_code:
            filters.append(
                SupplierArticleReview.product_code.ilike(f"%{product_code}%")
            )
        total = await self.session.scalar(
            select(func.count(SupplierArticleReview.id)).where(*filters)
        )
        rows = await self.session.execute(
            self._detail_query()
            .where(*filters)
            .order_by(
                SupplierArticleReview.opened_at.desc(), SupplierArticleReview.id.desc()
            )
            .limit(limit)
            .offset(offset)
        )
        return [cast(ReviewRow, tuple(row)) for row in rows.all()], int(total or 0)

    async def detail(
        self, review_id: uuid.UUID, *, lock: bool = False
    ) -> ReviewRow | None:
        query = self._detail_query().where(SupplierArticleReview.id == review_id)
        if lock:
            query = query.with_for_update(of=SupplierArticleReview)
        row = (await self.session.execute(query)).one_or_none()
        return cast(ReviewRow, tuple(row)) if row else None

    async def fields(self, delta_item_id: uuid.UUID) -> list[SupplierDeltaFieldChange]:
        rows = await self.session.execute(
            select(SupplierDeltaFieldChange)
            .where(SupplierDeltaFieldChange.delta_item_id == delta_item_id)
            .order_by(SupplierDeltaFieldChange.field_path, SupplierDeltaFieldChange.id)
        )
        return list(rows.scalars())

    async def events(
        self, review_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[SupplierArticleReviewEvent], int]:
        total = await self.session.scalar(
            select(func.count(SupplierArticleReviewEvent.id)).where(
                SupplierArticleReviewEvent.review_id == review_id
            )
        )
        rows = await self.session.execute(
            select(SupplierArticleReviewEvent)
            .where(SupplierArticleReviewEvent.review_id == review_id)
            .order_by(
                SupplierArticleReviewEvent.created_at, SupplierArticleReviewEvent.id
            )
            .limit(limit)
            .offset(offset)
        )
        return list(rows.scalars()), int(total or 0)

    async def pending_for_product(
        self, source_id: uuid.UUID, product_code: str
    ) -> list[SupplierArticleReview]:
        rows = await self.session.execute(
            select(SupplierArticleReview)
            .where(
                SupplierArticleReview.source_connection_id == source_id,
                SupplierArticleReview.product_code == product_code,
                SupplierArticleReview.status == "PENDING_REVIEW",
            )
            .with_for_update()
        )
        return list(rows.scalars())

    async def add_all(self, values: Sequence[object]) -> None:
        self.session.add_all(values)
        await self.session.flush()


__all__ = ["ReviewRow", "SupplierArticleReviewRepository"]
