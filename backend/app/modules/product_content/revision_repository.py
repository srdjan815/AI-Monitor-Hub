from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_, select

from app.modules.product_content.models import (
    ContentChangeEvent,
    DocumentReference,
    LandingPage,
    ProductContent,
    ProductSEO,
    VideoReference,
)
from app.modules.product_content.repository_support import ContentRepositorySupport


class RevisionRepository(ContentRepositorySupport):
    async def content_search(
        self,
        *,
        product_id: uuid.UUID | None,
        language_id: uuid.UUID | None,
        content_type_id: uuid.UUID | None,
        status: str | None,
        approval: str | None,
        source: str | None,
        offset: int,
        limit: int,
        snapshot_at: datetime | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> list[ProductContent]:
        query = select(ProductContent).where(ProductContent.is_current.is_(True))
        filters = (
            (ProductContent.product_id, product_id),
            (ProductContent.language_id, language_id),
            (ProductContent.content_type_id, content_type_id),
            (ProductContent.status, status),
            (ProductContent.approval_status, approval),
            (ProductContent.source_type, source),
        )
        for column, value in filters:
            if value is not None:
                query = query.where(column == value)
        if snapshot_at is not None:
            query = query.where(ProductContent.created_at <= snapshot_at)
        if after is not None:
            after_at, after_id = after
            query = query.where(
                or_(
                    ProductContent.created_at < after_at,
                    and_(
                        ProductContent.created_at == after_at,
                        ProductContent.id < after_id,
                    ),
                )
            )
        if snapshot_at is None and after is None:
            query = query.order_by(
                ProductContent.updated_at.desc(),
                ProductContent.id.desc(),
            )
        else:
            query = query.order_by(
                ProductContent.created_at.desc(),
                ProductContent.id.desc(),
            )
        return await self.all(query.offset(offset).limit(limit))

    async def content_revision(
        self,
        content_key: uuid.UUID,
        revision: int,
    ) -> ProductContent | None:
        return await self.one(
            select(ProductContent).where(
                ProductContent.content_key == content_key,
                ProductContent.revision == revision,
            )
        )

    async def current_content(
        self,
        content_key: uuid.UUID,
    ) -> ProductContent | None:
        return await self.one(
            select(ProductContent)
            .where(
                ProductContent.content_key == content_key,
                ProductContent.is_current.is_(True),
            )
            .with_for_update()
        )

    async def content_history(
        self,
        content_key: uuid.UUID,
    ) -> list[ProductContent]:
        return await self.all(
            select(ProductContent)
            .where(ProductContent.content_key == content_key)
            .order_by(ProductContent.revision.desc())
        )

    async def content_history_page(
        self,
        content_key: uuid.UUID,
        *,
        limit: int,
        after_revision: int | None,
        snapshot_revision: int | None,
    ) -> tuple[list[ProductContent], int]:
        rows, snapshot = await self._revision_page(
            ProductContent,
            ProductContent.content_key == content_key,
            limit=limit,
            after_revision=after_revision,
            snapshot_revision=snapshot_revision,
        )
        return rows, snapshot

    async def duplicate_content(self, digest: str) -> ProductContent | None:
        return await self.one(
            select(ProductContent).where(
                ProductContent.content_hash == digest,
                ProductContent.is_current.is_(True),
            )
        )

    async def references(
        self,
        model: type[Any],
        product_id: uuid.UUID | None,
        active_only: bool,
        *,
        offset: int = 0,
        limit: int = 100,
        snapshot_at: datetime | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> list[Any]:
        query = select(model)
        if product_id:
            query = query.where(model.product_id == product_id)
        if active_only:
            query = query.where(model.is_active.is_(True))
        if snapshot_at is not None:
            query = query.where(model.created_at <= snapshot_at)
        if after is not None:
            after_at, after_id = after
            query = query.where(
                or_(
                    model.created_at < after_at,
                    and_(
                        model.created_at == after_at,
                        model.id < after_id,
                    ),
                )
            )
        if snapshot_at is None and after is None:
            query = query.order_by(model.updated_at.desc(), model.id.desc())
        else:
            query = query.order_by(model.created_at.desc(), model.id.desc())
        return await self.all(query.offset(offset).limit(limit))

    async def revision_entities(
        self,
        model: type[Any],
        product_id: uuid.UUID | None,
        current_only: bool,
        *,
        offset: int = 0,
        limit: int = 100,
        snapshot_at: datetime | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> list[Any]:
        query = select(model)
        if product_id:
            query = query.where(model.product_id == product_id)
        if current_only:
            query = query.where(model.is_current.is_(True))
        if snapshot_at is not None:
            query = query.where(model.created_at <= snapshot_at)
        if after is not None:
            after_at, after_id = after
            query = query.where(
                or_(
                    model.created_at < after_at,
                    and_(
                        model.created_at == after_at,
                        model.id < after_id,
                    ),
                )
            )
        if snapshot_at is None and after is None:
            query = query.order_by(model.updated_at.desc(), model.id.desc())
        else:
            query = query.order_by(model.created_at.desc(), model.id.desc())
        return await self.all(query.offset(offset).limit(limit))

    async def revision_history(
        self,
        model: type[Any],
        key_column: Any,
        key: uuid.UUID,
    ) -> list[Any]:
        return await self.all(
            select(model).where(key_column == key).order_by(model.revision.desc())
        )

    async def revision_history_page(
        self,
        model: type[Any],
        key_column: Any,
        key: uuid.UUID,
        *,
        limit: int,
        after_revision: int | None,
        snapshot_revision: int | None,
    ) -> tuple[list[Any], int]:
        return await self._revision_page(
            model,
            key_column == key,
            limit=limit,
            after_revision=after_revision,
            snapshot_revision=snapshot_revision,
        )

    async def current_revision(
        self,
        model: type[Any],
        key_column: Any,
        key: uuid.UUID,
    ) -> Any | None:
        return await self.one(
            select(model).where(
                key_column == key,
                model.is_current.is_(True),
            )
        )

    async def related_by_value(
        self,
        model: type[Any],
        column: Any,
        value: str,
    ) -> list[Any]:
        return await self.all(select(model).where(column == value))

    async def export_product(self, product_id: uuid.UUID) -> dict[str, list[Any]]:
        queries: dict[str, Any] = {
            "content": select(ProductContent).where(
                ProductContent.product_id == product_id,
                ProductContent.is_current.is_(True),
            ),
            "seo": select(ProductSEO).where(
                ProductSEO.product_id == product_id,
                ProductSEO.is_current.is_(True),
            ),
            "landing_pages": select(LandingPage).where(
                LandingPage.product_id == product_id,
                LandingPage.is_current.is_(True),
            ),
            "documents": select(DocumentReference).where(
                DocumentReference.product_id == product_id,
                DocumentReference.is_active.is_(True),
            ),
            "videos": select(VideoReference).where(
                VideoReference.product_id == product_id,
                VideoReference.is_active.is_(True),
            ),
        }
        return {
            name: await self.all(
                query.order_by(query.column_descriptions[0]["entity"].id)
            )
            for name, query in queries.items()
        }

    async def changes(self, cursor: int, limit: int) -> list[ContentChangeEvent]:
        return await self.all(
            select(ContentChangeEvent)
            .where(ContentChangeEvent.cursor > cursor)
            .order_by(ContentChangeEvent.cursor)
            .limit(limit)
        )


__all__ = ["RevisionRepository"]
