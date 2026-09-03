from __future__ import annotations

import builtins
import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.modules.catalog.models import Product
from app.modules.catalog.utils import stable_code
from app.modules.product_content.models import (
    ContentLibraryItem,
    ContentLibraryRevision,
    Language,
    ProductLibraryReference,
)
from app.modules.product_content.schemas import (
    LibraryUpdate,
    LibraryWrite,
)

from app.modules.product_content.service_support import (
    ServiceBase,
)


class LibraryService(ServiceBase):
    async def create(self, data: LibraryWrite) -> ContentLibraryItem:
        await self.required(Language, data.language_id, "Language")
        item = ContentLibraryItem(
            name=data.name,
            slug=stable_code(data.slug or data.name),
            item_kind=data.item_kind,
            category=data.category,
            tags=data.tags,
            description=data.description,
        )
        try:
            await self.repository.add(item)
            await self.repository.add(
                ContentLibraryRevision(
                    library_item_id=item.id,
                    language_id=data.language_id,
                    revision=1,
                    title=data.title,
                    content=data.content,
                )
            )
            return await self.commit(item)
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409, detail="Content constraint conflict"
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

    async def list(
        self,
        kind: str | None,
        category: str | None,
        tag: str | None,
        active_only: bool,
        *,
        offset: int,
        limit: int,
        snapshot_at: datetime | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> list[ContentLibraryItem]:
        return await self.repository.library_items(
            kind=kind,
            category=category,
            tag=tag,
            active_only=active_only,
            offset=offset,
            limit=limit,
            snapshot_at=snapshot_at,
            after=after,
        )

    async def get(self, item_id: uuid.UUID) -> ContentLibraryItem:
        return await self.required(ContentLibraryItem, item_id, "Library item")

    async def update(
        self,
        item_id: uuid.UUID,
        data: LibraryUpdate,
    ) -> ContentLibraryItem:
        entity = await self.get(item_id)
        changed = False
        for field, value in data.model_dump(exclude_unset=True).items():
            if getattr(entity, field) != value:
                setattr(entity, field, value)
                changed = True
        if changed:
            entity.version += 1
        return await self.commit(entity)

    async def revise(
        self,
        item_id: uuid.UUID,
        data: LibraryWrite,
    ) -> ContentLibraryRevision:
        item = await self.get(item_id)
        current = await self.repository.library_current_revision(
            item_id, data.language_id
        )
        if current:
            current.is_current = False
        entity = ContentLibraryRevision(
            library_item_id=item_id,
            language_id=data.language_id,
            revision=await self.repository.next_library_revision(item_id),
            title=data.title,
            content=data.content,
        )
        item.version += 1
        return await self.mutate(entity)

    async def history(
        self,
        item_id: uuid.UUID,
    ) -> builtins.list[ContentLibraryRevision]:
        await self.get(item_id)
        return await self.repository.library_history(item_id)

    async def history_page(
        self,
        item_id: uuid.UUID,
        *,
        limit: int,
        after_revision: int | None,
        snapshot_revision: int | None,
    ) -> tuple[builtins.list[ContentLibraryRevision], int]:
        await self.get(item_id)
        return await self.repository.library_history_page(
            item_id,
            limit=limit,
            after_revision=after_revision,
            snapshot_revision=snapshot_revision,
        )

    async def deactivate(self, item_id: uuid.UUID) -> ContentLibraryItem:
        entity = await self.repository.library_item_for_update(item_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="Library item not found")
        entity.is_active = False
        return await self.commit(entity)

    async def assign(
        self,
        product_id: uuid.UUID,
        item_id: uuid.UUID,
        order: int,
    ) -> ProductLibraryReference:
        await self.required(Product, product_id, "Product")
        item = await self.repository.library_item_for_update(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Library item not found")
        if not item.is_active:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Inactive library item cannot be assigned",
            )
        return await self.mutate(
            ProductLibraryReference(
                product_id=product_id,
                library_item_id=item_id,
                sort_order=order,
            )
        )

    async def usage(self, item_id: uuid.UUID) -> dict[str, Any]:
        await self.get(item_id)
        rows = await self.repository.library_usage(item_id)
        return {
            "item_id": item_id,
            "usage_count": len(rows),
            "products": [row.product_id for row in rows],
            "last_usage": max((row.updated_at for row in rows), default=None),
        }
