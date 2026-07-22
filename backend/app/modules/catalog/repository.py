from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.catalog.models import (
    AttributeDefinition,
    Category,
    CategoryAttribute,
)


class CatalogRepository:
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
        filters = []

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
    ) -> list[Category]:
        filters = []

        if active_only:
            filters.append(Category.is_active.is_(True))

        result = await self.session.execute(
            select(Category)
            .where(*filters)
            .order_by(
                Category.position,
                Category.name,
            )
        )

        return list(result.scalars().all())

    async def create_category(
        self,
        category: Category,
    ) -> Category:
        self.session.add(category)
        await self.session.flush()
        return category

    async def get_attribute(
        self,
        attribute_id: uuid.UUID,
    ) -> AttributeDefinition | None:
        return await self.session.get(
            AttributeDefinition,
            attribute_id,
        )

    async def get_attribute_by_code(
        self,
        code: str,
    ) -> AttributeDefinition | None:
        result = await self.session.execute(
            select(AttributeDefinition).where(
                AttributeDefinition.code == code
            )
        )
        return result.scalar_one_or_none()

    async def list_attributes(
        self,
        *,
        scope: str | None = None,
        active_only: bool = True,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[AttributeDefinition], int]:
        filters = []

        if scope:
            filters.append(AttributeDefinition.scope == scope)

        if active_only:
            filters.append(AttributeDefinition.is_active.is_(True))

        query = select(AttributeDefinition).where(*filters)
        count_query = select(
            func.count(AttributeDefinition.id)
        ).where(*filters)

        rows = await self.session.execute(
            query.order_by(AttributeDefinition.name)
            .limit(limit)
            .offset(offset)
        )

        total = await self.session.scalar(count_query)

        return (
            list(rows.scalars().all()),
            int(total or 0),
        )

    async def create_attribute(
        self,
        attribute: AttributeDefinition,
    ) -> AttributeDefinition:
        self.session.add(attribute)
        await self.session.flush()
        return attribute

    async def link_attribute(
        self,
        *,
        category_id: uuid.UUID,
        attribute_id: uuid.UUID,
        position: int,
        group_name: str | None = None,
    ) -> CategoryAttribute:
        link = CategoryAttribute(
            category_id=category_id,
            attribute_id=attribute_id,
            position=position,
            group_name=group_name,
        )

        self.session.add(link)
        await self.session.flush()

        return link

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
                    group_name="Opšti podaci",
                )
            )

        await self.session.flush()

    async def link_global_attribute_to_all_categories(
        self,
        attribute_id: uuid.UUID,
    ) -> None:
        result = await self.session.execute(
            select(Category.id).where(
                Category.is_active.is_(True)
            )
        )

        category_ids = list(result.scalars().all())

        for category_id in category_ids:
            max_position = await self.session.scalar(
                select(
                    func.max(CategoryAttribute.position)
                ).where(
                    CategoryAttribute.category_id == category_id
                )
            )

            self.session.add(
                CategoryAttribute(
                    category_id=category_id,
                    attribute_id=attribute_id,
                    position=int(max_position or -1) + 1,
                    group_name="Opšti podaci",
                )
            )

        await self.session.flush()

    async def list_category_attributes(
        self,
        category_id: uuid.UUID,
        *,
        active_only: bool = True,
    ) -> list[CategoryAttribute]:
        filters = [
            CategoryAttribute.category_id == category_id
        ]

        if active_only:
            filters.extend(
                [
                    CategoryAttribute.is_active.is_(True),
                    AttributeDefinition.is_active.is_(True),
                ]
            )

        result = await self.session.execute(
            select(CategoryAttribute)
            .join(CategoryAttribute.attribute)
            .options(
                selectinload(CategoryAttribute.attribute)
            )
            .where(*filters)
            .order_by(
                CategoryAttribute.position,
                AttributeDefinition.name,
            )
        )

        return list(result.scalars().all())

    async def get_category_attribute(
        self,
        category_id: uuid.UUID,
        attribute_id: uuid.UUID,
    ) -> CategoryAttribute | None:
        result = await self.session.execute(
            select(CategoryAttribute).where(
                CategoryAttribute.category_id == category_id,
                CategoryAttribute.attribute_id == attribute_id,
            )
        )

        return result.scalar_one_or_none()