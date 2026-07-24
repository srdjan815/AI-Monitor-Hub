from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import and_, func, or_, select

from app.modules.product_content.models import (
    ContentLibraryItem,
    ContentLibraryRevision,
    ContentTemplate,
    ContentTemplateCondition,
    ContentTemplateItem,
    ProductContentTemplate,
    ProductLibraryReference,
)
from app.modules.product_content.repository_support import ContentRepositorySupport


class LibraryRepository(ContentRepositorySupport):
    async def library_items(
        self,
        *,
        kind: str | None,
        category: str | None,
        tag: str | None,
        active_only: bool,
        offset: int = 0,
        limit: int = 100,
        snapshot_at: datetime | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> list[ContentLibraryItem]:
        query = select(ContentLibraryItem)
        if kind:
            query = query.where(ContentLibraryItem.item_kind == kind)
        if category:
            query = query.where(ContentLibraryItem.category == category)
        if tag:
            query = query.where(ContentLibraryItem.tags.contains([tag]))
        if active_only:
            query = query.where(ContentLibraryItem.is_active.is_(True))
        if snapshot_at is not None:
            query = query.where(ContentLibraryItem.created_at <= snapshot_at)
        if after is not None:
            after_at, after_id = after
            query = query.where(
                or_(
                    ContentLibraryItem.created_at < after_at,
                    and_(
                        ContentLibraryItem.created_at == after_at,
                        ContentLibraryItem.id < after_id,
                    ),
                )
            )
        if snapshot_at is None and after is None:
            query = query.order_by(
                ContentLibraryItem.updated_at.desc(),
                ContentLibraryItem.id.desc(),
            )
        else:
            query = query.order_by(
                ContentLibraryItem.created_at.desc(),
                ContentLibraryItem.id.desc(),
            )
        return await self.all(query.offset(offset).limit(limit))

    async def library_item_for_update(
        self,
        item_id: uuid.UUID,
    ) -> ContentLibraryItem | None:
        return await self.one(
            select(ContentLibraryItem)
            .where(ContentLibraryItem.id == item_id)
            .with_for_update()
        )

    async def library_current_revision(
        self,
        item_id: uuid.UUID,
        language_id: uuid.UUID,
    ) -> ContentLibraryRevision | None:
        return await self.one(
            select(ContentLibraryRevision).where(
                ContentLibraryRevision.library_item_id == item_id,
                ContentLibraryRevision.language_id == language_id,
                ContentLibraryRevision.is_current.is_(True),
            )
        )

    async def next_library_revision(self, item_id: uuid.UUID) -> int:
        maximum = await self.one(
            select(func.max(ContentLibraryRevision.revision)).where(
                ContentLibraryRevision.library_item_id == item_id
            )
        )
        return int(maximum or 0) + 1

    async def library_history(
        self,
        item_id: uuid.UUID,
    ) -> list[ContentLibraryRevision]:
        return await self.all(
            select(ContentLibraryRevision)
            .where(ContentLibraryRevision.library_item_id == item_id)
            .order_by(ContentLibraryRevision.revision.desc())
        )

    async def library_history_page(
        self,
        item_id: uuid.UUID,
        *,
        limit: int,
        after_revision: int | None,
        snapshot_revision: int | None,
    ) -> tuple[list[ContentLibraryRevision], int]:
        rows, snapshot = await self._revision_page(
            ContentLibraryRevision,
            ContentLibraryRevision.library_item_id == item_id,
            limit=limit,
            after_revision=after_revision,
            snapshot_revision=snapshot_revision,
        )
        return rows, snapshot

    async def library_usage(
        self,
        item_id: uuid.UUID,
    ) -> list[ProductLibraryReference]:
        return await self.all(
            select(ProductLibraryReference).where(
                ProductLibraryReference.library_item_id == item_id,
                ProductLibraryReference.is_active.is_(True),
            )
        )

    async def templates(
        self,
        active_only: bool,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ContentTemplate]:
        query = select(ContentTemplate)
        if active_only:
            query = query.where(ContentTemplate.is_active.is_(True))
        return await self.all(
            query.order_by(ContentTemplate.name, ContentTemplate.id)
            .offset(offset)
            .limit(limit)
        )

    async def template_items(
        self,
        template_id: uuid.UUID,
    ) -> list[ContentTemplateItem]:
        return await self.all(
            select(ContentTemplateItem)
            .where(ContentTemplateItem.template_id == template_id)
            .order_by(ContentTemplateItem.sort_order)
        )

    async def template_conditions(
        self,
        item_ids: Sequence[uuid.UUID],
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[ContentTemplateCondition]:
        if not item_ids:
            return []
        query = (
            select(ContentTemplateCondition)
            .where(ContentTemplateCondition.template_item_id.in_(item_ids))
            .order_by(
                ContentTemplateCondition.template_item_id,
                ContentTemplateCondition.sort_order,
                ContentTemplateCondition.id,
            )
        )
        query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        return await self.all(query)

    async def template_render_rows(
        self,
        template_id: uuid.UUID,
        language_id: uuid.UUID,
    ) -> list[tuple[ContentTemplateItem, ContentLibraryRevision]]:
        result = await self.session.execute(
            select(ContentTemplateItem, ContentLibraryRevision)
            .join(
                ContentLibraryItem,
                ContentLibraryItem.id == ContentTemplateItem.library_item_id,
            )
            .join(
                ContentLibraryRevision,
                ContentLibraryRevision.library_item_id
                == ContentTemplateItem.library_item_id,
            )
            .where(
                ContentTemplateItem.template_id == template_id,
                ContentLibraryRevision.language_id == language_id,
                ContentLibraryRevision.is_current.is_(True),
                ContentLibraryRevision.is_visible.is_(True),
                ContentLibraryItem.is_active.is_(True),
            )
            .order_by(ContentTemplateItem.sort_order)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def template_usage(
        self,
        template_id: uuid.UUID,
    ) -> list[ProductContentTemplate]:
        return await self.all(
            select(ProductContentTemplate).where(
                ProductContentTemplate.template_id == template_id,
                ProductContentTemplate.is_active.is_(True),
            )
        )


__all__ = ["LibraryRepository"]
