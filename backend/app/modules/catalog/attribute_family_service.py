from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import func, or_, select

from app.modules.catalog.models import AttributeDefinition, Category
from app.modules.catalog.platform_models import (
    AttributeFamily,
    AttributeFamilyItem,
    AttributeTemplate,
    AttributeTemplateFamily,
    CategoryAttributeFamily,
)
from app.modules.catalog.platform_service_support import _PlatformServiceSupport
from app.modules.catalog.schemas.attribute_platform import (
    NamedEntityCreate,
    NamedEntityUpdate,
)
from app.modules.catalog.utils import stable_code


class AttributeFamilyService(_PlatformServiceSupport):
    """Owns family metadata, membership, assignments, and family usage."""

    async def create_family(self, data: NamedEntityCreate) -> AttributeFamily:
        family = AttributeFamily(
            name=data.name.strip(),
            slug=stable_code(data.slug or data.name),
            description=data.description,
            sort_order=data.sort_order,
        )
        self.session.add(family)
        await self.session.flush()
        return await self._commit(family)

    async def update_family(
        self,
        family_id: uuid.UUID,
        data: NamedEntityUpdate,
    ) -> AttributeFamily:
        family = await self._required(AttributeFamily, family_id, "Family")
        changes = data.model_dump(exclude_unset=True)
        for key, value in changes.items():
            setattr(family, key, value)
        if changes:
            family.version += 1
        await self.session.flush()
        return await self._commit(family)

    async def list_families(
        self,
        *,
        active_only: bool,
        search: str | None,
        offset: int,
        limit: int,
    ) -> list[AttributeFamily]:
        query = select(AttributeFamily)
        if active_only:
            query = query.where(AttributeFamily.is_active.is_(True))
        if search:
            token = f"%{search}%"
            query = query.where(
                or_(
                    AttributeFamily.name.ilike(token),
                    AttributeFamily.slug.ilike(token),
                )
            )
        result = await self.session.execute(
            query.order_by(
                AttributeFamily.sort_order,
                AttributeFamily.name,
                AttributeFamily.id,
            )
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars())

    async def add_family_item(
        self,
        family_id: uuid.UUID,
        attribute_id: uuid.UUID,
        sort_order: int,
    ) -> AttributeFamilyItem:
        await self._required(AttributeFamily, family_id, "Family")
        await self._required(AttributeDefinition, attribute_id, "Attribute")
        item = AttributeFamilyItem(
            family_id=family_id,
            attribute_definition_id=attribute_id,
            sort_order=sort_order,
        )
        self.session.add(item)
        await self.session.flush()
        return await self._commit(item)

    async def assign_family_category(
        self,
        family_id: uuid.UUID,
        category_id: uuid.UUID,
        sort_order: int,
    ) -> CategoryAttributeFamily:
        await self._required(AttributeFamily, family_id, "Family")
        await self._required(Category, category_id, "Category")
        assignment = CategoryAttributeFamily(
            family_id=family_id,
            category_id=category_id,
            sort_order=sort_order,
        )
        self.session.add(assignment)
        await self.session.flush()
        return await self._commit(assignment)

    async def assign_family_template(
        self,
        family_id: uuid.UUID,
        template_id: uuid.UUID,
        sort_order: int,
    ) -> AttributeTemplateFamily:
        await self._required(AttributeFamily, family_id, "Family")
        await self._required(AttributeTemplate, template_id, "Template")
        assignment = AttributeTemplateFamily(
            family_id=family_id,
            template_id=template_id,
            sort_order=sort_order,
        )
        self.session.add(assignment)
        await self.session.flush()
        return await self._commit(assignment)

    async def remove_family_category(
        self,
        family_id: uuid.UUID,
        category_id: uuid.UUID,
    ) -> None:
        assignment = await self.session.scalar(
            select(CategoryAttributeFamily).where(
                CategoryAttributeFamily.family_id == family_id,
                CategoryAttributeFamily.category_id == category_id,
            )
        )
        if assignment is None:
            raise HTTPException(
                status_code=404,
                detail="Family assignment not found",
            )
        assignment.is_active = False
        await self._commit()

    async def remove_family_template(
        self,
        family_id: uuid.UUID,
        template_id: uuid.UUID,
    ) -> None:
        assignment = await self.session.scalar(
            select(AttributeTemplateFamily).where(
                AttributeTemplateFamily.family_id == family_id,
                AttributeTemplateFamily.template_id == template_id,
            )
        )
        if assignment is None:
            raise HTTPException(
                status_code=404,
                detail="Family assignment not found",
            )
        await self.session.delete(assignment)
        await self.session.flush()
        await self._commit()

    async def deactivate_family_item(self, item_id: uuid.UUID) -> None:
        item = await self._required(AttributeFamilyItem, item_id, "Family item")
        item.is_active = False
        await self._commit()

    async def family_usage(self, family_id: uuid.UUID) -> dict[str, int]:
        await self._required(AttributeFamily, family_id, "Family")
        return {
            "attributes": int(
                await self.session.scalar(
                    select(func.count(AttributeFamilyItem.id)).where(
                        AttributeFamilyItem.family_id == family_id,
                        AttributeFamilyItem.is_active.is_(True),
                    )
                )
                or 0
            ),
            "templates": int(
                await self.session.scalar(
                    select(func.count(AttributeTemplateFamily.id)).where(
                        AttributeTemplateFamily.family_id == family_id
                    )
                )
                or 0
            ),
            "categories": int(
                await self.session.scalar(
                    select(func.count(CategoryAttributeFamily.id)).where(
                        CategoryAttributeFamily.family_id == family_id,
                        CategoryAttributeFamily.is_active.is_(True),
                    )
                )
                or 0
            ),
        }
