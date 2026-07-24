from __future__ import annotations

import uuid

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import (
    AttributeDefinition,
    Category,
    CategoryAttribute,
)


class CategoryRepository:
    """Category hierarchy persistence and category initialization queries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_category(
        self,
        category_id: uuid.UUID,
    ) -> Category | None:
        return await self.session.get(Category, category_id)

    async def get_category_by_code(
        self,
        code: str,
    ) -> Category | None:
        result = await self.session.execute(
            select(Category).where(Category.code == code)
        )
        return result.scalar_one_or_none()

    async def list_categories(
        self,
        *,
        active_only: bool = True,
        parent_id: uuid.UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Category], int]:
        filters: list[ColumnElement[bool]] = []

        if active_only:
            filters.append(Category.is_active.is_(True))

        if parent_id is not None:
            filters.append(Category.parent_id == parent_id)

        query = select(Category).where(*filters)
        count_query = select(func.count(Category.id)).where(*filters)

        rows = await self.session.execute(
            query.order_by(
                Category.position,
                Category.name,
                Category.id,
            )
            .limit(limit)
            .offset(offset)
        )

        total = await self.session.scalar(count_query)

        return (
            list(rows.scalars().all()),
            int(total or 0),
        )

    async def list_all_categories(
        self,
        *,
        active_only: bool = True,
        limit: int | None = None,
    ) -> list[Category]:
        filters = []

        if active_only:
            filters.append(Category.is_active.is_(True))

        query = (
            select(Category)
            .where(*filters)
            .order_by(
                Category.position,
                Category.name,
                Category.id,
            )
        )
        if limit is not None:
            query = query.limit(limit)
        result = await self.session.execute(query)

        return list(result.scalars().all())

    async def create_category(
        self,
        category: Category,
    ) -> Category:
        self.session.add(category)
        await self.session.flush()
        return category

    async def update_category(
        self,
        category: Category,
        changes: dict[str, object],
    ) -> Category:
        for field, value in changes.items():
            setattr(category, field, value)

        await self.session.flush()
        return category

    async def deactivate_category(
        self,
        category: Category,
    ) -> Category:
        category.is_active = False
        category.version += 1
        await self.session.flush()
        return category

    async def link_all_global_attributes(
        self,
        category_id: uuid.UUID,
    ) -> None:
        result = await self.session.execute(
            select(AttributeDefinition)
            .where(
                AttributeDefinition.scope == "GLOBAL",
                AttributeDefinition.is_active.is_(True),
            )
            .order_by(
                AttributeDefinition.created_at,
                AttributeDefinition.name,
            )
        )

        attributes = list(result.scalars().all())

        for position, attribute in enumerate(attributes):
            self.session.add(
                CategoryAttribute(
                    category_id=category_id,
                    attribute_id=attribute.id,
                    position=position,
                    group_name="Op\u0161ti podaci",
                )
            )

        await self.session.flush()


__all__ = ["CategoryRepository"]
