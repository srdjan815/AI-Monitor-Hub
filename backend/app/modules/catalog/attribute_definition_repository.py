from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, case, false, func, or_, select, tuple_
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from app.modules.catalog.attribute_models import (
    AttributeGroup,
    ProductAttributeValue,
)
from app.modules.catalog.models import (
    AttributeDefinition,
    Category,
    CategoryAttribute,
)
from app.modules.catalog.platform_models import (
    AttributeFamilyItem,
    AttributeTemplateItem,
)

from app.modules.catalog.attribute_repository_support import (
    ProductAttributeRepositorySupport,
)


class AttributeDefinitionRepository(ProductAttributeRepositorySupport):
    async def list_groups(
        self,
        active_only: bool,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[AttributeGroup]:
        query = select(AttributeGroup)
        if active_only:
            query = query.where(AttributeGroup.is_active.is_(True))
        query = query.order_by(
            AttributeGroup.sort_order,
            AttributeGroup.slug,
            AttributeGroup.id,
        ).offset(offset)
        if limit is not None:
            query = query.limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars())

    async def group_by_slug(self, slug: str) -> AttributeGroup | None:
        result = await self.session.scalars(
            select(AttributeGroup).where(AttributeGroup.slug == slug)
        )
        return result.first()

    async def list_definitions(
        self,
        *,
        active_only: bool,
        scope: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int | None = None,
        snapshot_at: datetime | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> list[AttributeDefinition]:
        query = select(AttributeDefinition)
        if active_only:
            query = query.where(AttributeDefinition.is_active.is_(True))
        if scope:
            query = query.where(AttributeDefinition.scope == scope)
        if search:
            token = f"%{search}%"
            query = query.where(
                or_(
                    AttributeDefinition.name.ilike(token),
                    AttributeDefinition.slug.ilike(token),
                    AttributeDefinition.api_name.ilike(token),
                )
            )
        if snapshot_at is not None:
            query = query.where(AttributeDefinition.created_at <= snapshot_at)
        if after is not None:
            after_at, after_id = after
            query = query.where(
                or_(
                    AttributeDefinition.created_at < after_at,
                    and_(
                        AttributeDefinition.created_at == after_at,
                        AttributeDefinition.id < after_id,
                    ),
                )
            )
        if snapshot_at is None and after is None:
            query = query.order_by(
                AttributeDefinition.default_sort_order,
                AttributeDefinition.slug,
                AttributeDefinition.id,
            )
        else:
            query = query.order_by(
                AttributeDefinition.created_at.desc(),
                AttributeDefinition.id.desc(),
            )
        query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars())

    async def resolved_definitions_page(
        self,
        *,
        category_ids: list[uuid.UUID],
        product_id: uuid.UUID | None,
        include_unset: bool,
        scope: str | None,
        group_id: uuid.UUID | None,
        family_id: uuid.UUID | None,
        template_ids: set[uuid.UUID],
        filter_only: bool,
        compatibility_only: bool,
        snapshot_at: datetime,
        after: tuple[datetime, uuid.UUID] | None,
        limit: int,
    ) -> tuple[list[AttributeDefinition], int, bool]:
        assigned = (
            select(CategoryAttribute.id)
            .where(
                CategoryAttribute.category_id.in_(category_ids),
                CategoryAttribute.attribute_id == AttributeDefinition.id,
                CategoryAttribute.is_active.is_(True),
            )
            .exists()
        )
        visibility = or_(
            AttributeDefinition.scope.in_(["GLOBAL", "SYSTEM"]),
            assigned,
        )
        if not include_unset:
            has_value = (
                select(ProductAttributeValue.id)
                .where(
                    ProductAttributeValue.product_id == product_id,
                    ProductAttributeValue.attribute_definition_id
                    == AttributeDefinition.id,
                    ProductAttributeValue.is_active.is_(True),
                )
                .exists()
                if product_id is not None
                else false()
            )
            visibility = or_(
                AttributeDefinition.scope == "SYSTEM",
                and_(
                    AttributeDefinition.scope != "GLOBAL",
                    assigned,
                ),
                has_value,
            )
        filters = [
            AttributeDefinition.is_active.is_(True),
            AttributeDefinition.created_at <= snapshot_at,
            visibility,
        ]
        if scope:
            filters.append(AttributeDefinition.scope == scope)
        assignment_depth = case(
            {category_id: depth for depth, category_id in enumerate(category_ids)},
            value=CategoryAttribute.category_id,
            else_=-1,
        )

        def winning_override(
            column: InstrumentedAttribute[Any],
        ) -> ColumnElement[Any]:
            return (
                select(column)
                .where(
                    CategoryAttribute.category_id.in_(category_ids),
                    CategoryAttribute.attribute_id == AttributeDefinition.id,
                    CategoryAttribute.is_active.is_(True),
                )
                .order_by(assignment_depth.desc())
                .limit(1)
                .correlate(AttributeDefinition)
                .scalar_subquery()
            )

        if group_id:
            filters.append(
                func.coalesce(
                    winning_override(CategoryAttribute.group_id_override),
                    AttributeDefinition.group_id,
                )
                == group_id
            )
        if family_id:
            filters.append(
                select(AttributeFamilyItem.id)
                .where(
                    AttributeFamilyItem.family_id == family_id,
                    AttributeFamilyItem.attribute_definition_id
                    == AttributeDefinition.id,
                    AttributeFamilyItem.is_active.is_(True),
                )
                .exists()
            )
        if template_ids:
            filters.append(
                select(AttributeTemplateItem.id)
                .where(
                    AttributeTemplateItem.template_id.in_(template_ids),
                    AttributeTemplateItem.attribute_definition_id
                    == AttributeDefinition.id,
                    AttributeTemplateItem.is_active.is_(True),
                )
                .exists()
            )
        if filter_only:
            filters.append(
                func.coalesce(
                    winning_override(CategoryAttribute.is_filter_override),
                    AttributeDefinition.is_filterable,
                ).is_(True)
            )
        if compatibility_only:
            filters.append(
                func.coalesce(
                    winning_override(CategoryAttribute.is_compatibility_override),
                    AttributeDefinition.is_compatibility_attribute,
                ).is_(True)
            )
        order_columns = (
            AttributeDefinition.created_at,
            AttributeDefinition.id,
        )
        page_filters = list(filters)
        if after:
            page_filters.append(tuple_(*order_columns) > after)
        query = (
            select(AttributeDefinition)
            .where(*page_filters)
            .order_by(*order_columns)
            .limit(limit + 1)
        )
        definitions = list((await self.session.scalars(query)).all())
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(AttributeDefinition).where(*filters)
            )
            or 0
        )
        has_next = len(definitions) > limit
        return definitions[:limit], total, has_next

    async def definition_by_identity(self, value: str) -> AttributeDefinition | None:
        result = await self.session.scalars(
            select(AttributeDefinition).where(
                or_(
                    AttributeDefinition.slug == value,
                    AttributeDefinition.api_name == value,
                    AttributeDefinition.internal_name == value,
                    AttributeDefinition.code == value,
                )
            )
        )
        return result.first()

    async def list_category_chain(self, category_id: uuid.UUID) -> list[Category]:
        chain: list[Category] = []
        seen: set[uuid.UUID] = set()
        current = await self.get(Category, category_id)
        while current is not None and current.id not in seen:
            chain.append(current)
            seen.add(current.id)
            current = (
                await self.get(Category, current.parent_id)
                if current.parent_id
                else None
            )
        chain.reverse()
        return chain


__all__ = ["AttributeDefinitionRepository"]
