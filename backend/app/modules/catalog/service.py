from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.enums import AttributeScope
from app.modules.catalog.models import AttributeDefinition, Category
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import (
    AttributeCreate,
    AttributeUpdate,
    CategoryAttributeReorder,
    CategoryCreate,
    CategoryUpdate,
)
from app.modules.catalog.utils import stable_code


class CatalogService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = CatalogRepository(session)

    async def _get_category_or_404(
        self,
        category_id: uuid.UUID,
    ) -> Category:
        category = await self.repository.get_category(category_id)

        if category is None:
            raise HTTPException(
                status_code=404,
                detail="Kategorija nije pronađena",
            )

        return category

    async def _validate_parent_category(
        self,
        *,
        category_id: uuid.UUID | None,
        parent_id: uuid.UUID | None,
    ) -> None:
        if parent_id is None:
            return

        if category_id is not None and parent_id == category_id:
            raise HTTPException(
                status_code=422,
                detail="Kategorija ne može biti sopstveni roditelj",
            )

        parent = await self.repository.get_category(parent_id)

        if parent is None:
            raise HTTPException(
                status_code=404,
                detail="Roditeljska kategorija ne postoji",
            )

        if category_id is None:
            return

        visited: set[uuid.UUID] = set()
        current: Category | None = parent

        while current is not None:
            if current.id == category_id:
                raise HTTPException(
                    status_code=422,
                    detail="Nije dozvoljena kružna hijerarhija kategorija",
                )

            if current.id in visited:
                raise HTTPException(
                    status_code=422,
                    detail="Otkrivena je neispravna hijerarhija kategorija",
                )

            visited.add(current.id)

            if current.parent_id is None:
                break

            current = await self.repository.get_category(current.parent_id)

    async def create_category(
        self,
        data: CategoryCreate,
    ) -> Category:
        name = data.name.strip()

        if not name:
            raise HTTPException(
                status_code=422,
                detail="Naziv kategorije ne sme biti prazan",
            )

        code = stable_code(data.code or name)

        if await self.repository.get_category_by_code(code):
            raise HTTPException(
                status_code=409,
                detail="Kod kategorije već postoji",
            )

        await self._validate_parent_category(
            category_id=None,
            parent_id=data.parent_id,
        )

        category = Category(
            name=name,
            code=code,
            parent_id=data.parent_id,
            position=data.position,
        )

        try:
            await self.repository.create_category(category)
            await self.repository.link_all_global_attributes(category.id)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Kategorija sa tim nazivom već postoji",
            ) from exc

        await self.session.refresh(category)
        return category

    async def update_category(
        self,
        category_id: uuid.UUID,
        data: CategoryUpdate,
    ) -> Category:
        category = await self._get_category_or_404(category_id)
        changes = data.model_dump(exclude_unset=True)

        if "name" in changes:
            name = changes["name"].strip()

            if not name:
                raise HTTPException(
                    status_code=422,
                    detail="Naziv kategorije ne sme biti prazan",
                )

            changes["name"] = name

        if "parent_id" in changes:
            await self._validate_parent_category(
                category_id=category_id,
                parent_id=changes["parent_id"],
            )

        for field, value in changes.items():
            setattr(category, field, value)

        if changes:
            category.version += 1

        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Kategorija sa tim nazivom već postoji",
            ) from exc

        await self.session.refresh(category)
        return category

    async def deactivate_category(
        self,
        category_id: uuid.UUID,
    ) -> None:
        category = await self._get_category_or_404(category_id)

        if not category.is_active:
            return

        category.is_active = False
        category.version += 1

        await self.session.commit()

    async def create_attribute(
        self,
        data: AttributeCreate,
    ) -> AttributeDefinition:
        name = data.name.strip()

        if not name:
            raise HTTPException(
                status_code=422,
                detail="Naziv atributa ne sme biti prazan",
            )

        code = stable_code(data.code or name)

        if await self.repository.get_attribute_by_code(code):
            raise HTTPException(
                status_code=409,
                detail="Kod atributa već postoji",
            )

        if (
            data.category_id is not None
            and not await self.repository.get_category(data.category_id)
        ):
            raise HTTPException(
                status_code=404,
                detail="Kategorija nije pronađena",
            )

        attribute = AttributeDefinition(
            name=name,
            code=code,
            scope=data.scope.value,
            data_type=data.data_type.value,
            unit=data.unit,
            description=data.description,
            ai_prompt=data.ai_prompt,
            example_value=data.example_value,
            validation_rules=data.validation_rules,
            api_name=stable_code(data.api_name or code),
            is_required=data.is_required,
            is_visible=data.is_visible,
            is_filterable=data.is_filterable,
            is_searchable=data.is_searchable,
            allows_multiple=data.allows_multiple,
        )

        try:
            await self.repository.create_attribute(attribute)

            if data.scope == AttributeScope.GLOBAL:
                await self.repository.link_global_attribute_to_all_categories(
                    attribute.id
                )
            else:
                await self.repository.link_attribute(
                    category_id=data.category_id,
                    attribute_id=attribute.id,
                    position=data.position,
                    group_name=data.group_name,
                )

            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Atribut već postoji",
            ) from exc

        await self.session.refresh(attribute)
        return attribute

    async def update_attribute(
        self,
        attribute_id: uuid.UUID,
        data: AttributeUpdate,
    ) -> AttributeDefinition:
        attribute = await self.repository.get_attribute(attribute_id)

        if attribute is None:
            raise HTTPException(
                status_code=404,
                detail="Atribut nije pronađen",
            )

        changes = data.model_dump(exclude_unset=True)

        if "name" in changes:
            name = changes["name"].strip()

            if not name:
                raise HTTPException(
                    status_code=422,
                    detail="Naziv atributa ne sme biti prazan",
                )

            changes["name"] = name

        if "data_type" in changes and changes["data_type"] is not None:
            changes["data_type"] = changes["data_type"].value

        for field, value in changes.items():
            setattr(attribute, field, value)

        if changes:
            attribute.version += 1

        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Atribut već postoji",
            ) from exc

        await self.session.refresh(attribute)
        return attribute

    async def reorder_category_attributes(
        self,
        category_id: uuid.UUID,
        data: CategoryAttributeReorder,
    ) -> None:
        if not await self.repository.get_category(category_id):
            raise HTTPException(
                status_code=404,
                detail="Kategorija nije pronađena",
            )

        for item in data.items:
            link = await self.repository.get_category_attribute(
                category_id,
                item.attribute_id,
            )

            if link is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Atribut {item.attribute_id} "
                        "nije povezan sa kategorijom"
                    ),
                )

            link.position = item.position
            link.group_name = item.group_name
            link.version += 1

        await self.session.commit()