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


class LegacyAttributeRepository:
    """Persistence for legacy attributes and the Attribute Type API façade."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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
            select(AttributeDefinition).where(AttributeDefinition.code == code)
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
        count_query = select(func.count(AttributeDefinition.id)).where(*filters)

        rows = await self.session.execute(
            query.order_by(
                AttributeDefinition.name,
                AttributeDefinition.id,
            )
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

    async def update_attribute(
        self,
        attribute: AttributeDefinition,
        changes: dict[str, object],
    ) -> AttributeDefinition:
        for field, value in changes.items():
            setattr(attribute, field, value)

        await self.session.flush()
        return attribute

    async def get_attribute_type(
        self,
        attribute_type_id: uuid.UUID,
    ) -> AttributeDefinition | None:
        return await self.get_attribute(attribute_type_id)

    async def get_attribute_type_by_code(
        self,
        code: str,
    ) -> AttributeDefinition | None:
        return await self.get_attribute_by_code(code)

    async def list_attribute_types(
        self,
        *,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AttributeDefinition], int]:
        return await self.list_attributes(
            active_only=active_only,
            limit=limit,
            offset=offset,
        )

    async def create_attribute_type(
        self,
        attribute_type: AttributeDefinition,
    ) -> AttributeDefinition:
        return await self.create_attribute(attribute_type)

    async def update_attribute_type(
        self,
        attribute_type: AttributeDefinition,
        changes: dict[str, object],
    ) -> AttributeDefinition:
        for field, value in changes.items():
            setattr(attribute_type, field, value)

        await self.session.flush()
        return attribute_type

    async def deactivate_attribute_type(
        self,
        attribute_type: AttributeDefinition,
    ) -> AttributeDefinition:
        attribute_type.is_active = False
        attribute_type.version += 1
        await self.session.flush()
        return attribute_type

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

    async def link_global_attribute_to_all_categories(
        self,
        attribute_id: uuid.UUID,
    ) -> None:
        result = await self.session.execute(
            select(Category.id).where(Category.is_active.is_(True))
        )

        category_ids = list(result.scalars().all())

        for category_id in category_ids:
            max_position = await self.session.scalar(
                select(func.max(CategoryAttribute.position)).where(
                    CategoryAttribute.category_id == category_id
                )
            )

            self.session.add(
                CategoryAttribute(
                    category_id=category_id,
                    attribute_id=attribute_id,
                    position=int(max_position or -1) + 1,
                    group_name="Op\u0161ti podaci",
                )
            )

        await self.session.flush()

    async def list_category_attributes(
        self,
        category_id: uuid.UUID,
        *,
        active_only: bool = True,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[CategoryAttribute]:
        filters = [CategoryAttribute.category_id == category_id]

        if active_only:
            filters.extend(
                [
                    CategoryAttribute.is_active.is_(True),
                    AttributeDefinition.is_active.is_(True),
                ]
            )

        query = (
            select(CategoryAttribute)
            .join(CategoryAttribute.attribute)
            .options(selectinload(CategoryAttribute.attribute))
            .where(*filters)
            .order_by(
                CategoryAttribute.position,
                AttributeDefinition.name,
                CategoryAttribute.id,
            )
        )
        query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        result = await self.session.execute(query)

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

    async def update_category_attribute(
        self,
        link: CategoryAttribute,
        *,
        position: int,
        group_name: str | None,
    ) -> CategoryAttribute:
        link.position = position
        link.group_name = group_name
        link.version += 1
        await self.session.flush()
        return link


__all__ = ["LegacyAttributeRepository"]
