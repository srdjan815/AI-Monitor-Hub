from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select

from app.modules.catalog.models import AttributeDefinition, Category, CategoryAttribute
from app.modules.catalog.platform_models import (
    AttributeFamily,
    AttributeTemplate,
    AttributeTemplateItem,
    CategoryAttributeTemplate,
)
from app.modules.catalog.platform_service_support import _PlatformServiceSupport
from app.modules.catalog.schemas.attribute_platform import (
    TemplateCreate,
    TemplateImport,
    TemplateItemCreate,
    TemplateUpdate,
)
from app.modules.catalog.utils import stable_code


class AttributeTemplateService(_PlatformServiceSupport):
    """Owns template definitions, inheritance, import/export, and assignment."""

    async def create_template(self, data: TemplateCreate) -> AttributeTemplate:
        if data.parent_template_id:
            await self._required(
                AttributeTemplate,
                data.parent_template_id,
                "Parent template",
            )
        template = AttributeTemplate(
            name=data.name.strip(),
            slug=stable_code(data.slug or data.name),
            description=data.description,
            parent_template_id=data.parent_template_id,
        )
        self.session.add(template)
        await self.session.flush()
        return await self._commit(template)

    async def update_template(
        self,
        template_id: uuid.UUID,
        data: TemplateUpdate,
    ) -> AttributeTemplate:
        template = await self._required(
            AttributeTemplate,
            template_id,
            "Template",
        )
        changes = data.model_dump(exclude_unset=True)
        if changes.get("parent_template_id") == template.id:
            raise HTTPException(
                status_code=422,
                detail="Template cannot inherit itself",
            )
        for key, value in changes.items():
            setattr(template, key, value)
        if changes:
            template.version += 1
        await self.session.flush()
        return await self._commit(template)

    async def list_templates(
        self,
        active_only: bool,
        offset: int,
        limit: int,
    ) -> list[AttributeTemplate]:
        query = select(AttributeTemplate)
        if active_only:
            query = query.where(AttributeTemplate.is_active.is_(True))
        rows = await self.session.execute(
            query.order_by(AttributeTemplate.name, AttributeTemplate.id)
            .offset(offset)
            .limit(limit)
        )
        return list(rows.scalars())

    async def add_template_item(
        self,
        template_id: uuid.UUID,
        data: TemplateItemCreate,
    ) -> AttributeTemplateItem:
        await self._required(AttributeTemplate, template_id, "Template")
        await self._required(
            AttributeDefinition,
            data.attribute_definition_id,
            "Attribute",
        )
        if data.family_id:
            await self._required(AttributeFamily, data.family_id, "Family")
        item = AttributeTemplateItem(
            template_id=template_id,
            **data.model_dump(),
        )
        self.session.add(item)
        await self.session.flush()
        template = await self._required(
            AttributeTemplate,
            template_id,
            "Template",
        )
        template.version += 1
        return await self._commit(item)

    async def deactivate_template_item(self, item_id: uuid.UUID) -> None:
        item = await self._required(
            AttributeTemplateItem,
            item_id,
            "Template item",
        )
        item.is_active = False
        template = await self._required(
            AttributeTemplate,
            item.template_id,
            "Template",
        )
        template.version += 1
        await self._commit()

    async def template_export(self, template_id: uuid.UUID) -> dict[str, Any]:
        template = await self._required(
            AttributeTemplate,
            template_id,
            "Template",
        )
        rows = await self.session.execute(
            select(AttributeTemplateItem)
            .where(
                AttributeTemplateItem.template_id == template_id,
                AttributeTemplateItem.is_active.is_(True),
            )
            .order_by(AttributeTemplateItem.sort_order)
        )
        return {
            "name": template.name,
            "slug": template.slug,
            "description": template.description,
            "version": template.version,
            "items": [
                {
                    "attribute_definition_id": item.attribute_definition_id,
                    "family_id": item.family_id,
                    "sort_order": item.sort_order,
                    "is_required_override": item.is_required_override,
                }
                for item in rows.scalars()
            ],
        }

    async def import_template(self, data: TemplateImport) -> AttributeTemplate:
        try:
            template = AttributeTemplate(
                name=data.name.strip(),
                slug=stable_code(data.slug),
                description=data.description,
            )
            self.session.add(template)
            await self.session.flush()
            for item in data.items:
                await self._required(
                    AttributeDefinition,
                    item.attribute_definition_id,
                    "Attribute",
                )
                if item.family_id:
                    await self._required(
                        AttributeFamily,
                        item.family_id,
                        "Family",
                    )
                self.session.add(
                    AttributeTemplateItem(
                        template_id=template.id,
                        **item.model_dump(),
                    )
                )
            await self.session.flush()
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(template)
        return template

    async def clone_template(
        self,
        template_id: uuid.UUID,
        name: str,
        slug: str,
    ) -> AttributeTemplate:
        exported = await self.template_export(template_id)
        return await self.import_template(
            TemplateImport(
                name=name,
                slug=slug,
                description=exported["description"],
                items=[TemplateItemCreate(**item) for item in exported["items"]],
            )
        )

    async def assign_template(
        self,
        template_id: uuid.UUID,
        category_id: uuid.UUID,
    ) -> dict[str, int]:
        await self._required(AttributeTemplate, template_id, "Template")
        await self._required(Category, category_id, "Category")
        template_ids = await self._template_chain(template_id)
        rows = await self.session.execute(
            select(AttributeTemplateItem)
            .where(
                AttributeTemplateItem.template_id.in_(template_ids),
                AttributeTemplateItem.is_active.is_(True),
            )
            .order_by(AttributeTemplateItem.sort_order)
        )
        created = 0
        for item in rows.scalars():
            existing = await self.session.scalar(
                select(CategoryAttribute).where(
                    CategoryAttribute.category_id == category_id,
                    CategoryAttribute.attribute_id == item.attribute_definition_id,
                )
            )
            if existing:
                if not existing.is_active:
                    existing.is_active = True
                continue
            self.session.add(
                CategoryAttribute(
                    category_id=category_id,
                    attribute_id=item.attribute_definition_id,
                    position=item.sort_order,
                    is_required_override=item.is_required_override,
                )
            )
            created += 1
        association = await self.session.scalar(
            select(CategoryAttributeTemplate).where(
                CategoryAttributeTemplate.category_id == category_id,
                CategoryAttributeTemplate.template_id == template_id,
            )
        )
        if association:
            association.is_active = True
        else:
            self.session.add(
                CategoryAttributeTemplate(
                    category_id=category_id,
                    template_id=template_id,
                )
            )
        await self.session.flush()
        await self._commit()
        return {"assignments_created": created}

    async def unassign_template(
        self,
        template_id: uuid.UUID,
        category_id: uuid.UUID,
    ) -> None:
        association = await self.session.scalar(
            select(CategoryAttributeTemplate).where(
                CategoryAttributeTemplate.category_id == category_id,
                CategoryAttributeTemplate.template_id == template_id,
            )
        )
        if association is None:
            raise HTTPException(
                status_code=404,
                detail="Template assignment not found",
            )
        association.is_active = False
        await self._commit()

    async def _template_chain(self, template_id: uuid.UUID) -> list[uuid.UUID]:
        chain: list[uuid.UUID] = []
        seen: set[uuid.UUID] = set()
        current: AttributeTemplate | None = await self._required(
            AttributeTemplate,
            template_id,
            "Template",
        )
        while current:
            if current.id in seen:
                raise HTTPException(
                    status_code=422,
                    detail="Template inheritance cycle",
                )
            seen.add(current.id)
            chain.append(current.id)
            current = (
                await self.session.get(
                    AttributeTemplate,
                    current.parent_template_id,
                )
                if current.parent_template_id
                else None
            )
        chain.reverse()
        return chain
